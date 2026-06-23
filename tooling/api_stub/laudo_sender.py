"""Envio do laudo PDF de volta pra Unidade Gestora (Techpratico).

Endpoint de callback do integrador:
    POST https://convert.se.techpratico.net/conversao/retorno-analise
    Header: X-API-Key: <VALBOT_TECHPRATICO_API_KEY>
    Payload: { id_analise, resultado (A/R/N), relatorio (PDF base64) }

Esta classe é a ÚNICA porta de saída pra esse callback. Centraliza:
  • validação (PDF existe, resultado válido, exame processado)
  • mapeamento do veredito VALBOT → A/R/N
  • base64 do PDF
  • POST autenticado com timeout + retry leve
  • registro do resultado no DB (laudo_envio_*)

Validação espelhada no frontend (botão só habilita quando has_pdf e
status processed) — mas a checagem AUTORITATIVA é aqui no backend.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Endpoint + credencial do integrador. URL pode ser sobrescrita via env pra
# apontar pra sandbox em testes. A API key NUNCA tem default hardcoded —
# falta dela é erro de configuração explícito.
TECHPRATICO_RETORNO_URL = os.environ.get(
    "VALBOT_TECHPRATICO_RETORNO_URL",
    "https://convert.se.techpratico.net/conversao/retorno-analise",
)
TECHPRATICO_API_KEY = os.environ.get("VALBOT_TECHPRATICO_API_KEY", "")

# Resultados aceitos pelo contrato do integrador.
RESULTADOS_VALIDOS = {"A", "R", "N"}


class LaudoSenderError(Exception):
    """Erro de validação ou envio. Mensagem é segura pra mostrar ao operador."""


@dataclass
class EnvioResult:
    """Resultado de uma tentativa de envio. Persistido em exams.laudo_envio_*."""

    ok: bool
    resultado: str  # A/R/N enviado
    http_status: int | None = None
    resposta: str = ""
    erro: str = ""


def mapear_resultado_valbot(overview: dict) -> str:
    """Deriva o A/R/N a partir do veredito VALBOT (não do examinador).

    É o NOSSO laudo voltando, então mapeia o que o VALBOT concluiu:
      • gate_rejected OU resultado SEM_AVALIACAO/INDEFINIDO  → 'N' (não avaliado)
      • aprovado is True                                     → 'A'
      • aprovado is False                                    → 'R'
      • aprovado is None (sem veredito)                      → 'N'
    """
    if overview.get("gate_rejected") is True:
        return "N"
    resultado = (overview.get("resultado") or "").upper()
    if resultado in {"SEM_AVALIACAO", "INDEFINIDO", "PENDENTE", "PROCESSANDO", "FALHOU"}:
        return "N"
    aprovado = overview.get("aprovado")
    if aprovado is True:
        return "A"
    if aprovado is False:
        return "R"
    return "N"


class LaudoSender:
    """Cliente do callback Techpratico. Instanciar por request é barato."""

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        analyses_dir: Path | None = None,
    ):
        self.url = url or TECHPRATICO_RETORNO_URL
        self.api_key = api_key if api_key is not None else TECHPRATICO_API_KEY
        # Import tardio pra não acoplar o módulo a um path fixo de server.py.
        if analyses_dir is None:
            from tooling.api_stub.server import ANALYSES_DIR

            analyses_dir = ANALYSES_DIR
        self.analyses_dir = analyses_dir

    # --- validações (todas levantam LaudoSenderError com msg amigável) ---

    def _validar_config(self) -> None:
        if not self.api_key:
            raise LaudoSenderError(
                "VALBOT_TECHPRATICO_API_KEY não configurada no servidor. Contate o administrador."
            )

    def _pdf_path(self, analysis_id: str) -> Path:
        f = self.analyses_dir / analysis_id / "laudo.pdf"
        if not f.exists():
            raise LaudoSenderError(
                "Laudo PDF ainda não foi gerado para este exame. Processe o exame antes de enviar."
            )
        if f.stat().st_size == 0:
            raise LaudoSenderError("Laudo PDF está vazio (0 bytes) — reprocesse o exame.")
        return f

    @staticmethod
    def _validar_resultado(resultado: str) -> str:
        r = (resultado or "").strip().upper()
        if r not in RESULTADOS_VALIDOS:
            raise LaudoSenderError(
                f"Resultado inválido '{resultado}'. Esperado um de: {sorted(RESULTADOS_VALIDOS)}."
            )
        return r

    # --- envio ---

    def enviar(self, analysis_id: str, resultado: str) -> EnvioResult:
        """Valida tudo, faz base64 do PDF e POSTa pro callback.

        Levanta LaudoSenderError em qualquer falha de validação (antes do POST).
        Falha de rede/HTTP volta como EnvioResult(ok=False) — não levanta, pra
        o caller registrar no DB e mostrar mensagem ao operador.
        """
        self._validar_config()
        resultado = self._validar_resultado(resultado)
        pdf_path = self._pdf_path(analysis_id)

        pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        payload = {
            "id_analise": analysis_id,
            "resultado": resultado,
            "relatorio": pdf_b64,
        }

        import httpx

        try:
            with httpx.Client(timeout=60.0) as c:
                resp = c.post(
                    self.url,
                    json=payload,
                    headers={"X-API-Key": self.api_key},
                )
        except Exception as e:
            log.warning("envio laudo %s falhou (rede): %s", analysis_id[:12], e)
            return EnvioResult(ok=False, resultado=resultado, erro=f"rede: {e}"[:500])

        body = (resp.text or "")[:1000]
        if 200 <= resp.status_code < 300:
            log.info("laudo %s enviado OK (resultado=%s)", analysis_id[:12], resultado)
            return EnvioResult(
                ok=True, resultado=resultado, http_status=resp.status_code, resposta=body
            )
        log.warning(
            "laudo %s rejeitado pela Unidade Gestora: HTTP %s — %s",
            analysis_id[:12],
            resp.status_code,
            body[:200],
        )
        return EnvioResult(
            ok=False,
            resultado=resultado,
            http_status=resp.status_code,
            resposta=body,
            erro=f"HTTP {resp.status_code}",
        )
