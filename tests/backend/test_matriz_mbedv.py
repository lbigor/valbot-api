"""Valida a Matriz Nacional canônica extraída do MBEDV (spec §4).

Confere que as 84 fichas reais carregam, que peso bate com gravidade, que todo
campo da spec §4.2 está presente, e que o prompt builder gera bloco com artigos
CTB reais — tudo sem DB (VALBOT_DB_DISABLED=1).
"""

from __future__ import annotations

import os

os.environ.setdefault("VALBOT_DB_DISABLED", "1")

from backend.matriz import correspondencia, prompt_builder, seed_mbedv

GRAV_PESO = {"leve": 1, "media": 2, "grave": 4, "gravissima": 6}

# Campos da regra exigidos pela spec §4.2.
CAMPOS_SPEC = [
    "codigo_val",
    "artigo_ctb",
    "ficha_mbedv",
    "fonte_normativa",
    "natureza",
    "peso",
    "categorias_aplicaveis",
    "conduta_observavel",
    "evidencia_necessaria",
    "quando_pontuar",
    "quando_nao_pontuar",
    "tipo_deteccao",
    "confiabilidade_deteccao",
    "requer_revisao_humana",
    "comentario_juridico",
    "versao_regra",
    "vigencia_inicio",
]


def test_carrega_84_fichas():
    payload = seed_mbedv.carregar_payload()
    assert payload["total_fichas"] == 84
    assert len(payload["fichas"]) == 84
    assert "MBEDV" in payload["fonte"]


def test_regras_tem_todos_os_campos_da_spec_42():
    for r in seed_mbedv.regras_canonicas():
        for campo in CAMPOS_SPEC:
            assert campo in r, f"{r.get('codigo_val')}: falta campo §4.2 {campo}"


def test_peso_coerente_com_gravidade():
    for r in seed_mbedv.regras_canonicas():
        nat = r["natureza"]
        if nat in GRAV_PESO:
            assert r["peso"] == GRAV_PESO[nat], f"{r['codigo_val']}: peso != natureza"
        else:
            # natureza variável (Art. 181) → peso nulo + revisão humana
            assert r["peso"] is None and r["requer_revisao_humana"]


def test_codigos_canonicos_sao_artigos_ctb():
    codigos = {r["codigo_val"] for r in seed_mbedv.regras_canonicas()}
    assert "VAL-CTB-169" in codigos
    assert "VAL-CTB-186-I" in codigos
    assert "VAL-CTB-196" in codigos
    # nenhum ID legado R1020 deve ter sobrado na Matriz canônica
    assert not any(c.startswith("R1020") for c in codigos)


def test_correspondencia_mapeia_legado():
    assert correspondencia.para_codigo_val("R1020-G-d") == "VAL-CTB-186-I"
    assert correspondencia.para_codigo_val("R1020-GR-e") == "VAL-CTB-196"
    assert correspondencia.para_codigo_val("Art. 186") == "VAL-CTB-186"
    assert correspondencia.para_codigo_val("R1020-INEXISTENTE") is None


def test_correspondencia_compliance_nao_pontua():
    # Condutas sem ficha MBEDV → compliance (não mapeiam para Art. CTB).
    assert correspondencia.eh_compliance("R1020-GR-f") is True  # cinto
    assert correspondencia.eh_compliance("R1020-G-c") is True  # baliza
    assert correspondencia.para_codigo_val("R1020-GR-f") is None
    assert correspondencia.eh_compliance("R1020-G-a") is False  # semáforo pontua


def test_mapa_cobre_as_30_condutas():
    # PONTUA + A_VALIDAR + COMPLIANCE = 30 condutas da taxonomia (auditável).
    pontua = set(correspondencia.R1020_PARA_CODIGO_VAL)
    avalidar = set(correspondencia.A_VALIDAR)
    compliance = correspondencia.COMPLIANCE_SEM_FICHA
    assert pontua.isdisjoint(compliance)
    assert len(pontua | avalidar | compliance) == 30


def test_seed_dry_run_valida():
    resumo = seed_mbedv.seed(dry_run=True)
    assert resumo["total_regras"] == 84
    assert resumo["versao"] == "matriz-nacional-v1.0"


def test_prompt_builder_gera_bloco_com_artigos_reais():
    bloco, versao = prompt_builder.construir_bloco(categoria="B")
    assert versao  # versão registrada
    assert "Art. 169" in bloco
    assert "Art. 186" in bloco
    assert "Condutas que NÃO pontuam" in bloco
    assert "MATRIZ NACIONAL" in bloco
