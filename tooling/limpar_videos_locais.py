#!/usr/bin/env python3
"""Limpeza RETROATIVA dos vídeos brutos locais de staging.

Contexto
--------
O `video.mp4` em ``storage/analyses/<hash>/`` é só STAGING do download
(TechPrático/S3 → disco local → upload GCS → análise lê do GCS via
``Part.from_uri``). A fonte canônica é o GCS
(``gs://<bucket>/uploads/<hash>/video.mp4``). Reter o local indefinidamente
encheu o disco ``/mnt/data`` (422G de resíduo). Este script varre
``storage/analyses/*/video.mp4`` (e ``*.mp4`` legados) e, para cada um:

  - PULA se o exame está em análise ativa (status ``running``/``uploading``
    e variantes) — nunca remove vídeo de exame em processamento.
  - Resolve o ``gs://`` do exame (upload.json/result.json) e verifica se o
    blob existe no GCS (``google.cloud.storage`` ``Blob.exists()``).
  - Se existe no GCS → remove o local (cópia descartável).
  - Se NÃO existe no GCS (404) OU não há ``gs_path`` → PRESERVA o local
    (pode ser a única cópia) e loga.

Modos
-----
- ``--dry-run`` (DEFAULT): só lista o que removeria e soma o espaço; não toca
  em disco.
- ``--apply``: executa as remoções.

Uso
---
    python tooling/limpar_videos_locais.py            # dry-run (default)
    python tooling/limpar_videos_locais.py --apply    # executa

O bucket vem de ``$GCS_BUCKET`` (default ``valbot-prod``); o diretório raiz de
``$VALBOT_ANALYSES_DIR`` ou ``<repo>/storage/analyses``. As credenciais GCS são
as ambientais padrão (ADC) — mesma do servidor.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Diretório de análises — mesma convenção do server (ANALYSES_DIR).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYSES_DIR = Path(
    os.environ.get("VALBOT_ANALYSES_DIR", str(PROJECT_ROOT / "storage" / "analyses"))
)
GCS_BUCKET = os.environ.get("GCS_BUCKET", "valbot-prod")

# Status que indicam exame em análise ATIVA / upload em curso — NUNCA remover.
ACTIVE_STATUSES = {"running", "processing", "analisando", "uploading"}


def _local_video_for(base: Path) -> Path | None:
    """Resolve o MP4 local de um exame (video.mp4 ou primeiro *.mp4 legado)."""
    local = base / "video.mp4"
    if local.exists() and local.is_file():
        return local
    if base.exists():
        for cand in sorted(base.glob("*.mp4")):
            if cand.is_file():
                return cand
    return None


def _status_of(base: Path) -> str:
    """Status do exame a partir do status.json local (debug/cache do server).

    Standalone: não consulta o DB. Em produção o status.json é escrito em todas
    as transições (uploading/running/processed/failed), então é suficiente para
    o guard de 'análise ativa'. 'unknown' quando ausente.
    """
    f = base / "status.json"
    if not f.exists():
        return "unknown"
    try:
        doc = json.loads(f.read_text())
        return str(doc.get("status") or "unknown").strip().lower()
    except Exception:
        return "unknown"


def _resolve_gs_uri(base: Path) -> str | None:
    """gs:// do vídeo via result.json/upload.json (mesma ordem do server)."""
    for name in ("result.json", "upload.json"):
        src = base / name
        if not src.exists():
            continue
        try:
            doc = json.loads(src.read_text())
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        v = doc.get("video") if isinstance(doc.get("video"), dict) else None
        gs = (v or {}).get("gs_uri") or (v or {}).get("gs_path") or doc.get("gs_path")
        if isinstance(gs, str) and gs.startswith("gs://"):
            return gs
    return None


def _gcs_blob_exists(client, gs_uri: str) -> bool:
    rest = gs_uri[len("gs://") :]
    bucket_name, _, blob_name = rest.partition("/")
    if not bucket_name or not blob_name:
        raise ValueError(f"gs_uri malformado: {gs_uri}")
    blob = client.bucket(bucket_name).blob(blob_name)
    return bool(blob.exists())


def _fmt_mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group()
    g.add_argument(
        "--dry-run",
        action="store_true",
        help="Só lista e soma o espaço (DEFAULT).",
    )
    g.add_argument(
        "--apply",
        action="store_true",
        help="Executa as remoções de fato.",
    )
    args = parser.parse_args(argv)
    apply = bool(args.apply)  # default: dry-run

    if not ANALYSES_DIR.exists():
        print(f"[limpar] diretório de análises não existe: {ANALYSES_DIR}")
        return 0

    print(
        f"[limpar] raiz={ANALYSES_DIR} bucket=gs://{GCS_BUCKET} modo={'APPLY' if apply else 'DRY-RUN'}"
    )

    # Lazy import do GCS — só quando há algo a verificar.
    client = None
    removidos = 0
    bytes_removidos = 0
    preservados_sem_gcs = 0
    preservados_ativos = 0
    erros = 0

    for base in sorted(ANALYSES_DIR.iterdir()):
        if not base.is_dir():
            continue
        local = _local_video_for(base)
        if local is None:
            continue
        hid = base.name
        status = _status_of(base)
        if status in ACTIVE_STATUSES:
            preservados_ativos += 1
            print(f"[skip ] {hid[:12]} status={status} — em análise ativa; preservado")
            continue

        gs_uri = _resolve_gs_uri(base)
        if not gs_uri:
            preservados_sem_gcs += 1
            print(f"[keep ] {hid[:12]} SEM gs_path — preservado (possível única cópia)")
            continue

        if client is None:
            from google.cloud import storage  # noqa: PLC0415

            client = storage.Client()

        try:
            exists = _gcs_blob_exists(client, gs_uri)
        except Exception as e:
            erros += 1
            print(f"[erro ] {hid[:12]} falha ao verificar GCS ({e}) — preservado")
            continue

        if not exists:
            preservados_sem_gcs += 1
            print(f"[keep ] {hid[:12]} blob AUSENTE no GCS ({gs_uri}) — preservado (única cópia)")
            continue

        try:
            size = local.stat().st_size
        except Exception:
            size = 0

        if apply:
            try:
                local.unlink()
            except Exception as e:
                erros += 1
                print(f"[erro ] {hid[:12]} unlink falhou ({e})")
                continue
            print(f"[del  ] {hid[:12]} removido {local.name} ({_fmt_mb(size)}) — GCS ok")
        else:
            print(f"[would] {hid[:12]} removeria {local.name} ({_fmt_mb(size)}) — GCS ok")

        removidos += 1
        bytes_removidos += size

    print("-" * 60)
    verbo = "Removidos" if apply else "Removeria"
    print(f"[limpar] {verbo}: {removidos} vídeo(s), {_fmt_mb(bytes_removidos)} liberados")
    print(f"[limpar] Preservados (em análise ativa): {preservados_ativos}")
    print(f"[limpar] Preservados (sem GCS / única cópia): {preservados_sem_gcs}")
    if erros:
        print(f"[limpar] Erros (preservados por segurança): {erros}")
    if not apply and removidos:
        print("[limpar] DRY-RUN — nada foi removido. Use --apply para executar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
