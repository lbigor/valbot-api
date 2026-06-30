"""Adapta `db.laudo_dossie(hash)` (shape do banco real) → o `dossie` esperado
por `montar_laudo_pdf_view` (mesmo shape de `tests/fixtures/laudo_caso_real.json`).

Ponte entre o pipeline Jinja/WeasyPrint (Laudo PDF v2.0 — `laudo_v2.html`) e o
dossiê real do PostgreSQL (`db.laudo_dossie`, que já junta exam + comitê +
parecer + decisão + trilha de eventos + divergência + enquadramentos).

Princípio: best-effort e HONESTO. Quando o schema real não tem o dado (ex.:
não existe tabela de anotações TPA do examinador; veículo não tem placa/ano
separados), o campo fica `None`/`[]` — nunca inventa valor. `montar_laudo_pdf_view`
já trata ausência com "não informado" via `_g()`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_DECISAO_AUDITOR_LABEL = {
    "concorda": "Concorda com o Val Auditor",
    "discorda": "Diverge do Val Auditor",
}
_DECISAO_SUPERVISOR_LABEL = {
    "homologar": "Homologado (mantém o parecer do Auditor)",
    "reformar": "Reformado (sobrepõe o parecer do Auditor)",
}
_RESULTADO_LABEL = {"aprovado": "APROVADO", "reprovado": "REPROVADO", "a": "APROVADO", "r": "REPROVADO"}


def _parse_dt(v: Any) -> datetime | None:
    """Normaliza datetime (psycopg) OU string ISO-8601 (ex.: vindo de JSON)
    pra um `datetime` real — adapter fica robusto a ambos."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt_dt(v: Any) -> str | None:
    """Formata datetime/string ISO em `dd/mm/aaaa HH:MM:SS`."""
    if v is None:
        return None
    dt = _parse_dt(v)
    return dt.strftime("%d/%m/%Y %H:%M:%S") if dt else str(v)


def _resultado_label(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    return _RESULTADO_LABEL.get(s, str(v).upper())


def _g(d: dict | None, *chaves: str) -> Any:
    d = d or {}
    for k in chaves:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None


def _parecer_auditor(db_dossie: dict) -> dict | None:
    p = db_dossie.get("parecer_auditor")
    if not p:
        return None
    decisao = (p.get("decisao") or "").lower()
    return {
        "responsavel": p.get("auditor") or "Auditor responsável",
        "decisao": decisao,
        "decisao_label": _DECISAO_AUDITOR_LABEL.get(decisao, p.get("decisao") or "—"),
        "resultado_final": _resultado_label(p.get("resultado_final")),
        "justificativa": p.get("justificativa") or "—",
        "referencia_mbedv": p.get("referencia_mbedv"),
        "data": _fmt_dt(p.get("created_at")) or "—",
    }


def _decisao_supervisor(db_dossie: dict) -> dict | None:
    d = db_dossie.get("decisao_supervisor")
    if not d:
        return None
    decisao = (d.get("decisao") or "").lower()
    return {
        "responsavel": d.get("supervisor") or "Supervisor responsável",
        "decisao": decisao,
        "decisao_label": _DECISAO_SUPERVISOR_LABEL.get(decisao, d.get("decisao") or "—"),
        "resultado_final": _resultado_label(d.get("resultado_final")),
        "justificativa": d.get("justificativa") or "—",
        "data": _fmt_dt(d.get("created_at")) or "—",
    }


def _infracoes(db_dossie: dict) -> list[dict]:
    """Junta `enquadramentos` (regra aplicada a um evento) com `eventos`
    (timestamp/câmera/transcrição) por `evento_id`. Só entram enquadramentos
    com `enquadrado=True` — os demais são eventos sem tipificação (ficam de
    fora; o conjunto completo de `eventos` alimenta a timeline/observações,
    não esta lista)."""
    eventos_por_id = {e.get("evento_id"): e for e in (db_dossie.get("eventos") or [])}
    out = []
    for enq in db_dossie.get("enquadramentos") or []:
        if not enq.get("enquadrado"):
            continue
        evt = eventos_por_id.get(enq.get("evento_id")) or {}
        conf = enq.get("confianca")
        if conf is None:
            conf = evt.get("confianca")
        out.append(
            {
                "artigo_ctb": enq.get("artigo_ctb"),
                "ficha_mbedv": enq.get("ficha_mbedv"),
                "severidade": (enq.get("natureza") or "").lower() or None,
                "pontos": enq.get("peso"),
                "ts_seconds": evt.get("timestamp_video_seg") or evt.get("timestamp_audio_seg"),
                "duracao_s": evt.get("duracao_seg"),
                "camera_origem": evt.get("camera_origem"),
                "conduta_observada": evt.get("descricao"),
                "evidencia_audio": evt.get("transcricao") or "",
                "confidence": float(conf) if conf is not None else None,
                "excecao_resultado": "aplicada" if enq.get("excecao_aplicada") else "nao_aplicavel",
                "fundamentacao_ctb": enq.get("justificativa"),
                "requer_revisao_humana": bool(enq.get("requer_revisao_humana")),
                "canal_evidencia": evt.get("canal_evidencia"),
            }
        )
    return out


def _observacoes_conduta(db_dossie: dict) -> list[dict]:
    """`exam_comentarios_compliance` (conduta do examinador/candidato, não
    pontua) → forma esperada pelo contrato (ts_seconds/categoria/classificacao/
    descricao/origem)."""
    out = []
    for c in db_dossie.get("compliance") or []:
        out.append(
            {
                "ts_seconds": c.get("timestamp_s"),
                "categoria": c.get("tipo"),
                "classificacao": c.get("classificacao"),
                "descricao": c.get("transcricao") or c.get("descricao"),
                "origem": "IA análise áudio" if c.get("transcricao") else "IA visão computacional",
            }
        )
    return out


def _subtipos_divergencia(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for s in raw:
        if isinstance(s, dict) and {"tipo", "aplicavel", "justificativa"} & s.keys():
            out.append(s)
    return out


def montar_dossie_de_db(db_dossie: dict) -> dict:
    """`db.laudo_dossie(hash)` → dossiê no shape de `montar_laudo_pdf_view`.

    Função pura (sem I/O). Resiliente: ausência de qualquer bloco do banco
    (OS/comitê/parecer/decisão/divergência) não derruba o mapeamento — vira
    `None`/`[]` no campo correspondente.
    """
    exam = db_dossie.get("exam") or {}
    ordem = db_dossie.get("ordem_servico") or {}
    comite = db_dossie.get("laudo_comite") or {}
    divergencia_db = db_dossie.get("divergencia") or {}
    comite_meta = db_dossie.get("comite_meta") or {}

    candidato = {
        "nome": exam.get("candidato_nome"),
        "cpf": exam.get("candidato_cpf"),
        "renach": exam.get("renach"),
        "processo": exam.get("processo") or exam.get("external_id"),
        "categoria": exam.get("categoria"),
        "tipo_exame": exam.get("tipo_exame"),
        "tentativa": None,  # não há coluna de nº de tentativa no schema atual
    }
    examinador = {
        "nome": exam.get("examinador"),
        "matricula": exam.get("examinador_matricula"),
        "comissao": None,  # comissão examinadora (TechPrático) não está no dossiê
        "eh_preposto": bool(exam.get("examinador_eh_preposto")),
        "historico_auditoria": None,  # exigiria agregação à parte (fora do dossiê)
    }
    veiculo = {
        "placa": None,  # `exams.veiculo` é texto livre (sem placa/ano separados)
        "modelo": exam.get("veiculo"),
        "ano": None,
        "duplo_comando": None,
    }
    unidade = {
        "nome": exam.get("local_unidade") or exam.get("unidade"),
        "endereco": None,
        "codigo": None,
        "auto_escola": exam.get("auto_escola"),
    }
    tempo = {
        "data": _fmt_dt(exam.get("data_hora_exame") or exam.get("created_at")),
        "inicio": None,
        "fim": None,
        "duracao_s": exam.get("duration_s"),
        "trajeto": None,
    }

    resultado_oficial = {
        "decisao": _resultado_label(exam.get("resultado_oficial")),
        "pontuacao": exam.get("pontuacao_oficial") or ordem.get("pontuacao_oficial"),
        "houve_interrupcao": bool(exam.get("houve_interrupcao")),
        "registrado_por": exam.get("examinador"),
        "registrado_em": None,  # sem timestamp específico de registro do oficial
        "exame_prosseguiu": not bool(exam.get("motivo_interrupcao")),
    }
    resultado_calculado = {
        "decisao": _resultado_label(exam.get("resultado_calculado") or exam.get("aprovado")),
        "pontuacao": exam.get("pontuacao_total") or exam.get("pontuacao_calculada"),
        "limite": 10,
        "duracao_s": exam.get("duration_s"),
        "evidencia_suficiente": divergencia_db.get("evidencia_suficiente"),
        "validator_veredito": exam.get("validator_veredito"),
        "layout": {"confianca_layout": exam.get("layout_confianca")},
        "tem_audio": True,
        "tem_telemetria": False,
        "houve_interrupcao": bool(exam.get("houve_interrupcao")),
    }

    infracoes_oficiais = [
        {"artigo_ctb": io.get("artigo_ctb")}
        for io in (db_dossie.get("infracoes_oficiais") or [])
        if io.get("artigo_ctb")
    ]
    infracoes_calc = _infracoes(db_dossie)
    artigos_calc = [i["artigo_ctb"] for i in infracoes_calc if i.get("artigo_ctb")]

    divergencia = {
        "tipo": divergencia_db.get("tipo_divergencia") or ordem.get("tipo_divergencia"),
        "concorda_resultado": divergencia_db.get("concorda_resultado")
        if divergencia_db.get("concorda_resultado") is not None
        else not bool(exam.get("divergente")),
        "houve_interrupcao": bool(exam.get("houve_interrupcao")),
        "artigos_oficiais": [i["artigo_ctb"] for i in infracoes_oficiais],
        "artigos_calculados": artigos_calc,
        "subtipos": _subtipos_divergencia(divergencia_db.get("subtipos_associados")),
    }

    modelo_comite = None
    if comite or comite_meta:
        versao = comite_meta.get("comite_versao")
        modelo_comite = f"val-comite-{versao}" if versao else "val-comite"

    dossie: dict = {
        "candidato": candidato,
        "examinador": examinador,
        "veiculo": veiculo,
        "unidade": unidade,
        "tempo": tempo,
        "resultado_oficial": resultado_oficial,
        "anotacoes_tpa": [],  # não existe tabela de TPA no schema atual
        "resultado_calculado": resultado_calculado,
        "infracoes": infracoes_calc,
        "observacoes_conduta": _observacoes_conduta(db_dossie),
        "divergencia": divergencia,
        "ano": (_parse_dt(exam.get("created_at")).year if _parse_dt(exam.get("created_at")) else None),
        "mes": (_parse_dt(exam.get("created_at")).month if _parse_dt(exam.get("created_at")) else None),
        "emitido_em": _fmt_dt(datetime.now(UTC)),
        "tempo_processamento": (
            f"{comite_meta.get('tempo_processamento_seg')} s"
            if comite_meta.get("tempo_processamento_seg")
            else None
        ),
        "resolucao": None,  # usa o default do contrato (Resolução CONTRAN 1.020/2025)
        "manual_mbedv": None,  # usa o default do contrato (MBEDV)
        "matriz_versao": exam.get("matriz_versao")
        or (db_dossie.get("matriz_vigente") or {}).get("versao"),
        "modelo_ia": exam.get("engine_model") or exam.get("engine_backend"),
        "modelo_comite": modelo_comite,
        "video_hash": exam.get("hash"),
        "assinatura": None,  # usa o default do contrato ([DIFERIDO — ICP-Brasil A1])
        "parecer_auditor": _parecer_auditor(db_dossie),
        "decisao_supervisor": _decisao_supervisor(db_dossie),
    }
    return dossie
