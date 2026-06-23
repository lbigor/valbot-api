"""Agregação de métricas do Dashboard Regulatório (spec §15).

Três grupos de indicadores, todos parametrizados por uma janela de ``dias``:

  • :func:`operacionais` (§15.2) — saúde da operação: volume recebido/processado,
    distribuição por status, taxa de erro, tempo médio de análise, custo total e
    backlog de Ordens de Serviço por status.
  • :func:`regulatorios` (§15.3) — qualidade regulatória: concordância
    resultado/pontuação, distribuição de divergências, top infrações, recortes por
    unidade/examinador/categoria, taxas de interrupção e de evidência insuficiente,
    e contagem de comentários inadequados do examinador.
  • :func:`resumo` — embrulha os dois grupos num único dict.

Filosofia de robustez (herdada de ``backend.core.db``): em dev sem Postgres, ou
quando uma tabela está vazia, ``fetch_one``/``fetch_all`` devolvem ``None``/``[]``.
Cada função aqui parte de um *default* com zeros/listas vazias e só sobrescreve o
que conseguiu ler — nenhuma delas levanta. Toda query é isolada em ``try/except``
para que a falha de um indicador não derrube o restante do painel.

Convenções: placeholders ``%s`` com params em tupla; ``COALESCE``/``NULLIF`` para
null-safety e divisão protegida; janela via ``created_at >= NOW() - (%s || ' days')::interval``.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.db import fetch_all, fetch_one

log = logging.getLogger("valbot.dashboard")

# Tipo de divergência que representa evidência insuficiente (spec §9 / §15.3).
TIPO_EVIDENCIA_INSUFICIENTE = "5_evidencia_insuficiente"


def _intervalo(dias: int) -> str:
    """Devolve o fragmento de intervalo já saneado (inteiro >= 1)."""
    try:
        d = int(dias)
    except (TypeError, ValueError):
        d = 30
    return str(max(d, 1))


def _linhas_para_contagem(linhas: list[dict], chave: str, valor: str = "total") -> dict[str, int]:
    """Converte ``[{chave: x, total: n}, ...]`` num dict ``{x: n}``.

    Linhas com ``chave`` nula são agrupadas sob ``"(sem informação)"`` para não
    perder o registro nem quebrar a serialização JSON.
    """
    out: dict[str, int] = {}
    for ln in linhas:
        rotulo = ln.get(chave)
        rotulo = str(rotulo) if rotulo is not None else "(sem informação)"
        try:
            out[rotulo] = int(ln.get(valor) or 0)
        except (TypeError, ValueError):
            out[rotulo] = 0
    return out


# ---------------------------------------------------------------------------
# §15.2 — Métricas operacionais
# ---------------------------------------------------------------------------
def operacionais(dias: int = 30) -> dict[str, Any]:
    """Indicadores operacionais da janela (spec §15.2).

    Retorna sempre o dict completo, mesmo sem banco — campos numéricos zerados,
    ``por_status``/``os_pendentes_por_status`` como dicts vazios.
    """
    janela = _intervalo(dias)
    resultado: dict[str, Any] = {
        "periodo_dias": int(dias),
        "total_recebidos": 0,
        "total_processados": 0,
        "por_status": {},
        "taxa_erro": 0.0,
        "tempo_medio_analise_s": 0.0,
        "custo_total_usd": 0.0,
        "os_pendentes_por_status": {},
    }

    # Agregados de volume/custo/tempo num único SELECT sobre exams.
    # "processados" = quem chegou a um estado terminal de análise.
    # taxa_erro = falhos / recebidos (protegida por NULLIF).
    try:
        row = fetch_one(
            """
            SELECT
                COUNT(*)                                                AS total_recebidos,
                COUNT(*) FILTER (
                    WHERE resultado IN ('APROVADO', 'INAPTO', 'SEM_AVALIACAO', 'FALHOU')
                )                                                       AS total_processados,
                COUNT(*) FILTER (WHERE resultado = 'FALHOU')            AS falhos,
                COALESCE(
                    COUNT(*) FILTER (WHERE resultado = 'FALHOU')::numeric
                    / NULLIF(COUNT(*), 0),
                    0
                )                                                       AS taxa_erro,
                COALESCE(AVG(gemini_elapsed_s), 0)                      AS tempo_medio_analise_s,
                COALESCE(SUM(cost_usd), 0)                              AS custo_total_usd
            FROM exams
            WHERE created_at >= NOW() - (%s || ' days')::interval
            """,
            (janela,),
        )
        if row:
            resultado["total_recebidos"] = int(row.get("total_recebidos") or 0)
            resultado["total_processados"] = int(row.get("total_processados") or 0)
            resultado["taxa_erro"] = float(row.get("taxa_erro") or 0.0)
            resultado["tempo_medio_analise_s"] = float(row.get("tempo_medio_analise_s") or 0.0)
            resultado["custo_total_usd"] = float(row.get("custo_total_usd") or 0.0)
    except Exception as e:  # robustez: indicador isolado não derruba o painel
        log.warning("operacionais: agregados de exams falharam: %s", e)

    # Distribuição por status (status bruto da pipeline).
    try:
        linhas = fetch_all(
            """
            SELECT status, COUNT(*) AS total
            FROM exams
            WHERE created_at >= NOW() - (%s || ' days')::interval
            GROUP BY status
            ORDER BY total DESC
            """,
            (janela,),
        )
        resultado["por_status"] = _linhas_para_contagem(linhas, "status")
    except Exception as e:
        log.warning("operacionais: por_status falhou: %s", e)

    # Backlog de Ordens de Serviço por status (registros ainda não encerrados).
    try:
        linhas = fetch_all(
            """
            SELECT status, COUNT(*) AS total
            FROM ordens_servico
            WHERE encerrada_em IS NULL
              AND criada_em >= NOW() - (%s || ' days')::interval
            GROUP BY status
            ORDER BY total DESC
            """,
            (janela,),
        )
        resultado["os_pendentes_por_status"] = _linhas_para_contagem(linhas, "status")
    except Exception as e:
        log.warning("operacionais: os_pendentes_por_status falhou: %s", e)

    return resultado


# ---------------------------------------------------------------------------
# §15.2+ — Custos de processamento (vídeo/tokens) para acompanhamento e cobrança
# ---------------------------------------------------------------------------
def custos(dias: int = 30) -> dict[str, Any]:
    """Agregação granular de custo de processamento da janela.

    Quebra ``cost_usd`` e os tokens (``cost_tokens_in/out``) por dia, unidade e
    categoria — base para acompanhar o gasto de IA e adequar a cobrança. Cada
    recorte é isolado em ``try/except`` (falha de um não derruba os demais) e o
    default já vem zerado, então em dev sem banco devolve a estrutura completa.
    """
    janela = _intervalo(dias)
    resultado: dict[str, Any] = {
        "periodo_dias": int(dias),
        "custo_total_usd": 0.0,
        "num_exames_cobrados": 0,
        "custo_medio_por_exame_usd": 0.0,
        "tokens_in_total": 0,
        "tokens_out_total": 0,
        "serie_diaria": [],
        "por_unidade": [],
        "por_categoria": [],
    }

    # Totais + média por exame (só conta exames com custo registrado).
    try:
        row = fetch_one(
            """
            SELECT
                COALESCE(SUM(cost_usd), 0)                              AS custo_total_usd,
                COUNT(*) FILTER (WHERE cost_usd IS NOT NULL)            AS num_exames_cobrados,
                COALESCE(SUM(cost_tokens_in), 0)                       AS tokens_in_total,
                COALESCE(SUM(cost_tokens_out), 0)                      AS tokens_out_total,
                COALESCE(
                    SUM(cost_usd) / NULLIF(COUNT(*) FILTER (WHERE cost_usd IS NOT NULL), 0),
                    0
                )                                                      AS custo_medio_por_exame_usd
            FROM exams
            WHERE created_at >= NOW() - (%s || ' days')::interval
            """,
            (janela,),
        )
        if row:
            resultado["custo_total_usd"] = float(row.get("custo_total_usd") or 0.0)
            resultado["num_exames_cobrados"] = int(row.get("num_exames_cobrados") or 0)
            resultado["tokens_in_total"] = int(row.get("tokens_in_total") or 0)
            resultado["tokens_out_total"] = int(row.get("tokens_out_total") or 0)
            resultado["custo_medio_por_exame_usd"] = float(
                row.get("custo_medio_por_exame_usd") or 0.0
            )
    except Exception as e:
        log.warning("custos: totais falharam: %s", e)

    # Série diária (para gráfico de tendência).
    try:
        linhas = fetch_all(
            """
            SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS dia,
                   COALESCE(SUM(cost_usd), 0)                           AS custo_usd,
                   COUNT(*)                                            AS num_exames
            FROM exams
            WHERE created_at >= NOW() - (%s || ' days')::interval
            GROUP BY 1 ORDER BY 1
            """,
            (janela,),
        )
        resultado["serie_diaria"] = [
            {
                "dia": r.get("dia"),
                "custo_usd": float(r.get("custo_usd") or 0.0),
                "num_exames": int(r.get("num_exames") or 0),
            }
            for r in (linhas or [])
        ]
    except Exception as e:
        log.warning("custos: serie_diaria falhou: %s", e)

    # Recorte por unidade (top 50) e por categoria.
    for chave, col in (("por_unidade", "local_unidade"), ("por_categoria", "categoria")):
        try:
            linhas = fetch_all(
                f"""
                SELECT COALESCE(NULLIF({col}, ''), 'N/D')      AS rotulo,
                       COALESCE(SUM(cost_usd), 0)              AS custo_usd,
                       COUNT(*)                               AS num_exames
                FROM exams
                WHERE created_at >= NOW() - (%s || ' days')::interval
                GROUP BY 1 ORDER BY custo_usd DESC LIMIT 50
                """,
                (janela,),
            )
            resultado[chave] = [
                {
                    "rotulo": r.get("rotulo"),
                    "custo_usd": float(r.get("custo_usd") or 0.0),
                    "num_exames": int(r.get("num_exames") or 0),
                }
                for r in (linhas or [])
            ]
        except Exception as e:
            log.warning("custos: %s falhou: %s", chave, e)

    return resultado


# ---------------------------------------------------------------------------
# §15.3 — Métricas regulatórias
# ---------------------------------------------------------------------------
def regulatorios(dias: int = 30) -> dict[str, Any]:
    """Indicadores regulatórios da janela (spec §15.3).

    Baseado em ``exam_divergencias`` (1 por exame) com joins em ``exams``,
    ``exam_infractions`` e ``exam_comite_laudos``. Percentuais expressos em
    pontos (0..100); divisões protegidas por ``NULLIF``.
    """
    janela = _intervalo(dias)
    resultado: dict[str, Any] = {
        "periodo_dias": int(dias),
        "concordancia_resultado_pct": 0.0,
        "concordancia_pontuacao_pct": 0.0,
        "distribuicao_divergencias": {},
        "top_infracoes": {},
        "divergencia_por_unidade": {},
        "divergencia_por_examinador": {},
        "divergencia_por_categoria": {},
        "taxa_interrupcao_pct": 0.0,
        "taxa_evidencia_insuficiente_pct": 0.0,
        "comentarios_inadequados_examinador": 0,
    }

    # Concordância resultado/pontuação: % de TRUE sobre as divergências que de
    # fato calcularam o respectivo flag (concorda_* NOT NULL no denominador).
    try:
        row = fetch_one(
            """
            SELECT
                COALESCE(
                    100.0 * COUNT(*) FILTER (WHERE concorda_resultado IS TRUE)
                    / NULLIF(COUNT(*) FILTER (WHERE concorda_resultado IS NOT NULL), 0),
                    0
                ) AS concordancia_resultado_pct,
                COALESCE(
                    100.0 * COUNT(*) FILTER (WHERE concorda_pontuacao IS TRUE)
                    / NULLIF(COUNT(*) FILTER (WHERE concorda_pontuacao IS NOT NULL), 0),
                    0
                ) AS concordancia_pontuacao_pct
            FROM exam_divergencias
            WHERE created_at >= NOW() - (%s || ' days')::interval
            """,
            (janela,),
        )
        if row:
            resultado["concordancia_resultado_pct"] = float(
                row.get("concordancia_resultado_pct") or 0.0
            )
            resultado["concordancia_pontuacao_pct"] = float(
                row.get("concordancia_pontuacao_pct") or 0.0
            )
    except Exception as e:
        log.warning("regulatorios: concordância falhou: %s", e)

    # Distribuição de divergências por tipo.
    try:
        linhas = fetch_all(
            """
            SELECT tipo_divergencia, COUNT(*) AS total
            FROM exam_divergencias
            WHERE created_at >= NOW() - (%s || ' days')::interval
            GROUP BY tipo_divergencia
            ORDER BY total DESC
            """,
            (janela,),
        )
        resultado["distribuicao_divergencias"] = _linhas_para_contagem(linhas, "tipo_divergencia")
    except Exception as e:
        log.warning("regulatorios: distribuicao_divergencias falhou: %s", e)

    # Top 10 infrações por regra (das infrações detectadas na janela).
    try:
        linhas = fetch_all(
            """
            SELECT i.regra_id, COUNT(*) AS total
            FROM exam_infractions i
            JOIN exams e ON e.id = i.exam_id
            WHERE e.created_at >= NOW() - (%s || ' days')::interval
            GROUP BY i.regra_id
            ORDER BY total DESC
            LIMIT 10
            """,
            (janela,),
        )
        resultado["top_infracoes"] = _linhas_para_contagem(linhas, "regra_id")
    except Exception as e:
        log.warning("regulatorios: top_infracoes falhou: %s", e)

    # Divergência por unidade — usa unidade (010) com fallback para local_unidade (001).
    try:
        linhas = fetch_all(
            """
            SELECT COALESCE(e.unidade, e.local_unidade) AS unidade, COUNT(*) AS total
            FROM exam_divergencias d
            JOIN exams e ON e.id = d.exam_id
            WHERE d.created_at >= NOW() - (%s || ' days')::interval
            GROUP BY COALESCE(e.unidade, e.local_unidade)
            ORDER BY total DESC
            """,
            (janela,),
        )
        resultado["divergencia_por_unidade"] = _linhas_para_contagem(linhas, "unidade")
    except Exception as e:
        log.warning("regulatorios: divergencia_por_unidade falhou: %s", e)

    # Divergência por examinador — top 10.
    try:
        linhas = fetch_all(
            """
            SELECT e.examinador, COUNT(*) AS total
            FROM exam_divergencias d
            JOIN exams e ON e.id = d.exam_id
            WHERE d.created_at >= NOW() - (%s || ' days')::interval
            GROUP BY e.examinador
            ORDER BY total DESC
            LIMIT 10
            """,
            (janela,),
        )
        resultado["divergencia_por_examinador"] = _linhas_para_contagem(linhas, "examinador")
    except Exception as e:
        log.warning("regulatorios: divergencia_por_examinador falhou: %s", e)

    # Divergência por categoria.
    try:
        linhas = fetch_all(
            """
            SELECT e.categoria, COUNT(*) AS total
            FROM exam_divergencias d
            JOIN exams e ON e.id = d.exam_id
            WHERE d.created_at >= NOW() - (%s || ' days')::interval
            GROUP BY e.categoria
            ORDER BY total DESC
            """,
            (janela,),
        )
        resultado["divergencia_por_categoria"] = _linhas_para_contagem(linhas, "categoria")
    except Exception as e:
        log.warning("regulatorios: divergencia_por_categoria falhou: %s", e)

    # Taxa de interrupção (% de exames com houve_interrupcao=TRUE na janela).
    try:
        row = fetch_one(
            """
            SELECT COALESCE(
                100.0 * COUNT(*) FILTER (WHERE houve_interrupcao IS TRUE)
                / NULLIF(COUNT(*), 0),
                0
            ) AS taxa_interrupcao_pct
            FROM exams
            WHERE created_at >= NOW() - (%s || ' days')::interval
            """,
            (janela,),
        )
        if row:
            resultado["taxa_interrupcao_pct"] = float(row.get("taxa_interrupcao_pct") or 0.0)
    except Exception as e:
        log.warning("regulatorios: taxa_interrupcao_pct falhou: %s", e)

    # Taxa de evidência insuficiente — divergência marcada como tal OU flag
    # evidencia_suficiente=FALSE, sobre o total de divergências da janela.
    try:
        row = fetch_one(
            """
            SELECT COALESCE(
                100.0 * COUNT(*) FILTER (
                    WHERE tipo_divergencia = %s
                       OR evidencia_suficiente IS FALSE
                )
                / NULLIF(COUNT(*), 0),
                0
            ) AS taxa_evidencia_insuficiente_pct
            FROM exam_divergencias
            WHERE created_at >= NOW() - (%s || ' days')::interval
            """,
            (TIPO_EVIDENCIA_INSUFICIENTE, janela),
        )
        if row:
            resultado["taxa_evidencia_insuficiente_pct"] = float(
                row.get("taxa_evidencia_insuficiente_pct") or 0.0
            )
    except Exception as e:
        log.warning("regulatorios: taxa_evidencia_insuficiente_pct falhou: %s", e)

    # Comentários inadequados do examinador — laudos do comitê cujo jsonb
    # comentarios_examinador tem ao menos um item (jsonb_array_length > 0).
    try:
        row = fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM exam_comite_laudos l
            JOIN exams e ON e.id = l.exam_id
            WHERE e.created_at >= NOW() - (%s || ' days')::interval
              AND jsonb_typeof(l.comentarios_examinador) = 'array'
              AND jsonb_array_length(l.comentarios_examinador) > 0
            """,
            (janela,),
        )
        if row:
            resultado["comentarios_inadequados_examinador"] = int(row.get("total") or 0)
    except Exception as e:
        log.warning("regulatorios: comentarios_inadequados_examinador falhou: %s", e)

    return resultado


# ---------------------------------------------------------------------------
# Supervisor — concordância da instância final (Supervisor x Auditor x IA)
# ---------------------------------------------------------------------------
def supervisor(dias: int = 30) -> dict[str, Any]:
    """Concordância da decisão final do Supervisor com o Auditor e com a IA.

    Baseado em ``supervisor_decisoes`` (migration 017) com LEFT JOIN em
    ``auditor_pareceres`` pela OS:

      • supervisor x auditor — % de decisões 'homologar' (Supervisor manteve o
        parecer do Auditor; 'reformar' = sobrepôs).
      • supervisor x IA — % em que o Supervisor homologou um parecer que JÁ
        concordava com a IA (``auditor_pareceres.decisao = 'concorda'``).

    Robustez idêntica ao resto do módulo: default zerado, query isolada em
    try/except, percentuais 0..100 com divisão protegida por ``NULLIF``.
    """
    janela = _intervalo(dias)
    resultado: dict[str, Any] = {
        "periodo_dias": int(dias),
        "total_decisoes": 0,
        "homologadas": 0,
        "reformadas": 0,
        "concordancia_supervisor_auditor_pct": 0.0,
        "concordancia_supervisor_ia_pct": 0.0,
    }
    try:
        row = fetch_one(
            """
            SELECT
                COUNT(*)                                              AS total_decisoes,
                COUNT(*) FILTER (WHERE s.decisao_final = 'homologar')  AS homologadas,
                COUNT(*) FILTER (WHERE s.decisao_final = 'reformar')   AS reformadas,
                COALESCE(
                    100.0 * COUNT(*) FILTER (WHERE s.decisao_final = 'homologar')
                    / NULLIF(COUNT(*), 0), 0
                )                                                     AS concordancia_supervisor_auditor_pct,
                COALESCE(
                    100.0 * COUNT(*) FILTER (
                        WHERE p.decisao = 'concorda' AND s.decisao_final = 'homologar')
                    / NULLIF(COUNT(*), 0), 0
                )                                                     AS concordancia_supervisor_ia_pct
            FROM supervisor_decisoes s
            LEFT JOIN auditor_pareceres p ON p.os_id = s.os_id
            WHERE s.created_at >= NOW() - (%s || ' days')::interval
            """,
            (janela,),
        )
        if row:
            resultado["total_decisoes"] = int(row.get("total_decisoes") or 0)
            resultado["homologadas"] = int(row.get("homologadas") or 0)
            resultado["reformadas"] = int(row.get("reformadas") or 0)
            resultado["concordancia_supervisor_auditor_pct"] = float(
                row.get("concordancia_supervisor_auditor_pct") or 0.0
            )
            resultado["concordancia_supervisor_ia_pct"] = float(
                row.get("concordancia_supervisor_ia_pct") or 0.0
            )
    except Exception as e:
        log.warning("supervisor: concordância falhou: %s", e)

    return resultado


# ---------------------------------------------------------------------------
# Resumo consolidado
# ---------------------------------------------------------------------------
def compliance(dias: int = 30) -> dict[str, Any]:
    """Comentários de compliance pendentes por tipo (camada não-pontuável, §15)."""
    try:
        from backend.compliance import repositorio

        return repositorio.resumo()
    except Exception as e:  # pragma: no cover
        log.warning("dashboard.compliance falhou: %s", e)
        return {}


def resumo(dias: int = 30) -> dict[str, Any]:
    """Consolida operacionais + regulatórios + compliance da mesma janela."""
    return {
        "periodo_dias": int(dias),
        "operacionais": operacionais(dias),
        "regulatorios": regulatorios(dias),
        "compliance": compliance(dias),
        "custos": custos(dias),
        "supervisor": supervisor(dias),
    }
