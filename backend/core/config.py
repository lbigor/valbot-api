"""Configuração central do backend, lida do ambiente.

Mantém compatibilidade com as env vars já usadas pelo deploy atual
(``DATABASE_URL``, ``GCS_BUCKET``, ``VERTEX_*``, ``VALBOT_*``) para que a
reescrita rode sobre a mesma infraestrutura sem mudar o ``.env`` de produção.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0") == "1"


@dataclass(frozen=True)
class Settings:
    # Banco
    database_url: str = os.environ.get("DATABASE_URL", "")
    db_disabled: bool = _bool("VALBOT_DB_DISABLED")

    # Storage / mídia
    gcs_bucket: str = os.environ.get("GCS_BUCKET", "valbot-prod")
    storage_dir: str = os.environ.get("VALBOT_STORAGE", "storage/analyses")

    # Análise (Motor de Detecção / Comitê)
    vertex_project: str = os.environ.get("VERTEX_PROJECT", "")
    vertex_location: str = os.environ.get("VERTEX_LOCATION", "global")
    vertex_model: str = os.environ.get("VERTEX_MODEL", "gemini-3.1-pro-preview")
    preset: str = os.environ.get("VALBOT_PRESET", "v25/valbot-r1-vip-v25")
    use_modular_v26: bool = _bool("VALBOT_USE_MODULAR_V26")

    # Comitê de IA
    comite_habilitado: bool = _bool("VALBOT_COMITE", True)
    comite_versao: str = os.environ.get("VALBOT_COMITE_VERSAO", "comite-v1.0")

    # Matriz Nacional (versão consolidada vigente)
    matriz_versao: str = os.environ.get("VALBOT_MATRIZ_VERSAO", "matriz-nacional-v1.0")

    # Validações do Motor de Evidências (spec §5.5)
    duracao_min_seg: int = int(os.environ.get("VALBOT_DURACAO_MIN", "60"))
    duracao_max_seg: int = int(os.environ.get("VALBOT_DURACAO_MAX", "1800"))

    # SLA das Ordens de Serviço (spec §12.4 — relógio começa no init_upload).
    # Prazos provisórios até definição com a Techpark; em horas.
    sla_prazo_auditor_h: int = int(os.environ.get("VALBOT_SLA_AUDITOR_H", "24"))
    sla_prazo_supervisor_h: int = int(os.environ.get("VALBOT_SLA_SUPERVISOR_H", "48"))

    # Resiliência de ingestão (spec §5.6)
    ingest_max_retries: int = int(os.environ.get("VALBOT_INGEST_MAX_RETRIES", "3"))
    dlq_retencao_dias: int = int(os.environ.get("VALBOT_DLQ_RETENCAO_DIAS", "7"))
    alerta_webhook_url: str = os.environ.get("VALBOT_ALERTA_WEBHOOK", "")

    # Segurança
    admin_token: str = os.environ.get("VALBOT_ADMIN_TOKEN", "")
    session_secret: str = os.environ.get("VALBOT_SESSION_SECRET", "")

    # Integração Unidade Gestora (Techpratico/DETRAN)
    retorno_url: str = os.environ.get("VALBOT_TECHPRATICO_RETORNO_URL", "")
    retorno_api_key: str = os.environ.get("VALBOT_TECHPRATICO_API_KEY", "")


settings = Settings()
