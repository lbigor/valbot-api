"""Testes do Laudo v2.0 (8 blocos) — determinismo, regras puras e render HTML.

O teste-âncora é o de DETERMINISMO: um laudo oficial do DETRAN tem de produzir
o mesmo documento para a mesma entrada. Os demais cobrem as regras determinísticas
(semáforo, INF-NNN, recomendação técnica, checklist) e o render do template.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.reporting import regras_laudo as R  # noqa: N812
from backend.reporting.checklist_anexo_k import montar_checklist
from backend.reporting.laudo_pdf_view import montar_laudo_pdf_view

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "laudo_caso_real.json"


@pytest.fixture
def dossie() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── Determinismo (o requisito central do documento oficial) ──


def test_view_e_deterministica(dossie):
    v1 = montar_laudo_pdf_view(dossie)
    v2 = montar_laudo_pdf_view(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert json.dumps(v1, sort_keys=True, ensure_ascii=False) == json.dumps(
        v2, sort_keys=True, ensure_ascii=False
    )


def test_hash_laudo_estavel(dossie):
    h1 = montar_laudo_pdf_view(dossie)["b1_identificacao"]["hash_laudo"]
    h2 = montar_laudo_pdf_view(dossie)["b1_identificacao"]["hash_laudo"]
    assert h1 == h2 and h1.startswith("sha256:")


def test_view_nao_muta_entrada(dossie):
    original = json.loads(FIXTURE.read_text(encoding="utf-8"))
    montar_laudo_pdf_view(dossie)
    assert dossie == original  # nenhuma mutação do dossiê de entrada


# ── Estrutura dos 8 blocos a partir do caso real ──


def test_oito_blocos_presentes(dossie):
    v = montar_laudo_pdf_view(dossie)
    for chave in (
        "b1_identificacao",
        "b2_sumario",
        "b3_completa",
        "b4_resultado_oficial",
        "b5_resultado_calculado",
        "b6_divergencia",
        "b7_infracoes",
        "b8_linha_tempo",
    ):
        assert chave in v, f"bloco ausente: {chave}"


def test_codigo_laudo_do_mockup(dossie):
    v = montar_laudo_pdf_view(dossie)
    assert v["b1_identificacao"]["codigo_laudo"] == "VAL-LAU-2026-06-76FD9ED62196"


def test_versao_final_com_comite(dossie):
    v = montar_laudo_pdf_view(dossie)
    assert v["b1_identificacao"]["versao"].startswith("FINAL")


def test_infracoes_numeradas_e_recomendacao(dossie):
    inf = montar_laudo_pdf_view(dossie)["b7_infracoes"]["infracoes"]
    assert [i["inf_id"] for i in inf] == ["INF-001", "INF-002"]
    # INF-001 (Art.169, 72%) → REVISAR; INF-002 (Art.193, 94%) → CONFIRMAR
    por_artigo = {i["artigo_ctb"]: i["recomendacao_tecnica"] for i in inf}
    assert por_artigo["Art. 169"] == R.REC_REVISAR
    assert por_artigo["Art. 193"] == R.REC_CONFIRMAR


def test_conduta_inadequada_contada_a_parte(dossie):
    v = montar_laudo_pdf_view(dossie)
    indicadores = {i["label"]: i["valor"] for i in v["b2_sumario"]["indicadores"]}
    assert indicadores["Conduta examinadora"] == "1 inadequado(s)"
    # 3 eventos contextuais (neutros/adequados), inadequado fica fora da tabela
    assert v["b5_resultado_calculado"]["eventos_sem_enquadramento"] == 3
    assert len(v["b7_infracoes"]["eventos_sem_enquadramento"]) == 3


def test_semaforo_divergencia_tipo4(dossie):
    v = montar_laudo_pdf_view(dossie)
    # Tipo 4 (enquadramento) → laranja; sem interrupção confirmada
    assert v["b2_sumario"]["semaforo"] == R.SEMAFORO_LARANJA
    assert v["b2_sumario"]["rotulo_divergencia"] == "TIPO 4 (Enquadramento)"


def test_lgpd_mascara_por_padrao(dossie):
    v = montar_laudo_pdf_view(dossie)
    assert v["b3_completa"]["candidato"]["nome"] == "M*** L*** dos S***"
    assert v["b3_completa"]["candidato"]["cpf"] == "***.***.987-**"
    # versão controlada expõe o nome integral
    vc = montar_laudo_pdf_view(dossie, versao_controlada=True)
    assert vc["b3_completa"]["candidato"]["nome"] == "Maria Lucia dos Santos"


def test_timeline_ordenada_com_inadequado(dossie):
    eventos = montar_laudo_pdf_view(dossie)["b8_linha_tempo"]
    ts = [e["ts"] for e in eventos if e["ts"] is not None]
    assert ts == sorted(ts)  # ordenada por tempo
    tipos = {e["tipo"] for e in eventos}
    assert "Áudio inadeq." in tipos  # inadequado permanece na timeline
    assert any(e["tipo"] == "Anotação TPA" for e in eventos)


def test_conclusao_textual_e_deterministica(dossie):
    v = montar_laudo_pdf_view(dossie)
    concl = v["conclusao"]
    assert isinstance(concl, list) and len(concl) >= 3
    texto = " ".join(concl)
    # narrativa cobre as etapas do processo, com o resultado real
    assert v["b1_identificacao"]["codigo_laudo"] in texto
    assert "Comissão Examinadora" in texto and "Val Auditor" in texto and "Comitê Val" in texto
    assert "REPROVADO" in texto
    # etapas humanas pendentes neste fixture (sem parecer/decisão no dossiê)
    assert v["parecer_auditor"] is None and v["decisao_supervisor"] is None
    assert "Auditor" in texto and "Supervisor" in texto
    # determinística + sem jargão interno vazado no documento oficial
    assert montar_laudo_pdf_view(dossie)["conclusao"] == concl
    assert "constitution" not in texto


# ── Regras puras determinísticas ──


@pytest.mark.parametrize(
    "kwargs,esperado",
    [
        ({"concorda_resultado": True, "tipo_divergencia": None}, R.SEMAFORO_VERDE),
        ({"concorda_resultado": False, "tipo_divergencia": "1_resultado"}, R.SEMAFORO_VERMELHO),
        ({"concorda_resultado": True, "tipo_divergencia": "2_pontuacao"}, R.SEMAFORO_LARANJA),
        ({"concorda_resultado": True, "tipo_divergencia": "4_enquadramento"}, R.SEMAFORO_LARANJA),
        (
            {"concorda_resultado": True, "tipo_divergencia": "5_evidencia_insuficiente"},
            R.SEMAFORO_CINZA,
        ),
        (
            {
                "concorda_resultado": False,
                "tipo_divergencia": "1_resultado",
                "houve_interrupcao": True,
            },
            R.SEMAFORO_ROXO,
        ),
    ],
)
def test_cor_semaforo(kwargs, esperado):
    assert R.cor_semaforo(**kwargs) == esperado


def test_item_critico():
    assert all(R.item_critico(n) for n in (1, 2, 8, 9, 10))
    assert not any(R.item_critico(n) for n in (3, 4, 5, 6, 7, 11, 12))


def test_confianca_agregada():
    assert R.confianca_agregada([0.94, 0.72]) == (83, "alta")
    assert R.confianca_agregada([0.65]) == (65, "media")
    assert R.confianca_agregada([]) == (0, "baixa")


def test_codigo_laudo_sem_hash():
    assert R.codigo_laudo(ano=2026, mes=6, video_hash=None) == "VAL-LAU-2026-06-XXXXXXXXXXXX"


# ── Checklist Anexo K ──


def test_checklist_critico_escala():
    chk = montar_checklist({"conduta_inadequada": True, "layout_confianca": 0.5})
    assert chk["total"] == 12
    assert chk["escalou_auditor"] is True  # item 8/9 (crítico) falha com layout baixo
    # biometria (item 1) sempre requer verificação humana
    item1 = next(i for i in chk["itens"] if i["numero"] == 1)
    assert item1["veredito"] == "requer_verificacao_humana"


# ── Render HTML (sem depender de WeasyPrint) ──


def test_render_html_tem_todos_os_blocos(dossie):
    from src.reporting.render_laudo_v2 import render_html

    html = render_html(montar_laudo_pdf_view(dossie))
    # Laudo v2.0 redesenhado: títulos de bloco (8 blocos canônicos + Anexo K + Glossário)
    for titulo in (
        "Identificação do Laudo",
        "Sumário Executivo",
        "Identificação Completa",
        "Resultado Oficial Detalhado",
        "Resultado Calculado pelo Val Auditor",
        "Análise de Divergência",
        "Detalhamento das Infrações",
        "Linha do Tempo do Exame",
        "Checklist Técnico — Anexo K",
        "Glossário e Notas Técnicas",
    ):
        assert titulo in html, f"bloco ausente no HTML: {titulo}"
    # transcrição literal de áudio entre aspas presente no corpo
    assert "pelo amor de Deus" in html
    assert "Estrutura v2.0" in html
