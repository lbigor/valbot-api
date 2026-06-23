"""
Tier A pipeline — gera `storage/analyses/<hash>/result.json` para 1 vídeo.

Cobre apenas os 2 IDs Tier A da Res. CONTRAN 1.020/2025:
    - R1020-G-a    (sinalização semafórica / placa PARE) — câmera FRONTAL
    - R1020-GR-f   (cinto de segurança) — câmera INTERNA

Modo MVP (sem VLM em runtime): extrai/filtra evidência e marca os itens Tier A
como `pendente_revisao_humana`. A revisão é feita pela skill /avaliador-detran
(o chat atua como VLM, custo zero).

Tier B é incluído como `pendente_revisao_humana` sem candidatos (varredura
passiva fica para iteração futura).
Tier C entra como `pendente_infraestrutura` com `infra_faltante` da taxonomia.

Uso:
    python -m src.tier_a_pipeline storage/videos/1.mp4
    python -m src.tier_a_pipeline --all   # processa os 4 vídeos do dataset
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from collections import defaultdict
from pathlib import Path

from src.detectors.cinto_sampler import amostrar_cinto, verdict_to_dict
from src.detectors.yolo_filter import (
    carregar_votos,
    filtrar_yolo_com_votos,
)
from src.ingestion.grid_slicer import GridSlicer
from src.rubrics.taxonomia import (
    Rubrica,
    StatusAvaliacao,
    Tier,
    por_id,
    por_tier,
)

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
STORAGE = ROOT / "storage"


# ============================================================================
# Filtros YOLO (do feedback_yolo_tier_a_filtros)
# ============================================================================


def is_overlay_bbox(bbox, frame_w: int = 640, frame_h: int = 360) -> bool:
    """
    Bbox que coincide com a zona do overlay '01'-'99' da câmera VIP Intelbras
    no quadrante TL (frontal). 343/343 FPs nos 4 vídeos caem aqui.
    """
    x1, y1, x2, y2 = bbox[:4]
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    return 180 <= cx <= 240 and 10 <= cy <= 50


def _road_text_e_contexto(d: dict) -> bool:
    """
    Filtra ruído recorrente do detector de texto de pista.

    O detector costuma reagir à borda entre quadrantes e a textos genéricos
    do asfalto. Esses hits aparecem muito perto de y≈180 na imagem e poluem
    bastante a fila de revisão de R1020-G-a.
    """
    bbox = d.get("bbox") or [0, 0, 0, 0]
    y = bbox[1] if len(bbox) > 1 else 0
    conf = float(d.get("confidence", 0.0))
    evidence = (d.get("evidence") or "").strip().upper()
    if evidence == "PARE":
        return False
    if y < 185:
        return True
    return bool(conf < 0.65 and not evidence)


def filtrar_yolo(detections: list[dict]) -> dict:
    """
    Aplica filtros do feedback_yolo_tier_a_filtros:
      - descarta bbox no overlay
      - cluster temporal ≥3 frames consecutivos (mesmo bbox ±15px) = confiável
      - bbox >25x25 + conf >0.28 + classe 'stop sign' isolado = suspeito promissor
      - resto = descartado

    Espera detections com keys: timestamp_s, class_name, confidence, bbox.
    """

    # schema do yolo_explore: class, conf, ts, bbox, frame_idx, track_id
    def _norm(d: dict) -> dict:
        return {
            "frame_idx": d.get("frame_idx"),
            "timestamp_s": d.get("ts", d.get("timestamp_s", 0.0)),
            "class_name": d.get("class", d.get("class_name", "")),
            "confidence": d.get("conf", d.get("confidence", 0.0)),
            "bbox": d["bbox"],
            "track_id": d.get("track_id"),
        }

    detections = [_norm(d) for d in detections]
    relevantes = [d for d in detections if d["class_name"] in ("traffic light", "stop sign")]

    # O overlay numérico "01"-"99" do gravador VIP Intelbras tipicamente é
    # confundido pelo YOLO como `traffic light` (formato retangular pequeno).
    # `stop sign` é octogonal/redondo — overlay quase nunca dispara essa
    # classe. Restringimos o filtro de overlay a `traffic light` para não
    # descartar placa Pare real que coincida com a região (placa distante).
    def _is_overlay_fp(d):
        return d["class_name"] == "traffic light" and is_overlay_bbox(d["bbox"])

    sem_overlay = [d for d in relevantes if not _is_overlay_fp(d)]
    overlay = [d for d in relevantes if _is_overlay_fp(d)]

    # cluster temporal por classe
    sem_overlay.sort(key=lambda d: (d["class_name"], d["timestamp_s"]))
    confiavel: list[dict] = []
    suspeito: list[dict] = []
    descartado: list[dict] = []

    by_class = defaultdict(list)
    for d in sem_overlay:
        by_class[d["class_name"]].append(d)

    for cls, group in by_class.items():
        # cluster: frames próximos (Δt ≤ 1.0s) e bbox próximo (centro ±15px)
        clusters: list[list[dict]] = []
        cur: list[dict] = []
        for d in group:
            if not cur:
                cur = [d]
                continue
            last = cur[-1]
            dt = d["timestamp_s"] - last["timestamp_s"]
            cx_l = (last["bbox"][0] + last["bbox"][2]) / 2
            cy_l = (last["bbox"][1] + last["bbox"][3]) / 2
            cx_d = (d["bbox"][0] + d["bbox"][2]) / 2
            cy_d = (d["bbox"][1] + d["bbox"][3]) / 2
            if dt <= 1.0 and abs(cx_d - cx_l) <= 15 and abs(cy_d - cy_l) <= 15:
                cur.append(d)
            else:
                clusters.append(cur)
                cur = [d]
        if cur:
            clusters.append(cur)

        for c in clusters:
            if len(c) >= 3:
                # cluster confiável: representado pelo frame de maior confidence
                best = max(c, key=lambda x: x["confidence"])
                confiavel.append({**best, "cluster_size": len(c)})
            else:
                # isolado: checa exceção placa PARE bbox grande + conf alta
                d = c[0] if len(c) == 1 else max(c, key=lambda x: x["confidence"])
                bw = d["bbox"][2] - d["bbox"][0]
                bh = d["bbox"][3] - d["bbox"][1]
                if cls == "stop sign" and bw > 25 and bh > 25 and d["confidence"] > 0.28:
                    suspeito.append({**d, "cluster_size": len(c)})
                else:
                    for x in c:
                        descartado.append(x)

    return {
        "confiavel": confiavel,
        "suspeito": suspeito,
        "descartado": descartado,
        "overlay_descartado": len(overlay),
        "stats": {
            "total_relevantes": len(relevantes),
            "overlay_fp": len(overlay),
            "confiavel": len(confiavel),
            "suspeito": len(suspeito),
            "descartado": len(descartado),
        },
    }


# ============================================================================
# Pipeline
# ============================================================================


def sha256_arquivo(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _avaliar_cinto(video_path: Path, analysis_dir: Path) -> dict:
    """
    Cinto sampler com decisão automática:
    - Se houver pose.json, usa heurística determinística (HSV + Hough diagonal)
    - Caso contrário, fica em pendente_revisao_humana
    """
    from src.detectors.cinto_heuristica import heuristica_callback_factory

    cinto_dir = analysis_dir / "cinto"
    pose_path = analysis_dir / "pose.json"
    callback = heuristica_callback_factory(pose_path) if pose_path.exists() else None
    verdict = amostrar_cinto(
        video_path=video_path,
        output_dir=cinto_dir,
        vlm_callback=callback,
        max_retries=3,
        seed=video_path.name,
    )
    trail_path = analysis_dir / "cinto_trail.json"
    trail_path.write_text(json.dumps(verdict_to_dict(verdict), indent=2, ensure_ascii=False))
    infra = por_id("R1020-GR-f")
    assert infra is not None, "taxonomia R1020-GR-f deve existir"
    return {
        "id": "R1020-GR-f",
        "descricao": infra.descricao,
        "severidade": infra.severidade.value,
        "pontos": infra.pontos,
        "tier": infra.tier.value,
        "status": "pendente_revisao_humana",
        "veredito": verdict.veredito,
        "confianca": verdict.confianca,
        "motivo": verdict.motivo,
        "rondadas_retry": verdict.rondadas_retry,
        "frames_extraidos": len(verdict.frames),
        "cinto_trail": str(trail_path.relative_to(STORAGE)),
    }


def _candidatos_cv(analysis_dir: Path) -> list[dict]:
    """
    Converte hits do cv_detections.json (road_text, traffic_light heurístico)
    em candidatos suspeitos para R1020-G-a. Hoje road_text NÃO faz OCR ainda
    (item 2 da fila), então o texto entra como sinal ambíguo — precisa
    revisão humana pra confirmar se é PARE, faixa de pedestre ou outro.
    """
    cv_path = analysis_dir / "cv_detections.json"
    if not cv_path.exists():
        return []
    try:
        cv = json.loads(cv_path.read_text())
    except Exception:
        return []
    out: list[dict] = []
    name_map = {
        "road_text": "road_text_cv",
        "traffic_light": "traffic_light_cv",
        "pare_sign": "pare_sign_cv",
    }
    for d in cv.get("detections", []):
        t = d.get("type")
        if t not in name_map:
            continue
        if t == "road_text" and _road_text_e_contexto(
            {
                "bbox": d.get("bbox"),
                "confidence": d.get("confidence", 0.0),
                "evidence": d.get("evidence", ""),
            }
        ):
            continue
        out.append(
            {
                "frame_idx": d.get("frame_idx"),
                "timestamp_s": d.get("ts"),
                "class_name": name_map[t],
                "confidence": d.get("confidence", 0.0),
                "bbox": d.get("bbox"),
                "origem": f"cv:{t}",
                "evidence": d.get("evidence", ""),
            }
        )

    # Aplica blacklist live dos votos /training-example refuted vote=N
    # para R1020-G-a. Mesma janela ±1.5s que filtrar_yolo_com_votos usa.
    votos = carregar_votos()
    hash_atual = analysis_dir.name
    bl_live = [
        b
        for b in votos.blacklist_bbox
        if b.get("source") == "live" and b.get("video") == hash_atual and b.get("ts") is not None
    ]
    if bl_live:

        def _vetado(d):
            ts = d.get("timestamp_s")
            if ts is None:
                return False
            return any(abs(ts - float(b["ts"])) <= 1.5 for b in bl_live)

        out = [d for d in out if not _vetado(d)]
    return out


def _avaliar_sinal_vertical(analysis_dir: Path) -> dict:
    """Lê yolo_explore/detections.json e funde com cv_detections.json."""
    det_path = analysis_dir / "yolo_explore" / "detections.json"
    infra = por_id("R1020-G-a")
    assert infra is not None, "taxonomia R1020-G-a deve existir"
    base = {
        "id": "R1020-G-a",
        "descricao": infra.descricao,
        "severidade": infra.severidade.value,
        "pontos": infra.pontos,
        "tier": infra.tier.value,
        "status": "pendente_revisao_humana",
    }

    cv_susp = _candidatos_cv(analysis_dir)

    if not det_path.exists():
        if cv_susp:
            return {
                **base,
                "veredito": "candidatos_para_revisao",
                "motivo": f"YOLO ausente; {len(cv_susp)} candidatos do CV",
                "stats": {"yolo_ausente": True, "cv_suspeitos": len(cv_susp)},
                "candidatos_confiavel": [],
                "candidatos_suspeito": cv_susp,
            }
        return {
            **base,
            "veredito": "inconclusivo",
            "motivo": "yolo_explore/detections.json ausente e sem CV",
            "candidatos_confiavel": [],
            "candidatos_suspeito": [],
        }

    raw = json.loads(det_path.read_text())
    detections = raw if isinstance(raw, list) else raw.get("detections", [])
    # Filtra com retroalimentação dos votos:
    #   - 39 curados originais (matching por filename "1.mp4" ↔ "vid1")
    #   - votos novos via UI examples.jsonl (matching por hash sha256)
    h = analysis_dir.name  # storage/analyses/<sha256>
    # Reconstrói filename a partir do hash pra casar votos legacy (que usam "vid1"…)
    video_filename = None
    try:
        for v in (STORAGE / "videos").glob("*.mp4"):
            if sha256_arquivo(v) == h:
                video_filename = v.name
                break
    except OSError as e:
        log.warning("tier_a: nao consegui scan videos pra hash %s: %s", h[:12], e)
    res = filtrar_yolo_com_votos(detections, video_filename=video_filename, video_hash=h)

    suspeitos_total = res["suspeito"] + cv_susp
    stats = {**res["stats"], "cv_suspeitos": len(cv_susp)}

    if res["stats"]["confiavel"] == 0 and not suspeitos_total:
        return {
            **base,
            "veredito": "sem_candidatos",
            "motivo": "nenhum candidato confiável nem suspeito após filtros",
            "stats": stats,
            "candidatos_confiavel": [],
            "candidatos_suspeito": [],
        }

    return {
        **base,
        "veredito": "candidatos_para_revisao",
        "motivo": f"{res['stats']['confiavel']} confiáveis (yolo) + "
        f"{res['stats']['suspeito']} suspeitos (yolo) + "
        f"{len(cv_susp)} suspeitos (cv)",
        "stats": stats,
        "candidatos_confiavel": res["confiavel"],
        "candidatos_suspeito": suspeitos_total,
    }


def _infracoes_confirmadas_por_voto(hash_atual: str) -> list[dict]:
    """
    Lê storage/training/examples.jsonl e devolve as R1020-G-a marcadas como
    `approved + vote=S` para este hash — são infrações confirmadas pelo
    avaliador IA simbólico (ou humano via UI). Cada uma já vem com `motion`
    embutido na string evidencia.

    Deduplica por ts (±2s) — múltiplos votos no mesmo evento contam 1 só.
    """
    examples_path = STORAGE / "training" / "examples.jsonl"
    if not examples_path.exists():
        return []

    # Carrega TODOS os votos do hash + infracao em ordem cronológica.
    todos = []
    for line in examples_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            log.debug("tier_a: pulando linha invalida em examples.jsonl: %s", e)
            continue
        if rec.get("hash") != hash_atual:
            continue
        if rec.get("infracao_id") != "R1020-G-a":
            continue
        if rec.get("ts") is None:
            continue
        todos.append(rec)
    todos.sort(key=lambda r: (float(r.get("ts") or 0), r.get("saved_at") or ""))

    # Agrupa por proximidade temporal sem efeito de corrente.
    clusters: list[list[dict]] = []
    for rec in todos:
        ts = float(rec.get("ts") or 0)
        if not clusters:
            clusters.append([rec])
            continue
        last_cluster = clusters[-1]
        last_ts = float(last_cluster[-1].get("ts") or 0)
        if abs(ts - last_ts) <= 2.0:
            last_cluster.append(rec)
        else:
            clusters.append([rec])

    aprovadas: list[dict] = []
    for cluster in clusters:
        rec = max(cluster, key=lambda r: (r.get("saved_at") or "", float(r.get("ts") or 0)))
        if rec.get("decisao") != "approved" or rec.get("vote") != "S":
            continue
        infra = por_id("R1020-G-a")
        assert infra is not None, "taxonomia R1020-G-a deve existir"
        aprovadas.append(
            {
                "id": "R1020-G-a",
                "descricao": infra.descricao,
                "severidade": infra.severidade.value,
                "pontos": infra.pontos,
                "tier": infra.tier.value,
                "status": "infracao_confirmada",
                "ts": float(rec["ts"]),
                "frame_idx": rec.get("frame_idx"),
                "evidencia": rec.get("evidencia", ""),
                "voto_em": rec.get("saved_at"),
            }
        )
    aprovadas.sort(key=lambda x: x["ts"])
    return aprovadas


def _pendentes_tier_b() -> list[dict]:
    out = []
    for inf in por_tier(Tier.B):
        out.append(
            {
                "id": inf.id,
                "descricao": inf.descricao,
                "severidade": inf.severidade.value,
                "pontos": inf.pontos,
                "tier": "B",
                "status": "pendente_revisao_humana",
                "motivo": "varredura passiva — exige revisão humana com evidência inequívoca",
            }
        )
    return out


def _pendentes_tier_c() -> list[dict]:
    out = []
    for inf in por_tier(Tier.C):
        out.append(
            {
                "id": inf.id,
                "descricao": inf.descricao,
                "severidade": inf.severidade.value,
                "pontos": inf.pontos,
                "tier": "C",
                "status": StatusAvaliacao.PENDENTE_INFRAESTRUTURA.value,
                "infra_faltante": inf.infra_faltante,
                "requer_obd": inf.requer_obd,
            }
        )
    return out


def run(video_path: Path, force: bool = False) -> dict:
    t0 = time.time()
    video_path = video_path.resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    print(f"[1/5] hash de {video_path.name}")
    h = sha256_arquivo(video_path)
    analysis_dir = STORAGE / "analyses" / h
    analysis_dir.mkdir(parents=True, exist_ok=True)
    out_path = analysis_dir / "result.json"
    if out_path.exists() and not force:
        print(f"  result.json já existe ({h[:12]}…) — use --force para refazer.")
        return json.loads(out_path.read_text())

    print("[2/5] metadata grid")
    slicer = GridSlicer(video_path)
    meta = slicer.metadata()

    print("[3/5] cinto sampler (5 frames fixos, sem VLM em runtime)")
    cinto = _avaliar_cinto(video_path, analysis_dir)

    print("[4/5] sinal vertical via YOLO + filtros")
    sinal = _avaliar_sinal_vertical(analysis_dir)

    print("[5/5] montando result.json")
    tier_a_ids = ["R1020-G-a", "R1020-GR-f"]
    tier_b_ids = [i.id for i in por_tier(Tier.B)]
    tier_c_ids = [i.id for i in por_tier(Tier.C)]

    result = {
        "schema_version": "tier_a/0.1",
        "rubrica": Rubrica.RES_1020_2025.value,
        "video": {
            "filename": video_path.name,
            "path": str(video_path),
            "hash": h,
            "duration_s": meta["duration_s"],
            "fps": meta["fps"],
            "size": [meta["width"], meta["height"]],
            "layout": meta["layout"],
        },
        "escopo_avaliado": tier_a_ids + tier_b_ids,
        "escopo_pendente_infraestrutura": tier_c_ids,
        "infracoes_avaliadas": [sinal, cinto, *_pendentes_tier_b()],
        "infracoes_pendentes_infraestrutura": _pendentes_tier_c(),
        "infracoes_detectadas": _infracoes_confirmadas_por_voto(h),
        "elapsed_s": round(time.time() - t0, 2),
    }

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"  → {out_path.relative_to(ROOT)} ({result['elapsed_s']}s)")
    return result


def run_all(force: bool = False) -> list[dict]:
    videos = sorted((STORAGE / "videos").glob("*.mp4"))
    if not videos:
        raise SystemExit(f"Nenhum vídeo em {STORAGE / 'videos'}")
    out = []
    for v in videos:
        print(f"\n=== {v.name} ===")
        out.append(run(v, force=force))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "video", nargs="?", type=Path, help="Caminho do vídeo. Use --all para os 4 do dataset."
    )
    ap.add_argument(
        "--all", action="store_true", help="Processa todos os vídeos em storage/videos/"
    )
    ap.add_argument("--force", action="store_true", help="Refaz mesmo se result.json já existir")
    args = ap.parse_args()
    if args.all:
        run_all(force=args.force)
    elif args.video:
        run(args.video, force=args.force)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
