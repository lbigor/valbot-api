"""Testes do adaptador `db.laudo_dossie()` → contrato de `montar_laudo_pdf_view`.

Usa um fixture SINTÉTICO no shape documentado de `db.laudo_dossie` (não há
acesso a banco real neste ambiente de dev) — valida a estrutura/mapeamento de
campos e que o resultado é aceito de ponta a ponta pelo pipeline de render.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.reporting.dossie_adapter import montar_dossie_de_db
from backend.reporting.laudo_pdf_view import montar_laudo_pdf_view

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "db_laudo_dossie_exemplo.json"


@pytest.fixture
def db_dossie() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_adapter_mapeia_identificacao(db_dossie):
    d = montar_dossie_de_db(db_dossie)
    assert d["candidato"]["nome"] == "Maria Lucia dos Santos"
    assert d["candidato"]["cpf"] == "12398798700"
    assert d["candidato"]["renach"] == "SE031229034"
    assert d["examinador"]["nome"] == "Ana Paula de Oliveira"
    assert d["examinador"]["matricula"] == "EX-DETRAN-SE-4521"
    assert d["unidade"]["nome"] == "CTR-SE Aracaju"
    assert d["video_hash"] == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"


def test_adapter_campos_genuinamente_ausentes_ficam_none(db_dossie):
    """O schema real não tem placa/ano de veículo nem TPA — o adapter NUNCA
    inventa valor; fica None/[] e o contrato exibe 'não informado'."""
    d = montar_dossie_de_db(db_dossie)
    assert d["veiculo"]["placa"] is None
    assert d["veiculo"]["ano"] is None
    assert d["anotacoes_tpa"] == []
    assert d["candidato"]["tentativa"] is None


def test_adapter_infracoes_join_enquadramento_evento(db_dossie):
    d = montar_dossie_de_db(db_dossie)
    infs = d["infracoes"]
    assert len(infs) == 2
    por_artigo = {i["artigo_ctb"]: i for i in infs}
    assert por_artigo["Art. 169"]["severidade"] == "leve"
    assert por_artigo["Art. 169"]["pontos"] == 1
    assert por_artigo["Art. 169"]["confidence"] == pytest.approx(0.72)
    assert por_artigo["Art. 193"]["severidade"] == "gravissima"
    assert por_artigo["Art. 193"]["camera_origem"] == "lateral_direita"


def test_adapter_parecer_e_decisao_com_label_e_resultado(db_dossie):
    d = montar_dossie_de_db(db_dossie)
    pa = d["parecer_auditor"]
    assert pa["decisao"] == "discorda"
    assert pa["decisao_label"] == "Diverge do Val Auditor"
    assert pa["resultado_final"] == "APROVADO"
    ds = d["decisao_supervisor"]
    assert ds["decisao_label"] == "Homologado (mantém o parecer do Auditor)"
    assert ds["resultado_final"] == "APROVADO"


def test_adapter_sem_parecer_nem_decisao_fica_none():
    d = montar_dossie_de_db({"exam": {"candidato_nome": "X"}})
    assert d["parecer_auditor"] is None
    assert d["decisao_supervisor"] is None


def test_pipeline_completo_db_ate_contexto_renderizavel(db_dossie):
    """db_dossie → adapter → montar_laudo_pdf_view não quebra e produz os
    8 blocos + checklist + conclusão, com o parecer/decisão refletidos."""
    dossie = montar_dossie_de_db(db_dossie)
    ctx = montar_laudo_pdf_view(dossie)
    for chave in (
        "b1_identificacao",
        "b2_sumario",
        "b3_completa",
        "b7_infracoes",
        "checklist_anexo_k",
        "conclusao",
        "parecer_auditor",
        "decisao_supervisor",
    ):
        assert chave in ctx
    assert len(ctx["b7_infracoes"]["infracoes"]) == 2
    assert ctx["parecer_auditor"]["resultado_final"] == "APROVADO"
    texto = " ".join(ctx["conclusao"])
    assert "considerou o candidato APROVADO" in texto
    assert "homologou o parecer do Auditor" in texto


def test_conclusao_reflete_resultado_final_revertido(db_dossie):
    """Regressão: o Val Auditor calculou REPROVADO, mas o Auditor discordou e
    o Supervisor homologou APROVADO (fixture). A frase de conclusão TEM de
    publicar APROVADO — nunca restatar cegamente o resultado calculado pela IA
    quando a decisão humana o reverteu (seria um erro factual grave no laudo)."""
    dossie = montar_dossie_de_db(db_dossie)
    ctx = montar_laudo_pdf_view(dossie)
    assert ctx["b5_resultado_calculado"]["decisao"] == "REPROVADO"  # IA original
    ultimo_paragrafo = ctx["conclusao"][-1]
    assert "APROVADO" in ultimo_paragrafo
    assert "REPROVADO" not in ultimo_paragrafo


def test_pipeline_renderiza_html(db_dossie):
    from src.reporting.render_laudo_v2 import render_html

    dossie = montar_dossie_de_db(db_dossie)
    ctx = montar_laudo_pdf_view(dossie)
    html = render_html(ctx)
    assert "Maria" in html or "M***" in html  # LGPD mascara por padrão
    assert "Situação: Registrado" in html  # parecer do auditor preenchido
    assert "Situação: Registrada" in html  # decisão do supervisor preenchida
