"""Testes dos motores determinísticos do backend v2.

Cobrem o núcleo regulatório que NÃO depende de IA/rede: exceções da §3.5
(com destaque para "veículo que morre não pontua"), enquadramento normativo,
cálculo de pontuação (pesos/limite/interrupção) e classificação das 5
divergências (§9).
"""

from __future__ import annotations

import os

os.environ.setdefault("VALBOT_DB_DISABLED", "1")

from backend.engines import comparacao, excecoes, normativo, pontuacao
from backend.models import (
    EventoDetectado,
    InfracaoOficial,
    Natureza,
    ResultadoExame,
    ResultadoOficial,
    TipoDivergencia,
)

# ---------------------------------------------------------------------------
# §3.5 — Eventos que NÃO pontuam
# ---------------------------------------------------------------------------


_seq = {"n": 0}


def _evento(regra_id: str, ctx: dict | None = None) -> EventoDetectado:
    base = {"regra_id": regra_id}
    base.update(ctx or {})
    _seq["n"] += 1
    return EventoDetectado(
        evento_id=f"EV-{_seq['n']:03d}",
        categoria="comportamento",
        descricao="teste",
        timestamp_video_seg=100.0,
        confianca=0.9,
        contexto_adicional=base,
    )


def test_carro_morreu_nao_pontua_por_padrao():
    """Regra DURA: motor calado (R1020-M-c) sem prova de 'sem justa razão' não pontua."""
    ev = _evento("R1020-M-c")
    assert excecoes.avaliar(ev) == "veiculo_morreu_nao_pontua"


def test_motor_interrompido_so_pontua_sem_justa_razao():
    ev = _evento("R1020-M-c", {"sem_justa_razao": True})
    assert excecoes.avaliar(ev) is None  # aí sim é passível de pontuar


def test_flag_explicita_motor_morreu():
    ev = _evento("R1020-G-a", {"motor_morreu": True})
    assert excecoes.avaliar(ev) == "veiculo_morreu_nao_pontua"


def test_baliza_isolada_nao_eliminatoria():
    ev = _evento("R1020-G-c", {"tentativas_baliza": 1})
    assert excecoes.avaliar(ev) == "baliza_isolada_nao_eliminatoria"


def test_emergencia_e_preposto():
    assert excecoes.avaliar(_evento("R1020-G-d", {"havia_emergencia": True})) == "emergencia"
    assert (
        excecoes.avaliar(_evento("R1020-G-d", {"intervencao_preposto": True}))
        == "orientacao_preposto"
    )


def test_conduta_induzida_por_comentario_examinador():
    ev = _evento("R1020-G-d")  # infração @100s
    comentario = EventoDetectado(
        evento_id="EX-001",
        categoria="evento_examinador",
        descricao="Cuidado, vai bater!",
        timestamp_audio_seg=98.0,  # dentro da janela
        classificacao="comentario_inadequado_intimidatorio",
    )
    assert excecoes.conduta_induzida(ev, [comentario]) == "conduta_induzida_comentario_examinador"


# ---------------------------------------------------------------------------
# Motor Normativo + Pontuação (integração do default protetor)
# ---------------------------------------------------------------------------


# Códigos canônicos da Matriz MBEDV (artigos CTB reais):
#   VAL-CTB-169     → leve (1)        Art. 169
#   VAL-CTB-186-I   → grave (4)       Art. 186, I (contramão duplo sentido)
#   VAL-CTB-186-II  → gravíssima (6)  Art. 186, II (contramão sentido único)
#   VAL-CTB-208     → gravíssima (6)  Art. 208 (semáforo/parada obrigatória)


def test_normativo_nao_pontua_carro_morto_e_pontuacao_zero():
    # Motor calou (flag motor_morreu) sobre qualquer regra → exceção §3.5, não pontua.
    eventos = [_evento("VAL-CTB-169", {"motor_morreu": True})]
    norm = normativo.enquadrar(eventos, exame_id="EXM-1", categoria="B")
    enq = norm.enquadramentos[0]
    assert enq.enquadrado is False
    assert enq.excecao_aplicada == "veiculo_morreu_nao_pontua"

    rp = pontuacao.calcular(norm)
    assert rp.pontuacao_calculada == 0
    assert rp.resultado_calculado == ResultadoExame.APROVADO


def test_evento_sem_regra_na_matriz_nao_pontua():
    # Código desconhecido (nem mapeado, nem compliance) → não enquadra → não pontua.
    eventos = [_evento("R1020-DESCONHECIDO")]
    norm = normativo.enquadrar(eventos, exame_id="EXM-1b", categoria="B")
    assert norm.enquadramentos == []
    assert norm.eventos_nao_enquadrados[0].motivo == "evento_observado_sem_enquadramento"
    assert pontuacao.calcular(norm).pontuacao_calculada == 0


def test_conduta_sem_ficha_vira_compliance_nao_pontua():
    # Cinto (R1020-GR-f) não tem ficha MBEDV → vai para compliance, não pontua.
    eventos = [_evento("R1020-GR-f")]
    norm = normativo.enquadrar(eventos, exame_id="EXM-1c", categoria="B")
    assert norm.enquadramentos == []
    assert norm.eventos_nao_enquadrados[0].motivo == "compliance_sem_ficha"
    assert pontuacao.calcular(norm).pontuacao_calculada == 0


def test_pontuacao_soma_pesos_e_limite():
    # grave(4) + gravíssima(6) = 10 → aprovado (limite é ≤10)
    eventos = [_evento("VAL-CTB-186-I"), _evento("VAL-CTB-186-II")]
    norm = normativo.enquadrar(eventos, exame_id="EXM-2", categoria="B")
    rp = pontuacao.calcular(norm)
    assert rp.pontuacao_calculada == 10
    assert rp.resultado_calculado == ResultadoExame.APROVADO


def test_pontuacao_acima_do_limite_reprova():
    # duas gravíssimas = 12 > 10 → reprovado
    eventos = [_evento("VAL-CTB-186-II"), _evento("VAL-CTB-208")]
    norm = normativo.enquadrar(eventos, exame_id="EXM-3", categoria="B")
    rp = pontuacao.calcular(norm)
    assert rp.pontuacao_calculada == 12
    assert rp.resultado_calculado == ResultadoExame.REPROVADO


def test_correspondencia_r1020_para_artigo_ctb():
    # A ponte legada R1020-* → Art. CTB enquadra na Matriz canônica.
    norm = normativo.enquadrar([_evento("R1020-G-d")], exame_id="EXM-3b", categoria="B")
    assert norm.enquadramentos[0].regra_aplicada == "VAL-CTB-186-I"
    assert norm.enquadramentos[0].artigo_ctb.startswith("Art. 186")


def test_interrupcao_vira_categoria_especial():
    norm = normativo.enquadrar([_evento("VAL-CTB-208")], exame_id="EXM-4", categoria="B")
    rp = pontuacao.calcular(norm, houve_interrupcao=True, motivo_interrupcao="imperícia reiterada")
    assert rp.resultado_calculado == ResultadoExame.INTERROMPIDO
    assert rp.pontuacao_calculada is None


# ---------------------------------------------------------------------------
# Motor de Comparação — 5 divergências
# ---------------------------------------------------------------------------


def _calc(resultado: ResultadoExame, pontos: int | None, artigos: list[str] = ()):
    norm = normativo.enquadrar([], exame_id="EXM-C", categoria="B")
    rp = pontuacao.calcular(norm)
    rp.resultado_calculado = resultado
    rp.pontuacao_calculada = pontos
    from backend.models import InfracaoCalculada

    rp.infracoes_calculadas = [
        InfracaoCalculada(artigo_ctb=a, natureza=Natureza.GRAVE, peso=4) for a in artigos
    ]
    return rp


def test_divergencia_resultado():
    calc = _calc(ResultadoExame.APROVADO, 8)
    of = ResultadoOficial(decisao=ResultadoExame.REPROVADO, pontuacao=14)
    comp = comparacao.comparar(calc, of)
    assert comp.tipo_divergencia == TipoDivergencia.RESULTADO
    assert comp.encaminhamento.value == "comite_de_ia"


def test_divergencia_pontuacao():
    calc = _calc(ResultadoExame.REPROVADO, 12)
    of = ResultadoOficial(decisao=ResultadoExame.REPROVADO, pontuacao=14)
    comp = comparacao.comparar(calc, of)
    assert comp.tipo_divergencia == TipoDivergencia.PONTUACAO


def test_divergencia_enquadramento():
    calc = _calc(ResultadoExame.REPROVADO, 8, artigos=["170"])
    of = ResultadoOficial(
        decisao=ResultadoExame.REPROVADO,
        pontuacao=8,
        infracoes=[InfracaoOficial(artigo_ctb="169", natureza=Natureza.GRAVE, peso=4)],
    )
    comp = comparacao.comparar(calc, of)
    assert comp.tipo_divergencia == TipoDivergencia.ENQUADRAMENTO


def test_sem_divergencia_exige_dados_completos():
    # Só afirma "sem divergência" quando há resultado + pontuação + infrações.
    calc = _calc(ResultadoExame.REPROVADO, 4, artigos=["169"])
    of = ResultadoOficial(
        decisao=ResultadoExame.REPROVADO,
        pontuacao=4,
        infracoes=[InfracaoOficial(artigo_ctb="169", natureza=Natureza.GRAVE, peso=4)],
    )
    comp = comparacao.comparar(calc, of)
    assert comp.tipo_divergencia == TipoDivergencia.SEM_DIVERGENCIA
    assert comp.encaminhamento.value == "encerramento"


def test_aprovado_limpo_sem_infracoes_e_sem_divergencia():
    # Aprovado com pontuação 0 e sem infrações é coerente (não é lacuna).
    calc = _calc(ResultadoExame.APROVADO, 0)
    of = ResultadoOficial(decisao=ResultadoExame.APROVADO, pontuacao=0)
    comp = comparacao.comparar(calc, of)
    assert comp.tipo_divergencia == TipoDivergencia.SEM_DIVERGENCIA


def test_dados_oficiais_ausentes_viram_divergencia():
    # Nada oficial veio → NUNCA "sem divergência"; vira evidência insuficiente.
    calc = _calc(ResultadoExame.APROVADO, 8)
    comp = comparacao.comparar(calc, None)
    assert comp.tipo_divergencia == TipoDivergencia.EVIDENCIA_INSUFICIENTE
    assert comp.encaminhamento.value == "comite_de_ia"
    assert "campos_oficiais_ausentes" in comp.detalhes


def test_resultado_concorda_mas_faltam_dados_oficiais():
    # Resultado bate, mas faltam pontuação/infrações oficiais → não dá para
    # afirmar "sem divergência"; vira evidência insuficiente para o humano.
    calc = _calc(ResultadoExame.REPROVADO, 12)
    of = ResultadoOficial(decisao=ResultadoExame.REPROVADO)  # sem pontuacao/infracoes
    comp = comparacao.comparar(calc, of)
    assert comp.tipo_divergencia == TipoDivergencia.EVIDENCIA_INSUFICIENTE
    assert "infracoes_oficiais" in comp.detalhes["campos_oficiais_ausentes"]


def test_evidencia_insuficiente_tem_precedencia():
    calc = _calc(ResultadoExame.APROVADO, 8)
    of = ResultadoOficial(decisao=ResultadoExame.REPROVADO, pontuacao=14)
    comp = comparacao.comparar(calc, of, evidencia_suficiente=False)
    assert comp.tipo_divergencia == TipoDivergencia.EVIDENCIA_INSUFICIENTE
