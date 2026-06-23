"""Busca dos dados OFICIAIS do exame na Unidade Gestora (Techpratico).

Endpoint de entrada do integrador (espelho do callback de saída em
``laudo_sender.py``):

    POST https://convert.se.techpratico.net/conversao/dados-exame-analise-ia
    Header: X-API-Key: <VALBOT_TECHPRATICO_API_KEY>
    Payload: { idAgendamento (int), id_analise (hash do exame VALBOT) }

Retorno (contrato observado):
    {
      "id":         <int>,        # = idAgendamento
      "renach":     "<str>",
      "processo":   "<str>",
      "categoria":  "<str>",      # ACC|A|B|C|D|E
      "resultado_exame": "A"|"R"|"N",   # VEREDITO OFICIAL da Comissão
      "training_annotations": [          # anotações TPA do examinador
          { "timestamp": "MM:SS", "anotacoes": "<texto c/ artigo CTB>" }
      ],
      "id_analise": "<hash>"
    }

É a porta de ENTRADA dos dados oficiais que o VALBOT não recebe no
``init_upload`` (o ``upload.json`` vem pobre: examinador/resultado oficial
vazios). O ``resultado_exame`` alimenta o Bloco 4 do laudo (Resultado
Oficial) e a análise de divergência; as ``training_annotations`` são as
infrações apontadas pelo examinador (TPA).

Esta classe é a ÚNICA porta de entrada pra esse fetch. Centraliza config,
POST autenticado com timeout e parsing tipado. Nenhum segredo é hardcoded —
a API key vem de env (falta dela é erro de configuração explícito).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Endpoint + credencial do integrador. URL sobrescrevível via env (sandbox em
# testes); API key reutiliza a mesma do callback de saída (laudo_sender).
TECHPRATICO_DADOS_URL = os.environ.get(
    "VALBOT_TECHPRATICO_DADOS_URL",
    "https://convert.se.techpratico.net/conversao/dados-exame-analise-ia",
)
TECHPRATICO_API_KEY = os.environ.get("VALBOT_TECHPRATICO_API_KEY", "")


class DadosExameFetcherError(Exception):
    """Erro de config/rede/HTTP no fetch. Mensagem segura pra mostrar ao operador."""


@dataclass
class AnotacaoTPA:
    """Uma anotação do examinador (TPA) no agendamento oficial."""

    timestamp: str  # "MM:SS"
    anotacoes: str  # texto livre, normalmente cita artigo CTB / natureza da falta


@dataclass
class DadosExame:
    """Dados OFICIAIS do exame retornados pela Unidade Gestora."""

    id_agendamento: int | None
    id_analise: str
    renach: str = ""
    processo: str = ""
    categoria: str = ""
    resultado_exame: str = ""  # A/R/N — veredito oficial da Comissão
    anotacoes_tpa: list[AnotacaoTPA] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # resposta crua, pra auditoria

    @classmethod
    def from_response(cls, data: dict, *, id_analise: str) -> DadosExame:
        anotacoes = [
            AnotacaoTPA(
                timestamp=str(a.get("timestamp", "")),
                anotacoes=str(a.get("anotacoes", "")),
            )
            for a in (data.get("training_annotations") or [])
        ]
        return cls(
            id_agendamento=data.get("id"),
            id_analise=str(data.get("id_analise") or id_analise),
            renach=str(data.get("renach") or ""),
            processo=str(data.get("processo") or ""),
            categoria=str(data.get("categoria") or "").upper(),
            resultado_exame=str(data.get("resultado_exame") or "").strip().upper(),
            anotacoes_tpa=anotacoes,
            raw=data,
        )


class DadosExameFetcher:
    """Cliente do fetch de dados oficiais (Techpratico). Barato por request."""

    def __init__(self, *, url: str | None = None, api_key: str | None = None):
        self.url = url or TECHPRATICO_DADOS_URL
        self.api_key = api_key if api_key is not None else TECHPRATICO_API_KEY

    def _validar_config(self) -> None:
        if not self.api_key:
            raise DadosExameFetcherError(
                "VALBOT_TECHPRATICO_API_KEY não configurada no servidor. "
                "Contate o administrador."
            )

    def buscar(self, id_agendamento: int, id_analise: str) -> DadosExame:
        """POSTa {idAgendamento, id_analise} e devolve os dados oficiais tipados.

        Levanta DadosExameFetcherError em falha de config/rede/HTTP — o caller
        precisa dos dados, então o erro propaga (diferente do envio de laudo,
        que é best-effort).
        """
        self._validar_config()
        if not id_analise:
            raise DadosExameFetcherError("id_analise (hash do exame) é obrigatório.")
        payload = {"idAgendamento": id_agendamento, "id_analise": id_analise}

        import httpx

        try:
            with httpx.Client(timeout=60.0) as c:
                resp = c.post(self.url, json=payload, headers={"X-API-Key": self.api_key})
        except Exception as e:
            log.warning("fetch dados-exame %s falhou (rede): %s", str(id_analise)[:12], e)
            raise DadosExameFetcherError(f"Falha de rede ao buscar dados do exame: {e}") from e

        if not (200 <= resp.status_code < 300):
            body = (resp.text or "")[:200]
            log.warning(
                "fetch dados-exame %s rejeitado: HTTP %s — %s",
                str(id_analise)[:12],
                resp.status_code,
                body,
            )
            raise DadosExameFetcherError(
                f"Unidade Gestora retornou HTTP {resp.status_code} ao buscar dados do exame."
            )

        try:
            data = resp.json()
        except Exception as e:
            raise DadosExameFetcherError("Resposta da Unidade Gestora não é JSON válido.") from e

        log.info(
            "dados-exame %s buscados OK (resultado_oficial=%s, anotacoes=%d)",
            str(id_analise)[:12],
            data.get("resultado_exame"),
            len(data.get("training_annotations") or []),
        )
        return DadosExame.from_response(data, id_analise=id_analise)
