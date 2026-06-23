"""Laudo Explicável (spec §14) — montagem do JSON estruturado + integridade.

Consolida as saídas de todos os motores num único documento auditável, com os
blocos mínimos da spec §14.2. Dois recortes pedidos explicitamente pelo produto
vão em destaque:

  • ``cobertura``  — TUDO o que foi auditado neste exame (regras avaliadas,
                     eventos detectados, exceções da §3.5 aplicadas).
  • ``divergencia`` — COMO e ONDE há divergência (tipo, subtipos, o que concorda
                     e o que não, campos oficiais ausentes).

O laudo recebe um ``hash_relatorio`` (SHA-256 do conteúdo) para integridade
(spec §14.2 / §17.2). O PDF continua sendo gerado pelo motor existente
(``src/reporting``); aqui produzimos o JSON, que a spec §14.3 também exige.
"""

from __future__ import annotations

import hashlib
import json

from backend.models import (
    Comparacao,
    LaudoComite,
    PayloadExame,
    ResultadoPontuacao,
    SaidaDeteccao,
    SaidaNormativo,
)


def _mascarar_cpf(cpf: str | None) -> str | None:
    if not cpf:
        return None
    if "*" in cpf:
        return cpf
    d = "".join(c for c in cpf if c.isdigit())
    return f"***.{d[3:6]}.{d[6:9]}-**" if len(d) == 11 else None


def montar_laudo_json(
    *,
    exame_id: str,
    payload: PayloadExame,
    deteccao: SaidaDeteccao,
    normativo: SaidaNormativo,
    pontuacao: ResultadoPontuacao,
    comparacao: Comparacao,
    comite: LaudoComite | None = None,
    os_id: str | None = None,
    video_hash: str | None = None,
    emitido_em: str | None = None,
    compliance: list | None = None,
) -> dict:
    """Monta o laudo JSON completo. Determinístico (não chama rede)."""
    cand = payload.candidato

    # COBERTURA — tudo o que foi auditado.
    regras_avaliadas = sorted(
        {e.regra_aplicada for e in normativo.enquadramentos if e.regra_aplicada}
    )
    excecoes_aplicadas = [
        {"evento_id": e.evento_id, "regra": e.regra_aplicada, "excecao": e.excecao_aplicada}
        for e in normativo.enquadramentos
        if e.excecao_aplicada
    ]
    cobertura = {
        "regras_avaliadas": regras_avaliadas,
        "total_eventos_detectados": len(deteccao.eventos_detectados),
        "total_enquadrados": sum(1 for e in normativo.enquadramentos if e.enquadrado),
        "excecoes_aplicadas": excecoes_aplicadas,  # §3.5 — o que NÃO pontuou e por quê
        "eventos_nao_enquadrados": [
            {"evento_id": n.evento_id, "motivo": n.motivo}
            for n in normativo.eventos_nao_enquadrados
        ],
        "comentarios_examinador_detectados": len(deteccao.comentarios_examinador),
        "evidencia_suficiente": deteccao.evidencia_suficiente,
    }

    # ANÁLISE DETALHADA por infração (spec §14.2).
    analise = [
        {
            "regra": e.regra_aplicada,
            "artigo_ctb": e.artigo_ctb,
            "ficha_mbedv": e.ficha_mbedv,
            "natureza": e.natureza.value if e.natureza else None,
            "peso": e.peso,
            "timestamp_s": e.timestamp_s,
            "justificativa": e.justificativa,
            "excecao_aplicada": e.excecao_aplicada,
            "confianca": e.confianca_enquadramento,
            "requer_revisao_humana": e.requer_revisao_humana,
        }
        for e in normativo.enquadramentos
    ]

    laudo = {
        "laudo_versao": "laudo/2.0",
        "exame_id": exame_id,
        "emitido_em": emitido_em,
        "identificacao": {
            "exame_id": exame_id,
            "unidade": payload.unidade,
            "data_hora_exame": payload.data_hora_exame,
            "categoria": cand.categoria_pretendida.value if cand.categoria_pretendida else None,
            "tipo_exame": payload.tipo_exame.value,
        },
        "candidato": {
            "nome": cand.nome,
            "cpf_mascarado": _mascarar_cpf(cand.cpf_mascarado),
            "renach": cand.renach,
            "categoria_pretendida": cand.categoria_pretendida.value
            if cand.categoria_pretendida
            else None,
        },
        "examinador": {
            "matricula": payload.examinador.matricula,
            "nome": payload.examinador.nome,
            "eh_preposto": payload.examinador.eh_preposto,
        },
        "resultado_oficial": {
            "decisao": comparacao.resultado_oficial.value if comparacao.resultado_oficial else None,
            "pontuacao": comparacao.pontuacao_oficial,
            "infracoes": [
                i.model_dump()
                for i in (payload.resultado_oficial.infracoes if payload.resultado_oficial else [])
            ],
        },
        "resultado_calculado": {
            "decisao": pontuacao.resultado_calculado.value,
            "pontuacao": pontuacao.pontuacao_calculada,
            "limite_reprovacao": pontuacao.limite_reprovacao,
            "houve_interrupcao": pontuacao.houve_interrupcao,
            "infracoes": [i.model_dump() for i in pontuacao.infracoes_calculadas],
        },
        "cobertura": cobertura,
        "analise_detalhada": analise,
        "divergencia": {
            "tipo": comparacao.tipo_divergencia.value,
            "subtipos_associados": [s.value for s in comparacao.subtipos_associados],
            "concorda_resultado": comparacao.concorda_resultado,
            "concorda_pontuacao": comparacao.concorda_pontuacao,
            "concorda_infracoes": comparacao.concorda_infracoes,
            "evidencia_suficiente": comparacao.evidencia_suficiente,
            "encaminhamento": comparacao.encaminhamento.value,
            "detalhes": comparacao.detalhes,
        },
        "comite_de_ia": comite.model_dump() if comite else None,
        "eventos_examinador": [
            {
                "timestamp_audio": c.timestamp_audio_seg,
                "transcricao": c.transcricao,
                "classificacao": c.classificacao,
            }
            for c in deteccao.comentarios_examinador
        ],
        # Compliance — sinais NÃO-pontuáveis (separados das infrações). Tela dedicada.
        "comentarios_compliance": [
            {
                "tipo": c.tipo.value,
                "descricao": c.descricao,
                "origem_codigo": c.origem_codigo,
                "timestamp_s": c.timestamp_s,
                "classificacao": c.classificacao,
                "status": c.status,
            }
            for c in (compliance or [])
        ],
        "ordem_servico": {"os_id": os_id} if os_id else None,
        "versoes": {
            "matriz_versao": pontuacao.matriz_versao,
            "modelo_deteccao": deteccao.modelo_versao,
            "comite_versao": comite.comite_versao if comite else None,
        },
        "integridade": {"video_hash": video_hash, "hash_relatorio": None},
    }

    laudo["integridade"]["hash_relatorio"] = hash_relatorio(laudo)
    return laudo


def hash_relatorio(laudo: dict) -> str:
    """SHA-256 do laudo, ignorando o próprio campo de hash (spec §14.2)."""
    copia = json.loads(json.dumps(laudo, ensure_ascii=False, sort_keys=True, default=str))
    copia.get("integridade", {}).pop("hash_relatorio", None)
    canonico = json.dumps(copia, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def gerar_pdf(laudo_json: dict, out_path: str) -> str | None:
    """Gera o PDF reaproveitando o motor existente (``src/reporting``).

    Best-effort: se WeasyPrint/template não estiverem disponíveis (dev), devolve
    None sem quebrar — o JSON já é o artefato canônico aqui.
    """
    try:
        from src.reporting import build_context, render_pdf  # type: ignore

        ctx = build_context(laudo_json)
        render_pdf(ctx, out_path)
        return out_path
    except Exception:
        return None
