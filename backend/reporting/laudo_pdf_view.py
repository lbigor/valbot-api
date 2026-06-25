"""Projeção do laudo nos 8 blocos do layout PDF oficial (mockup do Rodrigo).

O laudo canônico tem 12 blocos (spec `docs/specs/laudo-v2/`); o PDF oficial os
apresenta condensados em 8 blocos visuais. Este módulo recebe um *dossiê* do
exame (dict tolerante — campos ausentes viram "não informado") e produz o
contexto pronto para o template Jinja `templates/laudo_v2.html`.

Tudo é determinístico: textos vêm de `textos_laudo`, classificações de
`regras_laudo`, checklist de `checklist_anexo_k`. Nenhuma prosa é gerada por IA
aqui — o documento é reproduzível byte a byte para a mesma entrada (exceto o
campo `emitido_em`, que o chamador fixa).
"""

from __future__ import annotations

from backend.reporting import regras_laudo as R  # noqa: N812
from backend.reporting import textos_laudo as T  # noqa: N812
from backend.reporting.checklist_anexo_k import montar_checklist
from backend.reporting.laudo import _mascarar_cpf, hash_relatorio

NAO_INFORMADO = "não informado"


# ── helpers de formatação (puros) ──


def _fmt_mmss(seg) -> str:
    try:
        s = int(float(seg))
    except (TypeError, ValueError):
        return "—"
    m, s = divmod(max(s, 0), 60)
    return f"{m:02d}:{s:02d}"


def _g(d: dict | None, *chaves, default=NAO_INFORMADO):
    """Primeiro valor não-vazio entre as chaves; senão default."""
    d = d or {}
    for k in chaves:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return default


def _mascarar_cpf_forte(cpf: str | None) -> str:
    """LGPD nível laudo oficial: ``12398798700`` → ``***.***.987-**``.

    Mais restritiva que ``_mascarar_cpf`` (que revela os 6 dígitos do meio):
    expõe só o 3º grupo. Já mascarado / formato inesperado → cai no helper
    canônico reaproveitado.
    """
    if not cpf:
        return NAO_INFORMADO
    if "*" in cpf:
        return cpf
    d = "".join(c for c in cpf if c.isdigit())
    if len(d) == 11:
        return f"***.***.{d[6:9]}-**"
    return _mascarar_cpf(cpf) or NAO_INFORMADO


def _mascarar_nome(nome: str | None) -> str:
    """LGPD: 'Maria Lucia dos Santos' → 'M*** L*** dos S***' (doc §6.2)."""
    if not nome:
        return NAO_INFORMADO
    if "*" in nome:
        return nome
    pequenas = {"de", "da", "do", "dos", "das", "e"}
    partes = []
    for p in nome.split():
        partes.append(p if p.lower() in pequenas else f"{p[0]}***")
    return " ".join(partes)


def _classes_conduta(observacoes: list[dict] | None) -> tuple[int, list[dict]]:
    """Separa conduta inadequada (sinal de compliance, contado à parte) dos
    eventos contextuais sem enquadramento (Bloco 5/7).

    Devolve (n_comentarios_inadequados, eventos_sem_enquadramento). Comentários
    inadequados da examinadora NÃO entram na tabela de eventos sem enquadramento
    — viram indicador próprio (constitution §V: não pontuam o candidato) e
    permanecem na linha do tempo.
    """
    n_inadequados = 0
    eventos = []
    for o in observacoes or []:
        classif = (o.get("classificacao") or "").lower()
        if classif == "inadequado":
            n_inadequados += 1
            continue
        eventos.append(o)
    return n_inadequados, eventos


def montar_laudo_pdf_view(dossie: dict, *, versao_controlada: bool = False) -> dict:
    """Constrói o contexto de 8 blocos para o template PDF a partir do dossiê.

    `versao_controlada=False` (padrão) mascara candidato/examinador por LGPD; em
    ambiente controlado da Comissão, `True` exibe os dados integrais.
    """
    candidato = dossie.get("candidato") or {}
    examinador = dossie.get("examinador") or {}
    veiculo = dossie.get("veiculo") or {}
    unidade = dossie.get("unidade") or {}
    tempo = dossie.get("tempo") or {}
    rof = dossie.get("resultado_oficial") or {}
    rcalc = dossie.get("resultado_calculado") or {}
    divergencia = dossie.get("divergencia") or {}
    infracoes_in = dossie.get("infracoes") or []
    observacoes = dossie.get("observacoes_conduta") or []
    anotacoes_tpa = dossie.get("anotacoes_tpa") or []

    tipo_div = divergencia.get("tipo")
    concorda_resultado = bool(divergencia.get("concorda_resultado", True))
    houve_interrupcao = bool(rof.get("houve_interrupcao") or rcalc.get("houve_interrupcao"))
    # Interrupção só pinta o semáforo de roxo se foi CONFIRMADA (encerrou o exame).
    # Tipificação registrada mas com o exame prosseguindo é inconclusiva → divergência.
    interrupcao_confirmada = houve_interrupcao and not bool(rof.get("exame_prosseguiu"))
    n_inadequados, eventos_conduta = _classes_conduta(observacoes)
    tem_conduta_inadequada = n_inadequados > 0

    artigos_oficiais = divergencia.get("artigos_oficiais") or [
        i.get("artigo_ctb") for i in (rof.get("infracoes") or []) if i.get("artigo_ctb")
    ]
    artigos_calculados = divergencia.get("artigos_calculados") or [
        i.get("artigo_ctb") for i in infracoes_in if i.get("artigo_ctb")
    ]

    # ── infrações numeradas (INF-NNN) + campos derivados ──
    confidences = [i.get("confidence") for i in infracoes_in if i.get("confidence") is not None]
    conf_pct, conf_label = R.confianca_agregada(confidences)
    infracoes = []
    for inf in R.numerar_infracoes(infracoes_in):
        sev = (inf.get("severidade") or "").lower()
        rec = R.recomendacao_tecnica(
            confidence=inf.get("confidence"),
            requer_revisao_humana=bool(inf.get("requer_revisao_humana")),
            canal_evidencia=inf.get("canal_evidencia"),
        )
        excecao = T.frase_excecao(
            ficha=inf.get("ficha_mbedv"),
            excecao_texto=inf.get("excecao_ficha_texto"),
            resultado=inf.get("excecao_resultado"),
        )
        infracoes.append(
            {
                "inf_id": inf["inf_id"],
                "artigo_ctb": _g(inf, "artigo_ctb"),
                "ficha_mbedv": _g(inf, "ficha_mbedv"),
                "severidade": sev,
                "severidade_label": sev.upper(),
                "cor": R.cor_severidade(sev),
                "pontos": inf.get("pontos"),
                "timestamp_fmt": _fmt_mmss(inf.get("ts_seconds", inf.get("timestamp_s"))),
                "duracao_s": inf.get("duracao_s"),
                "camera_origem": _g(inf, "camera_origem"),
                "conduta_observada": _g(inf, "conduta_observada", "evidence", "evidencia"),
                "evidencia_audio": inf.get("evidencia_audio") or "",
                "confianca_pct": round(float(inf.get("confidence", 0)) * 100),
                "excecoes_analisadas": excecao,
                "fundamentacao_ctb": _g(inf, "fundamentacao_ctb", "penalidade"),
                "recomendacao_tecnica": rec,
            }
        )

    # ── eventos sem enquadramento (observações contextuais) ──
    eventos_sem_enquadramento = [
        {
            "timestamp_fmt": _fmt_mmss(o.get("ts_seconds", o.get("timestamp_s"))),
            "categoria": _g(o, "categoria"),
            "observacao": _g(o, "descricao", "descricao_factual", "transcricao_audio"),
            "origem": _g(o, "origem"),
        }
        for o in eventos_conduta
    ]

    # ── checklist Anexo K (Bloco 10, condensado no layout) ──
    checklist = montar_checklist(
        {
            "layout_confianca": (rcalc.get("layout") or {}).get("confianca_layout"),
            "evidencia_suficiente": rcalc.get("evidencia_suficiente"),
            "validator_veredito": rcalc.get("validator_veredito"),
            "conduta_inadequada": tem_conduta_inadequada,
            "duracao_s": rcalc.get("duracao_s") or tempo.get("duracao_s"),
        }
    )

    # ── linha do tempo consolidada (Bloco 8) ──
    linha_tempo = _linha_do_tempo(infracoes_in, anotacoes_tpa, observacoes, tempo)

    # ── Bloco 1 — Identificação do laudo ──
    tem_comite = bool(dossie.get("modelo_comite") or dossie.get("comite_de_ia"))
    b1 = {
        "codigo_laudo": R.codigo_laudo(
            ano=int(dossie.get("ano") or 0),
            mes=int(dossie.get("mes") or 0),
            video_hash=dossie.get("video_hash"),
        ),
        "versao": "FINAL (após processamento do Comitê)" if tem_comite else "PRELIMINAR (pós-Val)",
        "emitido_em": _g(dossie, "emitido_em"),
        "tempo_processamento": _g(dossie, "tempo_processamento"),
        "resolucao": _g(dossie, "resolucao", default="Resolução CONTRAN nº 1.020/2025"),
        "manual_mbedv": _g(dossie, "manual_mbedv", default="MBEDV"),
        "matriz_versao": _g(dossie, "matriz_versao"),
        "modelo_ia": _g(dossie, "modelo_ia"),
        "modelo_comite": _g(dossie, "modelo_comite"),
        "video_hash": _g(dossie, "video_hash"),
        "assinatura": _g(dossie, "assinatura", default="[DIFERIDO — ICP-Brasil A1]"),
    }

    # ── Bloco 2 — Sumário executivo ──
    semaforo = R.cor_semaforo(
        concorda_resultado=concorda_resultado,
        tipo_divergencia=tipo_div,
        houve_interrupcao=interrupcao_confirmada,
    )
    b2 = {
        "semaforo": semaforo,
        "rotulo_divergencia": R.rotulo_divergencia(tipo_div),
        "resultado_oficial": (_g(rof, "decisao") or "").upper(),
        "resultado_calculado": (_g(rcalc, "decisao") or "").upper(),
        "pontuacao_oficial": rof.get("pontuacao"),
        "pontuacao_calculada": rcalc.get("pontuacao"),
        "limite": rcalc.get("limite", 10),
        "veredito_agregado": T.veredito_agregado(
            tipo_divergencia=tipo_div,
            concorda_resultado=concorda_resultado,
            resultado_oficial=rof.get("decisao"),
            resultado_calculado=rcalc.get("decisao"),
            artigos_oficiais=artigos_oficiais,
            artigos_calculados=artigos_calculados,
        ),
        "indicadores": [
            {"label": "Duração", "valor": _fmt_mmss(tempo.get("duracao_s"))},
            {"label": "Infrações IA", "valor": f"{len(infracoes)} detectadas"},
            {"label": "Qualidade técnica", "valor": checklist["indicador"]},
            {"label": "Conduta examinadora", "valor": f"{n_inadequados} inadequado(s)"},
            {"label": "Confiança agregada", "valor": f"{conf_pct}% ({conf_label})"},
        ],
        "encaminhamento": T.recomendacao_encaminhamento(
            tipo_divergencia=tipo_div, tem_conduta_inadequada=tem_conduta_inadequada
        ),
    }

    # ── Bloco 3 — Identificação completa ──
    nome_cand = candidato.get("nome")
    cpf_cand = candidato.get("cpf")
    b3 = {
        "candidato": {
            "nome": nome_cand if versao_controlada else _mascarar_nome(nome_cand),
            "cpf": cpf_cand if versao_controlada else _mascarar_cpf_forte(cpf_cand),
            "renach": _g(candidato, "renach"),
            "processo": _g(candidato, "processo"),
            "categoria": _g(candidato, "categoria"),
            "tipo_exame": _g(candidato, "tipo_exame"),
            "tentativa": _g(candidato, "tentativa"),
        },
        "examinador": {
            "nome": examinador.get("nome")
            if versao_controlada
            else _mascarar_nome(examinador.get("nome")),
            "matricula": _g(examinador, "matricula"),
            "comissao": _g(examinador, "comissao"),
            "eh_preposto": "Sim" if examinador.get("eh_preposto") else "Não",
            "historico_auditoria": _g(examinador, "historico_auditoria"),
        },
        "veiculo": {
            "placa": _g(veiculo, "placa"),
            "modelo": _g(veiculo, "modelo"),
            "ano": _g(veiculo, "ano"),
            "duplo_comando": "Sim"
            if veiculo.get("duplo_comando")
            else _g(veiculo, "duplo_comando"),
        },
        "unidade": {
            "nome": _g(unidade, "nome"),
            "endereco": _g(unidade, "endereco"),
            "codigo": _g(unidade, "codigo"),
            "auto_escola": _g(unidade, "auto_escola"),
        },
        "tempo": {
            "data": _g(tempo, "data"),
            "inicio": _g(tempo, "inicio"),
            "fim": _g(tempo, "fim"),
            "duracao": _g(tempo, "duracao", default=_fmt_mmss(tempo.get("duracao_s"))),
            "trajeto": _g(tempo, "trajeto"),
        },
        "lgpd_nota": (
            "Versão controlada (Comissão) — dados integrais."
            if versao_controlada
            else "Dados pessoais mascarados conforme LGPD. Versão integral em ambiente controlado."
        ),
    }

    # ── Bloco 4 — Resultado oficial detalhado ──
    pont_tpa = sum(int(a.get("pontos") or 0) for a in anotacoes_tpa) if anotacoes_tpa else None
    b4 = {
        "decisao": (_g(rof, "decisao") or "").upper(),
        "pontuacao": _g(rof, "pontuacao", default="Não detalhada no payload"),
        "houve_interrupcao": _g(
            rof, "houve_interrupcao_texto", default="Sim" if houve_interrupcao else "Não"
        ),
        "registrado_por": _g(rof, "registrado_por"),
        "registrado_em": _g(rof, "registrado_em"),
        "anotacoes_tpa": [
            {
                "tempo": _g(a, "tempo", default=_fmt_mmss(a.get("ts_seconds"))),
                "categoria": _g(a, "categoria"),
                "texto": _g(a, "texto", "anotacoes"),
            }
            for a in anotacoes_tpa
        ],
        "observacao_tecnica": T.observacao_tecnica_registro_oficial(
            pontuacao_tpa=pont_tpa,
            limite=rcalc.get("limite", 10),
            houve_interrupcao_registrada=houve_interrupcao,
            exame_prosseguiu=bool(rof.get("exame_prosseguiu")),
        ),
    }

    # ── Bloco 5 — Resultado calculado ──
    b5 = {
        "decisao": (_g(rcalc, "decisao") or "").upper(),
        "pontuacao": rcalc.get("pontuacao"),
        "limite": rcalc.get("limite", 10),
        "num_infracoes": len(infracoes),
        "eventos_sem_enquadramento": len(eventos_sem_enquadramento),
        "confianca_agregada": f"{conf_pct}% — {conf_label.capitalize()}",
        "camadas_tecnicas": R.camadas_tecnicas(
            rcalc.get("layout"),
            tem_audio=rcalc.get("tem_audio", True),
            tem_telemetria=rcalc.get("tem_telemetria", False),
        ),
    }

    # ── Bloco 6 — Análise de divergência ──
    b6 = {
        "rotulo": R.rotulo_divergencia(tipo_div),
        "subtipos": divergencia.get("subtipos") or [],
        "justificativa": T.justificativa_divergencia(
            tipo_divergencia=tipo_div,
            artigos_oficiais=artigos_oficiais,
            artigos_calculados=artigos_calculados,
            pontuacao_oficial=rof.get("pontuacao"),
            pontuacao_calculada=rcalc.get("pontuacao"),
            limite=rcalc.get("limite", 10),
            tem_conduta_inadequada=tem_conduta_inadequada,
        ),
    }

    # ── Bloco 7 — Detalhamento das infrações ──
    b7 = {"infracoes": infracoes, "eventos_sem_enquadramento": eventos_sem_enquadramento}

    contexto = {
        "cabecalho": {
            "titulo": "VAL AUDITOR EXAMES",
            "subtitulo": "Laudo Técnico de Auditoria — Exame Prático de Direção Veicular CNH",
            "resolucao_ref": "Resolução CONTRAN 1.020/2025 + MBEDV",
            "estrutura": "Estrutura v2.0",
            "matriz_label": _g(dossie, "matriz_versao", default="matriz-nacional"),
        },
        "b1_identificacao": b1,
        "b2_sumario": b2,
        "b3_completa": b3,
        "b4_resultado_oficial": b4,
        "b5_resultado_calculado": b5,
        "b6_divergencia": b6,
        "b7_infracoes": b7,
        "b8_linha_tempo": linha_tempo,
        "checklist_anexo_k": checklist,
    }
    # integridade — hash do conteúdo (reúso do helper canônico).
    contexto["b1_identificacao"]["hash_laudo"] = hash_relatorio({"contexto": contexto})
    return contexto


# ── Bloco 8 — linha do tempo consolidada ──

_TIPO_COR = {
    "infracao": "infracao",
    "anotacao_tpa": "tpa",
    "audio_examinador": "audio_inadequado",
    "comportamento": "neutro",
    "trajetoria": "neutro",
    "sistema": "sistema",
}


def _linha_do_tempo(
    infracoes: list[dict],
    anotacoes_tpa: list[dict],
    observacoes: list[dict],
    tempo: dict,
) -> list[dict]:
    """Funde infrações, anotações TPA, observações e marcos num eixo temporal.

    Saída ordenada por timestamp; cada evento tem tipo, origem, descrição e
    cor — os 8 tipos da spec (FR-LAU-08), condensados.
    """
    dur = None
    try:
        dur = float(tempo.get("duracao_s"))
    except (TypeError, ValueError):
        dur = None

    eventos: list[dict] = [
        {
            "ts": 0.0,
            "tipo": "sistema",
            "origem": "Sistema",
            "descricao": "Início do exame",
            "cor": "sistema",
        }
    ]
    for inf in infracoes:
        ts = inf.get("ts_seconds", inf.get("timestamp_s"))
        eventos.append(
            {
                "ts": float(ts) if isinstance(ts, (int, float)) else None,
                "tipo": "Infração",
                "origem": "Motor Normativo",
                "descricao": f"{inf.get('artigo_ctb', '—')} — {inf.get('conduta_observada', inf.get('evidence', ''))}",
                "cor": "infracao",
            }
        )
    for a in anotacoes_tpa:
        ts = a.get("ts_seconds")
        eventos.append(
            {
                "ts": float(ts) if isinstance(ts, (int, float)) else _seg_de_mmss(a.get("tempo")),
                "tipo": "Anotação TPA",
                "origem": "Examinadora",
                "descricao": f"{a.get('categoria', '')}: {a.get('texto', a.get('anotacoes', ''))}".strip(
                    ": "
                ),
                "cor": "tpa",
            }
        )
    for o in observacoes:
        ts = o.get("ts_seconds", o.get("timestamp_s"))
        classif = (o.get("classificacao") or "").lower()
        eventos.append(
            {
                "ts": float(ts) if isinstance(ts, (int, float)) else None,
                "tipo": "Áudio inadeq."
                if classif == "inadequado"
                else (o.get("categoria") or "Observação"),
                "origem": o.get("origem") or "IA",
                "descricao": o.get("descricao") or o.get("transcricao_audio") or "",
                "cor": "audio_inadequado" if classif == "inadequado" else "neutro",
            }
        )
    if dur:
        eventos.append(
            {
                "ts": dur,
                "tipo": "sistema",
                "origem": "Examinadora",
                "descricao": "Encerramento do exame",
                "cor": "sistema",
            }
        )

    eventos.sort(key=lambda e: e["ts"] if e["ts"] is not None else float("inf"))
    for e in eventos:
        e["tempo_fmt"] = _fmt_mmss(e["ts"]) if e["ts"] is not None else "—"
        e["pct"] = round((e["ts"] / dur) * 100, 2) if (dur and e["ts"] is not None) else None
    return eventos


def _seg_de_mmss(valor: str | None) -> float | None:
    if not valor or ":" not in str(valor):
        return None
    try:
        m, s = str(valor).split(":")[:2]
        return int(m) * 60 + int(s)
    except ValueError:
        return None
