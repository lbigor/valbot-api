#!/usr/bin/env python3
"""
Política de retenção dos vídeos (.mp4) do Valbot.

CONTEXTO
--------
O disco de dados (/dev/sdb -> /mnt/data) hospeda tanto o Postgres quanto o
volume de storage. Os vídeos brutos das análises (video.mp4) são ~98% do uso
e já são guardados no GCS (coluna exams.gs_video = gs://valbot-prod/uploads/
<hash>/video.mp4). O endpoint /api/exams/<id>/video re-baixa o vídeo do GCS
sob demanda quando o arquivo local não existe (server.py:1379-1406). Logo, o
video.mp4 local é CACHE descartável: removê-lo é reversível.

O QUE FAZ
---------
Remove o video.mp4 local de análises concluídas e antigas, SOMENTE quando o
backup no GCS está confirmado. Mantém laudo.pdf/.html, result.json,
status.json e upload.json (juntos < 50 KB por análise) intactos -- só o vídeo
é descartado.

TRAVAS DE SEGURANÇA (todas precisam passar p/ apagar)
-----------------------------------------------------
  1. Backup GCS confirmado:
       - exams.gs_video preenchido (fonte de verdade no banco), E
       - (default) o objeto realmente existe no GCS  -> `gcloud storage`.
     Sem prova de backup, NUNCA apaga.
  2. Status terminal: status IN ('processed','failed'). Nunca toca em
     'running'/'queued' (processamento ativo).
  3. Grace period: mtime do video.mp4 mais velho que --days (default 7).

Órfãos (pasta no disco sem linha no banco) só são considerados com
--include-orphans, e mesmo assim exigem gs_path nos JSONs locais + verificação
no GCS. Por padrão são ignorados (logados como skip).

USO
---
  # Dry-run (não apaga nada, só mostra o que faria) -- DEFAULT
  python3 video_retention.py --days 7

  # Apaga de verdade
  python3 video_retention.py --days 7 --apply

  # Inclui órfãos (exige backup GCS comprovado mesmo assim)
  python3 video_retention.py --days 7 --apply --include-orphans

  # Pula a verificação online no GCS (confia só no gs_video do banco) -- mais rápido
  python3 video_retention.py --days 7 --apply --no-verify-gcs
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field

ANALYSES_DIR = os.environ.get(
    "VALBOT_ANALYSES_DIR",
    "/mnt/data/docker-volumes/valbot-deploy_valbot-storage/_data/analyses",
)
PG_CONTAINER = os.environ.get("VALBOT_PG_CONTAINER", "valbot-postgres")
PG_USER = os.environ.get("VALBOT_PG_USER", "valbot")
PG_DB = os.environ.get("VALBOT_PG_DB", "valbot")

TERMINAL_STATUS = {"processed", "failed"}


@dataclass
class Stats:
    deleted: int = 0
    freed_bytes: int = 0
    skip_reasons: dict = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1


def log(msg: str) -> None:
    print(f"[retention] {msg}", flush=True)


def load_db_index() -> dict[str, dict]:
    """hash -> {status, gs_video} a partir do Postgres (via docker exec psql)."""
    sql = "SELECT hash, COALESCE(status,''), COALESCE(gs_video,'') FROM exams"
    cmd = [
        "sudo",
        "docker",
        "exec",
        PG_CONTAINER,
        "psql",
        "-U",
        PG_USER,
        "-d",
        PG_DB,
        "-tAF",
        "\x1f",
        "-c",
        sql,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        log(f"ERRO consultando o banco: {e.stderr.strip()}")
        sys.exit(2)
    index: dict[str, dict] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) < 3:
            continue
        h, status, gs_video = parts[0], parts[1], parts[2]
        index[h] = {"status": status, "gs_video": gs_video}
    return index


def gs_uri_from_local(folder: str) -> str | None:
    """Procura gs:// nos JSONs locais (upload.json / result.json)."""
    for name in ("upload.json", "result.json"):
        p = os.path.join(folder, name)
        if not os.path.isfile(p):
            continue
        try:
            doc = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        v = doc.get("video") if isinstance(doc, dict) else None
        uri = (v or {}).get("gs_uri") or (v or {}).get("gs_path") or doc.get("gs_path")
        if isinstance(uri, str) and uri.startswith("gs://"):
            return uri
    return None


def gcs_object_exists(gs_uri: str) -> bool:
    """True se o objeto existe no GCS. Usa o gcloud SDK do host."""
    cmd = ["gcloud", "storage", "objects", "describe", gs_uri, "--format=value(name)"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.returncode == 0 and bool(r.stdout.strip())
    except FileNotFoundError:
        log("AVISO: gcloud não encontrado no host; não dá pra verificar o GCS.")
        return False


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> int:
    ap = argparse.ArgumentParser(description="Retenção de vídeos do Valbot")
    ap.add_argument("--days", type=int, default=7, help="grace period em dias (default 7)")
    ap.add_argument("--apply", action="store_true", help="apaga de verdade (default: dry-run)")
    ap.add_argument(
        "--include-orphans",
        action="store_true",
        help="considera pastas sem registro no banco (exige backup GCS)",
    )
    ap.add_argument(
        "--no-verify-gcs",
        dest="verify_gcs",
        action="store_false",
        help="confia no gs_video do banco sem checar o objeto online",
    )
    ap.set_defaults(verify_gcs=True)
    args = ap.parse_args()

    if not os.path.isdir(ANALYSES_DIR):
        log(f"ERRO: diretório não existe: {ANALYSES_DIR}")
        return 2

    mode = "APPLY (apaga)" if args.apply else "DRY-RUN (não apaga nada)"
    log(f"modo={mode} days={args.days} verify_gcs={args.verify_gcs} orphans={args.include_orphans}")
    log(f"dir={ANALYSES_DIR}")

    db = load_db_index()
    log(f"banco: {len(db)} exames indexados")

    cutoff = time.time() - args.days * 86400
    st = Stats()

    for name in sorted(os.listdir(ANALYSES_DIR)):
        folder = os.path.join(ANALYSES_DIR, name)
        video = os.path.join(folder, "video.mp4")
        if not os.path.isdir(folder) or not os.path.isfile(video):
            continue

        sz = os.path.getsize(video)
        mtime = os.path.getmtime(video)

        # trava 3: idade
        if mtime > cutoff:
            st.skip("recente (dentro do grace period)")
            continue

        rec = db.get(name)

        # trava 2: status terminal (ou órfão, se permitido)
        if rec is None:
            if not args.include_orphans:
                st.skip("órfão (sem registro no banco)")
                continue
            status = "orphan"
        else:
            status = rec["status"]
            if status not in TERMINAL_STATUS:
                st.skip(f"status não-terminal ({status or 'vazio'})")
                continue

        # trava 1: backup no GCS comprovado
        gs_uri = (rec or {}).get("gs_video") or None
        if not gs_uri:
            gs_uri = gs_uri_from_local(folder)
        if not gs_uri:
            st.skip("sem backup GCS (gs_video/gs_path ausente)")
            continue
        if args.verify_gcs and not gcs_object_exists(gs_uri):
            st.skip("backup GCS não confirmado online")
            continue

        # passou nas 3 travas -> elegível
        if args.apply:
            try:
                os.remove(video)
            except OSError as e:
                log(f"ERRO ao remover {video}: {e}")
                st.skip("erro de I/O")
                continue
            log(f"DEL {name}  {human(sz)}  status={status}")
        else:
            log(f"would-DEL {name}  {human(sz)}  status={status}")
        st.deleted += 1
        st.freed_bytes += sz

    log("-" * 60)
    verb = "removidos" if args.apply else "elegíveis"
    log(
        f"{verb}: {st.deleted} vídeos  |  espaço {'liberado' if args.apply else 'a liberar'}: {human(st.freed_bytes)}"
    )
    if st.skip_reasons:
        log("ignorados:")
        for reason, n in sorted(st.skip_reasons.items(), key=lambda x: -x[1]):
            log(f"  {n:5d}  {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
