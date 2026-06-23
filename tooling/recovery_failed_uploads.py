"""One-shot recovery: reabilita exames `status=failed` (causados por 403 S3)
pra que o sweep `process_pending_s3.py` os retome via boto3 autenticado.

Pra cada exame failed:
  1. Lê upload.json. Se `video.gs_path_original_s3` ausente, copia de
     `video.source_url` (sweep usa esse campo pra detectar a URL S3 original).
  2. Reseta status.json → status="queued" (e limpa error).
  3. Reseta DB → status='queued', error=NULL.

Depois roda process_pending_s3 main() que vai:
  4. boto3 baixa S3 → sobe GCS.
  5. Chama Gemini, gera laudo.pdf.
  6. Atualiza DB com aprovado/categoria/etc.

Idempotente: se o exame voltar a falhar, fica em failed de novo. Pode rodar
de novo sem efeito colateral.

Uso (na VM, dentro do container):
    docker exec valbot-api python -m tooling.recovery_failed_uploads
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ANALYSES_DIR = Path(os.environ.get("ANALYSES_DIR", "/opt/valbot/storage/analyses"))


def _reset_one(analysis_id: str) -> bool:
    """Reseta upload.json + status.json + DB. Devolve True se ficou pronto pro sweep."""
    out_dir = ANALYSES_DIR / analysis_id
    upload_path = out_dir / "upload.json"
    status_path = out_dir / "status.json"
    if not upload_path.exists():
        log.warning("[%s] upload.json ausente — pula", analysis_id[:12])
        return False

    try:
        upload_meta = json.loads(upload_path.read_text())
    except Exception as e:
        log.warning("[%s] upload.json corrompido (%s) — pula", analysis_id[:12], e)
        return False

    video = upload_meta.setdefault("video", {})
    source_url = video.get("source_url") or ""
    if not source_url:
        log.warning("[%s] sem source_url — pula", analysis_id[:12])
        return False

    # process_pending_s3.process_one detecta "já streamado" via
    # `gs_path.startswith("gs://")`. Pro init_upload original o gs_path é o
    # DESTINO futuro (intenção), mas o sweep interpreta como FATO. Pra exames
    # failed o vídeo nunca chegou no GCS, então precisamos zerar essa pista.
    #
    # Trocamos gs_path pelo source_url HTTPS — assim o sweep entra no ramo
    # "stream pela primeira vez", boto3 baixa do S3 e sobe pro GCS de verdade.
    # Quando sucesso, ele reescreve gs_path pro gs:// canônico.
    current_gs = video.get("gs_path") or ""
    if current_gs.startswith("gs://"):
        # Preserva o destino canônico previsto (pro caso de debug futuro).
        video["gs_path_destino_planejado"] = current_gs
    video["gs_path"] = source_url
    video["gs_path_original_s3"] = source_url  # safety pro caller que usa esse field

    upload_path.write_text(json.dumps(upload_meta, indent=2, ensure_ascii=False))

    # status.json → queued (limpa error)
    status_path.write_text(
        json.dumps(
            {"status": "queued", "updated_at": datetime.utcnow().isoformat() + "Z"},
            indent=2,
            ensure_ascii=False,
        )
    )
    return True


def main() -> int:
    try:
        from tooling.api_stub import db as _db
    except ImportError as e:
        log.error("não consigo importar tooling.api_stub.db: %s", e)
        return 2

    if _db._DISABLED:  # noqa: SLF001
        log.error("DB disabled (DATABASE_URL ausente?). Abortando.")
        return 2

    # Lista exames failed
    with _db._conn() as c:  # noqa: SLF001
        if c is None:
            log.error("sem conexão Postgres")
            return 2
        rows = c.execute(
            "SELECT hash FROM exams WHERE status='failed' ORDER BY created_at DESC"
        ).fetchall()
        hashes = [r[0] for r in rows]

    log.info("achei %d exames com status=failed pra recuperar", len(hashes))
    if not hashes:
        return 0

    ready, skipped = [], 0
    for h in hashes:
        if _reset_one(h):
            ready.append(h)
        else:
            skipped += 1

    log.info("reset OK em %d exames (skipped=%d)", len(ready), skipped)
    if not ready:
        log.warning("nada pra resetar no DB; saindo")
        return 0

    # Reset DB em batch
    log.info("resetando DB: status='queued', error=NULL pros %d", len(ready))
    with _db._conn() as c:  # noqa: SLF001
        if c is None:
            log.error("sem conexão Postgres pro UPDATE")
            return 2
        c.execute(
            "UPDATE exams SET status='queued', error=NULL WHERE hash = ANY(%s)",
            (ready,),
        )
    log.info("DB resetado. agora chamando o sweep…")

    # Roda sweep (process_pending_s3.main)
    from tooling import process_pending_s3

    # main() lê sys.argv — passa vazio pra evitar argparse pegar nossos flags
    saved_argv = sys.argv
    sys.argv = ["process_pending_s3"]
    try:
        rc = process_pending_s3.main()
    finally:
        sys.argv = saved_argv

    log.info("sweep terminou com exit_code=%s", rc)
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
