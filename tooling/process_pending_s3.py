"""
process_pending_s3.py — backfill de análises queued cujo vídeo está num S3 externo.

Cenário: o cliente Trânsito Prático/SE chama POST /api/exams/init-upload passando
`video_url=https://techpratico-stream-se-cache.s3.amazonaws.com/.../Camera_01.mp4`.
Como o vídeo já está num bucket S3 do cliente (privado), o fluxo padrão (upload
direto pro GCS via signed URL → finalize → _run_analysis) não dispara.

Este script:

    1) Varre storage/analyses/* procurando status="queued" com gs_path HTTPS S3
    2) Faz STREAM S3 → GCS via boto3 (StreamingBody) → blob.upload_from_file
       Bytes passam pela RAM do container, nunca tocam disco.
    3) Atualiza upload.json com o novo gs_path (gs://...)
    4) Chama analyze_video(gs_uri) — Gemini lê direto do GCS
    5) Escreve result.json + status.json=processed

Roda dentro do container valbot-api:

    docker exec -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY \
                -e AWS_REGION -e AWS_S3_BUCKET \
                valbot-api python /opt/valbot/tooling/process_pending_s3.py

Flags:
    --analysis-id <id>   Processa só um analysis_id específico
    --dry-run            Lista o que faria, sem chamar S3 nem Gemini
    --limit N            Processa no máximo N (default: todos)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

log = logging.getLogger("process_pending_s3")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


STORAGE_DIR = Path(os.getenv("VALBOT_STORAGE_DIR", "/opt/valbot/storage"))
ANALYSES_DIR = STORAGE_DIR / "analyses"
GCS_BUCKET = os.getenv("GCS_BUCKET", "valbot-prod")
GCS_PREFIX = os.getenv("GCS_UPLOAD_PREFIX", "uploads")

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "techpratico-stream-se-cache")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
# AWS_ACCESS_KEY_ID e AWS_SECRET_ACCESS_KEY já são lidos pelo boto3 do env.

# Hosts S3 conhecidos do cliente — filtro de quais URLs HTTPS processamos.
ALLOWED_S3_HOSTS = {
    "techpratico-stream-se-cache.s3.amazonaws.com",
    "techpratico-stream-se-cache.s3.us-east-1.amazonaws.com",
    f"{AWS_S3_BUCKET}.s3.amazonaws.com",
    f"{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com",
    "s3.amazonaws.com",
    f"s3.{AWS_REGION}.amazonaws.com",
}


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_status(out_dir: Path, status: str, **extra) -> None:
    payload = {"status": status, "updated_at": _iso_now()}
    payload.update(extra)
    (out_dir / "status.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def _render_pdf(out_dir: Path, result: dict, upload_meta: dict) -> None:
    """Renderiza laudo.pdf em `out_dir` — mesma lógica do _render_laudo_pdf
    do api_stub, replicada aqui pra evitar dependência de import circular.
    """
    from datetime import datetime as _dt

    from src.reporting.adapter import build_context
    from src.reporting.pdf import render_pdf

    detectadas = []
    for d in result.get("infracoes_detectadas", []) or []:
        ts = d.get("timestamp_s")
        if ts is None:
            ts = d.get("ts_seconds") or 0
        detectadas.append(
            {
                "id": d.get("id") or f"i{len(detectadas)}",
                "timestamp_inicio": float(ts or 0),
                "duracao_s": float(d.get("duracao_s") or 1.0),
                "evidencia": d.get("evidence") or d.get("evidencia") or "",
                "descricao_longa": d.get("evidence") or "",
                "occurrences": 1,
            }
        )

    candidato = dict(upload_meta.get("candidato", {}))
    candidato["veiculo"] = upload_meta.get("exame", {}).get("veiculo", "—")

    hash_short = (result.get("video", {}).get("hash") or "")[:8].upper() or "UNKNOWN"
    metadata = {
        "laudo_id": f"LAU-{hash_short}",
        "rubrica": "1020_2025",
        "video_hash": result.get("video", {}).get("hash", ""),
        "modelo_versao": result.get("engine", {}).get("model", "gemini-3.1-pro-preview"),
        "duracao_seg": float(result.get("video", {}).get("duration_s") or 240.0),
        "limite_pontuacao": 10,
        "local": upload_meta.get("exame", {}).get("local", "—"),
        "examinador": upload_meta.get("exame", {}).get("examinador", "—"),
        "data_exame": _dt.now().strftime("%d/%m/%Y"),
        "result_hash": hashlib.sha1(
            json.dumps(result, sort_keys=True, default=str).encode()
        ).hexdigest()[:12],
        "analysis_version": "valbot-vertex-v25",
    }

    ctx = build_context(detectadas, candidato, metadata)
    ctx_dict = dict(ctx)
    ctx_dict["contagem"] = {"eliminatoria": 0, **ctx_dict.get("contagem", {})}
    render_pdf(ctx_dict, out_dir / "laudo.pdf")


def parse_s3_url(url: str) -> tuple[str, str]:
    """Extrai (bucket, key) de uma URL S3 HTTPS.

    Aceita virtual-hosted (https://bucket.s3.region.amazonaws.com/key) e
    path-style (https://s3.region.amazonaws.com/bucket/key). Faz unquote da
    key (caso venha com %20 etc).
    """
    p = urlparse(url)
    host = p.hostname or ""
    path = p.path.lstrip("/")

    if host.endswith(".amazonaws.com"):
        parts = host.split(".")
        # virtual-hosted: bucket.s3[.region].amazonaws.com
        if (
            len(parts) >= 4
            and parts[-3].startswith("s3")
            and parts[-2] == "amazonaws"
            and parts[-1] == "com"
        ):
            bucket = parts[0]
            key = path
        # virtual-hosted curto: bucket.s3.amazonaws.com
        elif (
            len(parts) >= 3
            and parts[-3] == "s3"
            and parts[-2] == "amazonaws"
            and parts[-1] == "com"
        ):
            bucket = ".".join(parts[:-3])
            key = path
        # path-style: s3[.region].amazonaws.com/bucket/key
        elif parts[0].startswith("s3"):
            bucket, _, key = path.partition("/")
        else:
            raise ValueError(f"host S3 não reconhecido: {host}")
    else:
        raise ValueError(f"URL não parece S3: {url}")

    return bucket, unquote(key)


def stream_s3_to_gcs(s3_url: str, analysis_id: str) -> tuple[str, int]:
    """Stream do objeto S3 → GCS sem tocar disco.

    Devolve (gs_uri, size_bytes) — o caller persiste o tamanho no upload.json.
    """
    import boto3
    from botocore.config import Config
    from google.cloud import storage  # type: ignore[import-not-found]

    bucket, key = parse_s3_url(s3_url)
    log.info("S3 GET bucket=%s key=%s", bucket, key[:80])

    s3 = boto3.client(
        "s3",
        region_name=AWS_REGION,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"]  # StreamingBody — file-like, suporta read()
    size_bytes = int(obj.get("ContentLength", 0) or 0)
    size_mb = size_bytes / (1024 * 1024)
    log.info("S3 OK size=%.1fMB content_type=%s", size_mb, obj.get("ContentType"))

    gcs = storage.Client()
    blob_name = f"{GCS_PREFIX}/{analysis_id}/video.mp4"
    blob = gcs.bucket(GCS_BUCKET).blob(blob_name)

    log.info("GCS PUT gs://%s/%s", GCS_BUCKET, blob_name)
    t0 = time.monotonic()
    # upload_from_file lê em chunks; StreamingBody implementa .read(size).
    # Bytes nunca encostam no disco — só passam pela RAM em buffers.
    blob.upload_from_file(body, content_type="video/mp4", rewind=False, size=size_bytes or None)
    elapsed = time.monotonic() - t0
    log.info("GCS OK %.1fMB em %.1fs (%.1f MB/s)", size_mb, elapsed, size_mb / max(elapsed, 0.01))

    return f"gs://{GCS_BUCKET}/{blob_name}", size_bytes


_S3_PATH_CATEGORIA_RE = re.compile(
    r"/(ACC|AB|AC|AD|AE|[A-E])/[A-Z]{2}\d{4,}",
    re.IGNORECASE,
)


def parse_categoria_from_s3_path(s3_path: str) -> str:
    """Extrai categoria CNH do path original do S3.

    Padrão tecpratico: `s3://.../YYYYMMDD/HHMM/<CAT>/<RENACH>_*.mp4`.
    """
    if not s3_path:
        return ""
    m = _S3_PATH_CATEGORIA_RE.search(s3_path)
    return m.group(1).upper() if m else ""


def warm_local_cache_from_gcs(analysis_id: str, gs_uri: str) -> bool:
    """Baixa o blob do GCS pro disco local em `storage/analyses/{id}/video.mp4`.

    Idempotente: se já existe, retorna True sem baixar. Erros não propagam —
    warm é best-effort e a UI ainda funciona via stream do GCS se falhar.
    """
    from google.cloud import storage  # type: ignore[import-not-found]

    local = ANALYSES_DIR / analysis_id / "video.mp4"
    if local.exists() and local.stat().st_size > 0:
        return True
    if not gs_uri.startswith("gs://"):
        log.warning("[%s] warm: gs_uri invalido %s", analysis_id[:12], gs_uri)
        return False
    rest = gs_uri[len("gs://") :]
    bucket_name, _, blob_name = rest.partition("/")
    if not bucket_name or not blob_name:
        log.warning("[%s] warm: gs_uri malformado %s", analysis_id[:12], gs_uri)
        return False
    try:
        gcs = storage.Client()
        blob = gcs.bucket(bucket_name).blob(blob_name)
        local.parent.mkdir(parents=True, exist_ok=True)
        tmp = local.with_suffix(".mp4.partial")
        t0 = time.monotonic()
        blob.download_to_filename(str(tmp))
        tmp.rename(local)
        size_mb = local.stat().st_size / (1024 * 1024)
        elapsed = time.monotonic() - t0
        log.info(
            "[%s] warm OK %.1fMB em %.1fs (%.1f MB/s)",
            analysis_id[:12],
            size_mb,
            elapsed,
            size_mb / max(elapsed, 0.01),
        )
        return True
    except Exception as e:
        log.warning("[%s] warm FALHOU: %s", analysis_id[:12], e)
        # Limpa partial se ficou pra trás
        tmp = local.with_suffix(".mp4.partial")
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
        return False


def enrich_upload_metadata(analysis_id: str) -> bool:
    """Popula campos derivaveis no upload.json (size_mb, categoria, duration).

    Chamado tanto durante o processamento (após stream) quanto no backfill.
    Idempotente — só preenche campos vazios; nunca sobrescreve dado humano.
    Devolve True se gravou mudanças.
    """
    out_dir = ANALYSES_DIR / analysis_id
    upload_path = out_dir / "upload.json"
    if not upload_path.exists():
        return False
    try:
        upload = json.loads(upload_path.read_text())
    except Exception:
        return False
    changed = False
    video = upload.setdefault("video", {})
    candidato = upload.setdefault("candidato", {})

    # 1) size_mb / size_bytes — prioridade stat local > result.video.size
    if not video.get("size_mb") or not video.get("size_bytes"):
        local = out_dir / "video.mp4"
        size_bytes = None
        if local.exists() and local.stat().st_size > 0:
            size_bytes = local.stat().st_size
        else:
            result_path = out_dir / "result.json"
            if result_path.exists():
                try:
                    rv = json.loads(result_path.read_text()).get("video") or {}
                    if isinstance(rv.get("size"), (int, float)) and rv["size"] > 0:
                        size_bytes = int(rv["size"])
                except Exception:
                    pass
        if size_bytes:
            video["size_bytes"] = size_bytes
            video["size_mb"] = round(size_bytes / (1024 * 1024), 2)
            changed = True

    # 2) categoria CNH — parse do path S3 quando upload veio sem
    if not candidato.get("categoria"):
        s3_path = video.get("gs_path_original_s3") or ""
        cat = parse_categoria_from_s3_path(s3_path)
        if cat:
            candidato["categoria"] = cat
            changed = True

    # 3) duration_s — do result.json se disponível
    if not video.get("duration_s"):
        result_path = out_dir / "result.json"
        if result_path.exists():
            try:
                dur = (json.loads(result_path.read_text()).get("video") or {}).get("duration_s")
                if isinstance(dur, (int, float)) and dur > 0:
                    video["duration_s"] = float(dur)
                    changed = True
            except Exception:
                pass

    if changed:
        upload_path.write_text(json.dumps(upload, indent=2, ensure_ascii=False))
    return changed


def process_one(analysis_id: str, dry_run: bool = False) -> bool:
    out_dir = ANALYSES_DIR / analysis_id
    upload_path = out_dir / "upload.json"
    if not upload_path.exists():
        log.error("[%s] upload.json não encontrado", analysis_id[:12])
        return False

    upload_meta = json.loads(upload_path.read_text())
    video_meta = upload_meta.get("video") or {}
    current_path = video_meta.get("gs_path") or ""
    original_s3 = video_meta.get("gs_path_original_s3")
    # Se já foi streamado (re-run após falha): pula S3 e usa o gs:// existente.
    already_streamed = current_path.startswith("gs://")
    s3_url = original_s3 if already_streamed else current_path

    if not already_streamed:
        if not s3_url.startswith("http"):
            log.warning("[%s] gs_path não é HTTPS, ignorando (%s)", analysis_id[:12], s3_url[:60])
            return False
        host = urlparse(s3_url).hostname or ""
        if host not in ALLOWED_S3_HOSTS:
            log.warning("[%s] host não autorizado: %s", analysis_id[:12], host)
            return False

    if dry_run:
        log.info("[%s] DRY-RUN: streamaria de %s", analysis_id[:12], (s3_url or current_path)[:100])
        return True

    rubrica_slug = (upload_meta.get("exame") or {}).get("rubrica", "1020/2025")

    try:
        if already_streamed:
            gs_uri = current_path
            log.info("[%s] já streamado, reusando %s", analysis_id[:12], gs_uri)
        else:
            _write_status(out_dir, "streaming_s3")
            gs_uri, size_bytes = stream_s3_to_gcs(s3_url, analysis_id)
            # Atualiza upload.json com path canônico + size + categoria.
            upload_meta.setdefault("video", {})
            upload_meta["video"]["gs_path_original_s3"] = s3_url
            upload_meta["video"]["gs_path"] = gs_uri
            upload_meta["video"]["streamed_at"] = _iso_now()
            if size_bytes > 0:
                upload_meta["video"]["size_bytes"] = size_bytes
                upload_meta["video"]["size_mb"] = round(size_bytes / (1024 * 1024), 2)
            cat = parse_categoria_from_s3_path(s3_url)
            if cat and not (upload_meta.get("candidato") or {}).get("categoria"):
                upload_meta.setdefault("candidato", {})["categoria"] = cat
            upload_path.write_text(json.dumps(upload_meta, indent=2, ensure_ascii=False))
            # Warm local cache em background — pra 1a request da UI servir
            # direto do disco sem 1 round-trip GCS. Best-effort.
            threading.Thread(
                target=warm_local_cache_from_gcs,
                args=(analysis_id, gs_uri),
                daemon=True,
                name=f"warm-{analysis_id[:8]}",
            ).start()

        _write_status(out_dir, "running")
        log.info("[%s] chamando Gemini com %s", analysis_id[:12], gs_uri)

        # Preset explícito via env — default já aponta pro preset valbot oficial.
        preset = os.getenv("VALBOT_PRESET", "v25/valbot-r1-vip-v25")
        # max_output_tokens default Gemini é 8192 — vídeos longos com muitas
        # infrações estouravam e devolviam JSON truncado. Bumpando pra 16384.
        max_out = int(os.getenv("VALBOT_MAX_OUTPUT_TOKENS", "16384"))
        from src.analysis.gemini_analyzer import AnalysisOptions, analyze_video

        # Repassa training_annotations do examinador presencial pro analyzer.
        # Vai virar bloco "ANOTAÇÕES DE REFERÊNCIA" no user_prompt — modelo
        # verifica cada timestamp com independência (não copia cego).
        train_anns = upload_meta.get("training_annotations") or []
        # Categoria do candidato (A/B/C/D/E) — extraída por insert_exam ou
        # presente direto no upload_meta. Quando setada + flag VALBOT_USE_
        # MODULAR_V26=1, ativa o pipeline 2-fase (discovery Flash + composer
        # v26). Default = pipeline v25 monolítico (rollout gradual).
        categoria = (upload_meta.get("candidato") or {}).get("categoria") or None
        use_modular_v26 = os.getenv("VALBOT_USE_MODULAR_V26", "0") == "1"
        result = analyze_video(
            gs_uri,
            rubrica_slug=rubrica_slug,
            options=AnalysisOptions(
                rubrica_slug=rubrica_slug,
                preset=preset,
                max_output_tokens=max_out,
                training_annotations=train_anns,
                categoria=categoria,
                use_modular_v26=use_modular_v26,
            ),
        )

        # Enriquecer com metadados do upload (mesma lógica do _run_analysis).
        result.setdefault("video", {})
        result["video"]["hash"] = upload_meta.get("video", {}).get("hash") or analysis_id
        result["video"]["filename"] = "video.mp4"
        result["video"]["gs_path"] = gs_uri
        result["exam"] = upload_meta.get("exame", {})
        result["candidato"] = upload_meta.get("candidato", {})
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=str)
        )

        # Enriquece upload.json com duration_s + qq fallback que dependia
        # do result.json (chamado APÓS o write_text de result.json acima).
        try:
            enrich_upload_metadata(analysis_id)
        except Exception as e:
            log.warning("[%s] enrich pos-result falhou: %s", analysis_id[:12], e)

        cost = result.get("cost") or {}

        # F2 — DUAL-WRITE: persiste resultado completo no Postgres.
        # File-based continua autoritativo até F4/F5 (DB é shadow).
        # Erros aqui não derrubam o pipeline — file ainda tá no disco.
        try:
            from tooling.api_stub import db as _db

            _db.update_result(hash_=analysis_id, result=result, cost=cost, upload_meta=upload_meta)
            infracoes_raw = result.get("infracoes_detectadas") or []
            if infracoes_raw:
                _db.upsert_infractions(hash_=analysis_id, infracoes=infracoes_raw)
            # size_bytes — usar stat do disco se warm já rodou
            local = ANALYSES_DIR / analysis_id / "video.mp4"
            if local.exists() and local.stat().st_size > 0:
                _db.update_size_and_paths(
                    hash_=analysis_id,
                    size_bytes=local.stat().st_size,
                )
        except Exception as e:
            log.warning("[%s] db dual-write falhou (file ok, segue): %s", analysis_id[:12], e)

        # Renderiza PDF (mesma lógica do _run_analysis no api_stub).
        pdf_ok = False
        pdf_err = None
        try:
            _render_pdf(out_dir, result, upload_meta)
            pdf_ok = True
            log.info("[%s] PDF renderizado em %s", analysis_id[:12], out_dir / "laudo.pdf")
        except Exception as e:
            pdf_err = str(e)
            log.exception("[%s] falha ao renderizar PDF: %s", analysis_id[:12], e)

        status_extra = dict(
            pontuacao_total=result.get("pontuacao_total"),
            aprovado=result.get("aprovado"),
            cost_usd=cost.get("usd"),
            tokens_in=cost.get("prompt_tokens"),
            tokens_out=cost.get("output_tokens"),
            gemini_elapsed_s=cost.get("elapsed_s"),
            has_pdf=pdf_ok,
        )
        if pdf_err:
            status_extra["pdf_error"] = pdf_err[:300]
        final_status = "processed" if pdf_ok else "processed_no_pdf"
        _write_status(out_dir, final_status, **status_extra)

        # F2 — propaga status final pro DB (dispara trigger que loga em exam_events
        # automaticamente). Best-effort.
        try:
            from tooling.api_stub import db as _db

            pdf_path_str = str(out_dir / "laudo.pdf") if pdf_ok else None
            _db.update_status(
                analysis_id, final_status, pdf_path=pdf_path_str
            ) if pdf_path_str else _db.update_status(analysis_id, final_status)
        except Exception as e:
            log.warning("[%s] db.update_status pos-PDF falhou: %s", analysis_id[:12], e)

        log.info(
            "[%s] OK pontos=%s aprovado=%s custo=$%s pdf=%s",
            analysis_id[:12],
            result.get("pontuacao_total"),
            result.get("aprovado"),
            cost.get("usd"),
            "✓" if pdf_ok else "✗",
        )
        return True

    except Exception as e:
        log.exception("[%s] FALHOU: %s", analysis_id[:12], e)
        _write_status(
            out_dir,
            "failed",
            error=str(e),
            traceback=traceback.format_exc()[-2000:],
        )
        try:
            from tooling.api_stub import db as _db

            _db.update_status(analysis_id, "failed", error=str(e)[:500])
        except Exception as _dbe:
            log.warning("[%s] db.update_status(failed) falhou: %s", analysis_id[:12], _dbe)
        return False


def list_pending() -> list[str]:
    """Lista analysis_ids com status=queued cujo vídeo veio de S3 autorizado
    (ou já foi streamado uma vez — caso de re-run, `gs_path_original_s3` existe).
    """
    pending = []
    for d in sorted(ANALYSES_DIR.iterdir()):
        if not d.is_dir():
            continue
        status_file = d / "status.json"
        upload_file = d / "upload.json"
        if not status_file.exists() or not upload_file.exists():
            continue
        try:
            status = json.loads(status_file.read_text()).get("status")
            if status != "queued":
                continue
            video_meta = json.loads(upload_file.read_text()).get("video") or {}
            # Aceita: gs_path HTTPS S3 (primeiro processamento)
            #     OU: gs_path_original_s3 preservado (re-run, já streamado pra GCS)
            s3_url = video_meta.get("gs_path") or ""
            if not s3_url.startswith("http"):
                s3_url = video_meta.get("gs_path_original_s3") or ""
            if not s3_url.startswith("http"):
                continue
            host = urlparse(s3_url).hostname or ""
            if host in ALLOWED_S3_HOSTS:
                pending.append(d.name)
        except Exception:
            continue
    return pending


def list_streamed() -> list[str]:
    """Análises com gs_path já apontando pro GCS (qualquer status).
    Usado pelo modo --backfill pra enriquecer/warm o que já foi streamado."""
    ids = []
    for d in sorted(ANALYSES_DIR.iterdir()):
        if not d.is_dir():
            continue
        upload_file = d / "upload.json"
        if not upload_file.exists():
            continue
        try:
            upload = json.loads(upload_file.read_text())
            gs = (upload.get("video") or {}).get("gs_path") or ""
            if gs.startswith("gs://"):
                ids.append(d.name)
        except Exception:
            continue
    return ids


def reset_derivatives_files(analysis_id: str) -> dict[str, bool]:
    """COFRE-SAFE: apaga só os arquivos DERIVADOS da análise.

    REMOVE:
      - result.json   (laudo gerado pela Gemini)
      - status.json   (estado do pipeline — vai voltar pra 'queued' no DB)
      - laudo.pdf     (PDF renderizado a partir do result)
      - laudo.html    (HTML intermediário do WeasyPrint)

    PRESERVA (cofre — vem do integrador via init-upload):
      - upload.json   (candidato, exame, gs_path_original_s3 — IMUTÁVEL)
      - video.mp4     (cache local do vídeo — não regerar à toa)
      - qualquer .json/.bin custom

    Retorna dict com quais arquivos foram removidos.
    """
    out_dir = ANALYSES_DIR / analysis_id
    removed = {"result": False, "status": False, "pdf": False, "html": False}
    if not out_dir.exists():
        return removed
    for name, key in (
        ("result.json", "result"),
        ("status.json", "status"),
        ("laudo.pdf", "pdf"),
        ("laudo.html", "html"),
    ):
        f = out_dir / name
        if f.exists():
            try:
                f.unlink()
                removed[key] = True
            except Exception as e:
                log.warning("[%s] unlink %s falhou: %s", analysis_id[:12], name, e)
    return removed


def reset_one_for_reprocess(analysis_id: str) -> dict[str, Any]:
    """COFRE-SAFE: reseta um exame pra reprocessamento.

    Não toca em:
      - upload.json local (cofre dos dados de integração)
      - video.mp4 local (cache do vídeo)
      - exams.{candidato_*, renach, processo, categoria, veiculo, examinador,
               auto_escola, local_unidade, rubrica, gs_video, training_annotations}
        (cofre no DB)
    """
    try:
        from tooling.api_stub import db as _db

        db_reset = _db.reset_exam_derivatives(analysis_id, new_status="queued")
    except Exception as e:
        log.warning("[%s] db reset falhou: %s", analysis_id[:12], e)
        db_reset = False
    files = reset_derivatives_files(analysis_id)
    log.info(
        "[%s] reset: db=%s files=%s",
        analysis_id[:12],
        db_reset,
        ",".join(f"{k}" for k, v in files.items() if v) or "—",
    )
    return {"db_reset": db_reset, "files_removed": files}


def db_backfill_one(analysis_id: str) -> dict[str, bool]:
    """F3 — Backfill: lê arquivos da análise e popula DB retroativamente.

    Não toca GCS, não baixa vídeo, não chama Gemini. Só lê
    upload.json+result.json+status.json e replica no DB.

    Idempotente: ON CONFLICT do INSERT e UPDATE-com-COALESCE garantem que
    rodar 2× não cria duplicatas nem perde dados.
    """
    out_dir = ANALYSES_DIR / analysis_id
    upload_path = out_dir / "upload.json"
    result_path = out_dir / "result.json"
    status_path = out_dir / "status.json"
    if not upload_path.exists():
        log.warning("[%s] db-backfill: sem upload.json", analysis_id[:12])
        return {"exam": False, "result": False, "infractions": False, "status": False}

    try:
        from tooling.api_stub import db as _db
    except Exception as e:
        log.error("db-backfill: import db falhou: %s", e)
        return {"exam": False, "result": False, "infractions": False, "status": False}

    out = {"exam": False, "result": False, "infractions": False, "status": False}

    try:
        upload = json.loads(upload_path.read_text())
    except Exception as e:
        log.warning("[%s] db-backfill: upload.json invalido: %s", analysis_id[:12], e)
        return out

    # Categoria CNH — enriquece in-memory antes do INSERT (parse do gs_path_original_s3
    # pra uploads antigos do tecpratico stream onde candidato.categoria veio "")
    upload.setdefault("candidato", {})
    if not upload["candidato"].get("categoria"):
        s3_path = (upload.get("video") or {}).get("gs_path_original_s3") or ""
        cat = parse_categoria_from_s3_path(s3_path)
        if cat:
            upload["candidato"]["categoria"] = cat

    # 1) INSERT exam (ON CONFLICT atualiza minimamente — preserva DB existente)
    try:
        _db.insert_exam(
            analysis_id=analysis_id,
            hash_=analysis_id,
            upload_meta=upload,
            gs_path=(upload.get("video") or {}).get("gs_path") or "",
            external_id=upload.get("external_id"),
            initial_status=(
                json.loads(status_path.read_text()).get("status")
                if status_path.exists()
                else "queued"
            ),
        )
        out["exam"] = True
    except Exception as e:
        log.warning("[%s] db-backfill: insert_exam falhou: %s", analysis_id[:12], e)

    # 2) update_result (se tem result.json)
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text())
            _db.update_result(analysis_id, result, cost=result.get("cost"))
            out["result"] = True
            # 3) Infrações filhas
            infs = result.get("infracoes_detectadas") or []
            if infs:
                _db.upsert_infractions(analysis_id, infs)
                out["infractions"] = True
        except Exception as e:
            log.warning("[%s] db-backfill: result falhou: %s", analysis_id[:12], e)

    # 4) Status final (vindo do status.json)
    if status_path.exists():
        try:
            st = json.loads(status_path.read_text())
            status_str = st.get("status")
            if status_str:
                _db.update_status(analysis_id, status_str)
                out["status"] = True
        except Exception as e:
            log.warning("[%s] db-backfill: status falhou: %s", analysis_id[:12], e)

    # 5) size_bytes do disco se tiver
    local = out_dir / "video.mp4"
    if local.exists() and local.stat().st_size > 0:
        try:
            _db.update_size_and_paths(analysis_id, size_bytes=local.stat().st_size)
        except Exception as e:
            log.warning("[%s] db-backfill: size update falhou: %s", analysis_id[:12], e)

    log.info(
        "[%s] db-backfill %s",
        analysis_id[:12],
        ",".join(f"{k}={'✓' if v else '✗'}" for k, v in out.items()),
    )
    return out


def backfill_one(analysis_id: str, warm: bool = True) -> tuple[bool, bool]:
    """Enriquece upload.json + warm local. Retorna (enriched, warmed)."""
    out_dir = ANALYSES_DIR / analysis_id
    upload_path = out_dir / "upload.json"
    if not upload_path.exists():
        log.warning("[%s] upload.json ausente", analysis_id[:12])
        return False, False
    enriched = enrich_upload_metadata(analysis_id)
    warmed = False
    if warm:
        try:
            upload = json.loads(upload_path.read_text())
            gs = (upload.get("video") or {}).get("gs_path") or ""
            if gs.startswith("gs://"):
                warmed = warm_local_cache_from_gcs(analysis_id, gs)
        except Exception as e:
            log.warning("[%s] backfill warm falhou: %s", analysis_id[:12], e)
    # Reroda enrich pós-warm pra capturar size_mb do stat fresco
    if warmed:
        enrich_upload_metadata(analysis_id)
    log.info(
        "[%s] backfill enriched=%s warmed=%s",
        analysis_id[:12],
        enriched,
        warmed,
    )
    return enriched, warmed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analysis-id", help="processa só esse analysis_id")
    ap.add_argument("--dry-run", action="store_true", help="lista sem processar")
    ap.add_argument("--limit", type=int, default=0, help="processa no máximo N (0=todos)")
    ap.add_argument(
        "--backfill",
        action="store_true",
        help="enriquece upload.json + warm local nas análises já streamadas (NÃO chama Gemini)",
    )
    ap.add_argument(
        "--no-warm",
        action="store_true",
        help="(--backfill) pula o download do GCS, só enriquece metadados",
    )
    ap.add_argument(
        "--db-backfill",
        action="store_true",
        help="F3 — popula DB lendo upload.json/result.json/status.json de cada análise. NÃO toca GCS/Gemini.",
    )
    ap.add_argument(
        "--reprocess-all",
        action="store_true",
        help="COFRE-SAFE: apaga DERIVADOS de TODOS os exames (result.json/status.json/laudo.* e colunas computadas no DB) e re-roda Gemini via process_one. Preserva upload.json e dados de integração.",
    )
    ap.add_argument(
        "--reset-only",
        action="store_true",
        help="(usa com --reprocess-all) só reseta sem reprocessar. Util pra dry-run.",
    )
    ap.add_argument(
        "--yes", action="store_true", help="(--reprocess-all) pula confirmação interativa"
    )
    args = ap.parse_args()

    # --backfill/--db-backfill/--reset-only não precisam de AWS creds
    # (não tocam S3). --reprocess-all também não precisa: vídeos já estão
    # no GCS (gs_path setado), o stream pra GCS só roda em primeiro upload.
    # process_one detecta already_streamed e pula o S3 nesse caso.
    skip_creds = args.backfill or args.db_backfill or args.reset_only or args.reprocess_all
    if not skip_creds:
        if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
            log.error("AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY ausentes no env")
            return 2

    if args.reprocess_all:
        # Lista todas as análises que TÊM um upload.json (cofre)
        if args.analysis_id:
            ids = [args.analysis_id]
        else:
            ids = []
            for d in sorted(ANALYSES_DIR.iterdir()):
                if d.is_dir() and (d / "upload.json").exists():
                    ids.append(d.name)
            if args.limit:
                ids = ids[: args.limit]

        log.info("REPROCESS-ALL: %d exames serão resetados", len(ids))
        if not args.yes:
            log.warning("(passe --yes pra confirmar; abortando dry-run)")
            for aid in ids[:10]:
                log.info("  - %s", aid[:12])
            if len(ids) > 10:
                log.info("  ... +%d", len(ids) - 10)
            return 0

        # FASE 1: reset (cofre-safe — preserva upload.json e dados de integração)
        log.info("FASE 1: resetando derivados (cofre preservado)")
        n_reset = 0
        for aid in ids:
            r = reset_one_for_reprocess(aid)
            if r["db_reset"]:
                n_reset += 1
        log.info("reset OK: %d/%d", n_reset, len(ids))

        if args.reset_only:
            log.info("--reset-only: parando aqui (sem chamar Gemini)")
            return 0

        # FASE 2: reprocesso via process_one (vai usar gs_path já streamado)
        log.info("FASE 2: chamando Gemini pra %d exames", len(ids))
        ok = fail = 0
        for aid in ids:
            if process_one(aid, dry_run=False):
                ok += 1
            else:
                fail += 1
        log.info("FIM reprocess-all ok=%d fail=%d total=%d", ok, fail, len(ids))
        return 0 if fail == 0 else 1

    if args.db_backfill:
        if args.analysis_id:
            ids = [args.analysis_id]
        else:
            # Todas as analises com upload.json (qualquer status)
            ids = []
            for d in sorted(ANALYSES_DIR.iterdir()):
                if d.is_dir() and (d / "upload.json").exists():
                    ids.append(d.name)
            log.info("db-backfill: encontrei %d análises com upload.json", len(ids))
            if args.limit:
                ids = ids[: args.limit]
                log.info("limitando a %d", len(ids))
        n_exam = n_result = n_inf = n_status = 0
        for aid in ids:
            r = db_backfill_one(aid)
            n_exam += 1 if r["exam"] else 0
            n_result += 1 if r["result"] else 0
            n_inf += 1 if r["infractions"] else 0
            n_status += 1 if r["status"] else 0
        log.info(
            "FIM db-backfill exams=%d result=%d infractions=%d status=%d total=%d",
            n_exam,
            n_result,
            n_inf,
            n_status,
            len(ids),
        )
        return 0

    if args.backfill:
        if args.analysis_id:
            ids = [args.analysis_id]
        else:
            ids = list_streamed()
            log.info("backfill: encontrei %d análises já streamadas", len(ids))
            if args.limit:
                ids = ids[: args.limit]
                log.info("limitando a %d", len(ids))
        enriched_n = warmed_n = 0
        for aid in ids:
            e, w = backfill_one(aid, warm=not args.no_warm)
            enriched_n += 1 if e else 0
            warmed_n += 1 if w else 0
        log.info(
            "FIM backfill enriched=%d warmed=%d total=%d",
            enriched_n,
            warmed_n,
            len(ids),
        )
        return 0

    if args.analysis_id:
        ids = [args.analysis_id]
    else:
        ids = list_pending()
        log.info("encontrei %d análises queued com URL S3", len(ids))
        if args.limit:
            ids = ids[: args.limit]
            log.info("limitando a %d", len(ids))

    ok = 0
    fail = 0
    for aid in ids:
        if process_one(aid, dry_run=args.dry_run):
            ok += 1
        else:
            fail += 1

    log.info("FIM ok=%d fail=%d total=%d", ok, fail, len(ids))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
