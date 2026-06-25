"""Persistência das saídas dos motores (camada de repositório).

Grava no Postgres as etapas intermediárias da cadeia de auditoria — payload de
evidências, eventos brutos, enquadramentos, pontuação, divergência e laudo do
Comitê — dando rastreabilidade e materializando o que antes só existia em
``result.json``. Todas as funções são best-effort: em dev sem DB (ou em falha)
viram no-op, sem mascarar o resultado de negócio.

Usa o hash do vídeo como chave de correlação com ``exams`` (mesma convenção do
backend atual) e resolve o ``exam_id`` (UUID) via :func:`db.exam_id_from_hash`.
"""

from __future__ import annotations

import logging

from backend.core import db
from backend.models import (
    CODIGO_PARA_RESULTADO,
    Comparacao,
    InfracaoOficial,
    LaudoComite,
    Natureza,
    PayloadExame,
    ResultadoExame,
    ResultadoOficial,
    ResultadoPontuacao,
    SaidaDeteccao,
    SaidaNormativo,
)

log = logging.getLogger("valbot.persistence")


def salvar_payload(hash_: str, payload: PayloadExame) -> None:
    """Persiste os campos de evidência da spec §5.4 que faltavam em ``exams`` e
    a lista discreta de infrações oficiais (migration 010)."""
    of = payload.resultado_oficial
    db.execute(
        """
        UPDATE exams SET
            unidade                = COALESCE(%s, unidade),
            tipo_exame             = COALESCE(%s, tipo_exame),
            examinador_matricula   = COALESCE(%s, examinador_matricula),
            examinador_eh_preposto = COALESCE(%s, examinador_eh_preposto),
            pontuacao_oficial      = COALESCE(%s, pontuacao_oficial),
            houve_interrupcao      = COALESCE(%s, houve_interrupcao),
            motivo_interrupcao     = COALESCE(%s, motivo_interrupcao)
        WHERE hash = %s
        """,
        (
            payload.unidade,
            payload.tipo_exame.value if payload.tipo_exame else None,
            payload.examinador.matricula,
            payload.examinador.eh_preposto,
            of.pontuacao if of else None,
            of.houve_interrupcao if of else None,
            of.motivo_interrupcao if of else None,
            hash_,
        ),
    )
    if of and of.infracoes:
        exam_id = db.exam_id_from_hash(hash_)
        if exam_id:
            for inf in of.infracoes:
                db.execute(
                    """
                    INSERT INTO exam_infracoes_oficiais (exam_id, artigo_ctb, natureza, peso)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (exam_id, artigo_ctb) DO NOTHING
                    """,
                    (
                        exam_id,
                        inf.artigo_ctb,
                        inf.natureza.value if inf.natureza else None,
                        inf.peso,
                    ),
                )


def salvar_deteccao(hash_: str, saida: SaidaDeteccao) -> None:
    exam_id = db.exam_id_from_hash(hash_)
    if not exam_id:
        return
    for ev in [*saida.eventos_detectados, *saida.comentarios_examinador]:
        db.execute(
            """
            INSERT INTO exam_eventos (
                exam_id, evento_id, categoria, descricao,
                timestamp_video_seg, timestamp_audio_seg, duracao_seg,
                confianca, canal_evidencia, quadrante_origem, camera_origem,
                transcricao, classificacao, contexto
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (exam_id, evento_id) DO NOTHING
            """,
            (
                exam_id,
                ev.evento_id,
                ev.categoria,
                ev.descricao,
                ev.timestamp_video_seg,
                ev.timestamp_audio_seg,
                ev.duracao_seg,
                ev.confianca,
                ev.canal_evidencia,
                ev.quadrante_origem,
                ev.camera_origem,
                ev.transcricao,
                ev.classificacao,
                db.to_jsonb(ev.contexto_adicional),
            ),
        )


def salvar_normativo(hash_: str, saida: SaidaNormativo) -> None:
    exam_id = db.exam_id_from_hash(hash_)
    if not exam_id:
        return
    for enq in saida.enquadramentos:
        db.execute(
            """
            INSERT INTO exam_enquadramentos (
                exam_id, evento_id, enquadrado, regra_aplicada, artigo_ctb,
                ficha_mbedv, natureza, peso, excecao_aplicada, justificativa,
                confianca, requer_revisao_humana, matriz_versao
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (exam_id, evento_id, regra_aplicada) DO NOTHING
            """,
            (
                exam_id,
                enq.evento_id,
                enq.enquadrado,
                enq.regra_aplicada,
                enq.artigo_ctb,
                enq.ficha_mbedv,
                enq.natureza.value if enq.natureza else None,
                enq.peso,
                enq.excecao_aplicada,
                enq.justificativa,
                enq.confianca_enquadramento,
                enq.requer_revisao_humana,
                saida.matriz_versao,
            ),
        )


def salvar_pontuacao(hash_: str, rp: ResultadoPontuacao) -> None:
    db.execute(
        """
        UPDATE exams SET
            resultado_calculado = %s,
            pontuacao_calculada = %s,
            matriz_versao       = %s
        WHERE hash = %s
        """,
        (rp.resultado_calculado.value, rp.pontuacao_calculada, rp.matriz_versao, hash_),
    )


def salvar_divergencia(hash_: str, comp: Comparacao) -> None:
    exam_id = db.exam_id_from_hash(hash_)
    if not exam_id:
        return
    db.execute(
        """
        INSERT INTO exam_divergencias (
            exam_id, tipo_divergencia, subtipos_associados,
            resultado_oficial, resultado_calculado, pontuacao_oficial, pontuacao_calculada,
            concorda_resultado, concorda_pontuacao, concorda_infracoes,
            evidencia_suficiente, encaminhamento, detalhes
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (exam_id) DO UPDATE SET
            tipo_divergencia    = EXCLUDED.tipo_divergencia,
            subtipos_associados = EXCLUDED.subtipos_associados,
            resultado_oficial   = EXCLUDED.resultado_oficial,
            resultado_calculado = EXCLUDED.resultado_calculado,
            pontuacao_oficial   = EXCLUDED.pontuacao_oficial,
            pontuacao_calculada = EXCLUDED.pontuacao_calculada,
            concorda_resultado  = EXCLUDED.concorda_resultado,
            concorda_pontuacao  = EXCLUDED.concorda_pontuacao,
            concorda_infracoes  = EXCLUDED.concorda_infracoes,
            evidencia_suficiente= EXCLUDED.evidencia_suficiente,
            encaminhamento      = EXCLUDED.encaminhamento,
            detalhes            = EXCLUDED.detalhes,
            updated_at          = NOW()
        """,
        (
            exam_id,
            comp.tipo_divergencia.value,
            db.to_jsonb([s.value for s in comp.subtipos_associados]),
            comp.resultado_oficial.value if comp.resultado_oficial else None,
            comp.resultado_calculado.value,
            comp.pontuacao_oficial,
            comp.pontuacao_calculada,
            comp.concorda_resultado,
            comp.concorda_pontuacao,
            comp.concorda_infracoes,
            comp.evidencia_suficiente,
            comp.encaminhamento.value,
            db.to_jsonb(comp.detalhes),
        ),
    )


def salvar_comite(
    hash_: str, laudo: LaudoComite, *, cost_usd: float | None = None, raw: dict | None = None
) -> None:
    exam_id = db.exam_id_from_hash(hash_)
    if not exam_id:
        return
    db.execute(
        """
        INSERT INTO exam_comite_laudos (
            exam_id, comite_versao, tipo_divergencia_analisada,
            tipo_divergencia_pos_comite,
            causas_identificadas, verificacoes_executadas, comentarios_examinador,
            recomendacao_para_auditor, conclusao_comite, resultado_comite,
            tempo_processamento_seg, cost_usd, raw
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            exam_id,
            laudo.comite_versao,
            laudo.tipo_divergencia_analisada.value,
            laudo.tipo_divergencia_pos_comite.value if laudo.tipo_divergencia_pos_comite else None,
            db.to_jsonb([c.model_dump() for c in laudo.causas_identificadas]),
            db.to_jsonb([v.model_dump() for v in laudo.verificacoes_executadas]),
            db.to_jsonb([c.model_dump() for c in laudo.comentarios_examinador_detectados]),
            laudo.recomendacao_para_auditor,
            laudo.conclusao_comite,
            laudo.resultado_comite,  # veredito explícito ③: 'A' | 'R' | None
            laudo.tempo_processamento_seg,
            cost_usd,
            db.to_jsonb(raw) if raw is not None else None,
        ),
    )


def ler_resultado_oficial(hash_: str) -> ResultadoOficial | None:
    """Reconstrói o resultado oficial a partir de ``exams`` + infrações oficiais.

    Usado pelo Motor de Comparação quando o resultado oficial não veio no
    payload da chamada mas já foi persistido por uma ingestão anterior.
    """
    row = db.fetch_one(
        """
        SELECT resultado_exame, pontuacao_oficial, houve_interrupcao, motivo_interrupcao
        FROM exams WHERE hash = %s
        """,
        (hash_,),
    )
    if not row or row.get("resultado_exame") is None:
        return None
    decisao = CODIGO_PARA_RESULTADO.get(
        str(row["resultado_exame"]).upper(), ResultadoExame.NAO_AVALIADO
    )
    exam_id = db.exam_id_from_hash(hash_)
    infracoes: list[InfracaoOficial] = []
    if exam_id:
        for r in db.fetch_all(
            "SELECT artigo_ctb, natureza, peso FROM exam_infracoes_oficiais WHERE exam_id = %s",
            (exam_id,),
        ):
            nat = None
            try:
                nat = Natureza(r["natureza"]) if r.get("natureza") else None
            except ValueError:
                nat = None
            infracoes.append(
                InfracaoOficial(artigo_ctb=r["artigo_ctb"], natureza=nat, peso=r.get("peso"))
            )
    return ResultadoOficial(
        decisao=decisao,
        pontuacao=row.get("pontuacao_oficial"),
        houve_interrupcao=bool(row.get("houve_interrupcao")),
        motivo_interrupcao=row.get("motivo_interrupcao"),
        infracoes=infracoes,
    )
