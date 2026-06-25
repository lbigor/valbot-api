"""Loader da Matriz Nacional a partir das fichas reais do MBEDV (spec §4).

Lê ``configs/references/mbedv_fichas.json`` (84 fichas extraídas do PDF oficial)
e mapeia cada ficha para os campos da regra da spec §4.2, populando
``exam_rules`` e registrando a versão consolidada em ``matriz_versoes`` (§4.4).

Idempotente. Roda como módulo: ``python -m backend.matriz.seed_mbedv [--dry-run]``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from backend.core import db

log = logging.getLogger("valbot.matriz.seed")

FICHAS_JSON = Path(__file__).resolve().parents[2] / "configs" / "references" / "mbedv_fichas.json"

GRAV_PESO = {"leve": 1, "media": 2, "grave": 4, "gravissima": 6}

# Detectabilidade herdada da taxonomia (Tier A/B) — só p/ artigos com correspondência
# de detecção atual; o resto fica conservador (revisão humana obrigatória).
_CONF_POR_ARTIGO = {
    "Art. 186": ("alta", False, "visao_computacional + analise_trajetoria"),  # contramão
    "Art. 196": ("media", True, "visao_computacional"),  # seta/sinalização
    "Art. 208": ("alta", False, "visao_computacional"),  # semáforo
    "Art. 207": ("alta", False, "visao_computacional"),  # parada obrigatória
}


def carregar_payload() -> dict:
    if not FICHAS_JSON.exists():
        raise FileNotFoundError(f"Fichas MBEDV não encontradas em {FICHAS_JSON}")
    return json.loads(FICHAS_JSON.read_text(encoding="utf-8"))


def _num_artigo(artigo_ctb: str) -> str:
    m = re.search(r"(\d+)", artigo_ctb or "")
    return m.group(1) if m else "0"


def _codigo_val(fic: dict) -> str:
    num = _num_artigo(fic.get("artigo_ctb", ""))
    inc = (fic.get("inciso") or "").strip()
    return f"VAL-CTB-{num}-{inc}" if inc else f"VAL-CTB-{num}"


def ficha_para_regra(fic: dict) -> dict[str, Any]:
    """Mapeia uma ficha MBEDV → colunas de ``exam_rules`` (spec §4.2)."""
    artigo = fic.get("artigo_ctb", "")
    inc = (fic.get("inciso") or "").strip()
    artigo_full = f"{artigo}, {inc}" if inc and inc not in artigo else artigo
    num_key = f"Art. {_num_artigo(artigo)}"
    conf, revisao, tipo_det = _CONF_POR_ARTIGO.get(num_key, ("baixa", True, "visao_computacional"))
    # Peso variável (Art. 181: gravidade por inciso) → natureza "variavel" + peso nulo.
    peso_var = bool(fic.get("peso_variavel"))
    nat = "variavel" if peso_var else (fic.get("gravidade") or "variavel")
    peso = None if peso_var else fic.get("peso")
    return {
        "codigo_val": _codigo_val(fic),
        "artigo_ctb": artigo_full,
        "ficha_mbedv": f"MBEDV-FICHA-{_num_artigo(artigo)}" + (f"-{inc}" if inc else ""),
        "fonte_normativa": "MBEDV (SENATRAN 01/02/2026) + CTB",
        "natureza": nat,
        "peso": peso,
        "peso_variavel": bool(fic.get("peso_variavel")),
        "categorias_aplicaveis": fic.get("categorias") or ["ACC", "A", "B", "C", "D", "E"],
        "conduta_observavel": fic.get("titulo", ""),
        "descricao": fic.get("descricao", ""),
        "evidencia_necessaria": fic.get("constatacao", ""),
        "constatacao": fic.get("constatacao", ""),
        "informacoes_complementares": fic.get("informacoes_complementares", ""),
        "quando_pontuar": "\n".join(fic.get("condutas_que_pontuam") or []),
        "quando_nao_pontuar": "\n".join(fic.get("condutas_que_nao_pontuam") or []),
        "tipo_deteccao": tipo_det,
        "confiabilidade_deteccao": conf,
        "requer_revisao_humana": bool(revisao or fic.get("peso_variavel")),
        "comentario_juridico": fic.get("definicoes_procedimentos", ""),
        "versao_regra": "v1.0",
        "vigencia_inicio": "2026-02-01",
    }


def regras_canonicas() -> list[dict]:
    """Todas as regras da Matriz como dicts (usado pelo Motor Normativo como
    fonte canônica quando ``exam_rules`` não está populada)."""
    payload = carregar_payload()
    return [ficha_para_regra(f) for f in payload.get("fichas", [])]


# ---------------------------------------------------------------------------
# Seed no banco
# ---------------------------------------------------------------------------

_COLS = [
    "codigo_val",
    "artigo_ctb",
    "ficha_mbedv",
    "fonte_normativa",
    "natureza",
    "peso",
    "peso_variavel",
    "categorias_aplicaveis",
    "conduta_observavel",
    "descricao",
    "evidencia_necessaria",
    "constatacao",
    "informacoes_complementares",
    "quando_pontuar",
    "quando_nao_pontuar",
    "tipo_deteccao",
    "confiabilidade_deteccao",
    "requer_revisao_humana",
    "comentario_juridico",
    "versao_regra",
    "vigencia_inicio",
]


def seed(dry_run: bool = False) -> dict:
    """Popula ``exam_rules`` e registra a versão consolidada. Devolve um resumo."""
    payload = carregar_payload()
    regras = [ficha_para_regra(f) for f in payload.get("fichas", [])]
    versao = payload.get("matriz_versao", "matriz-nacional-v1.0")

    # Conferência (spec §4.2): nada de peso incoerente com natureza.
    for r in regras:
        if r["natureza"] in GRAV_PESO and r["peso"] != GRAV_PESO[r["natureza"]]:
            raise ValueError(f"{r['codigo_val']}: peso {r['peso']} != natureza {r['natureza']}")

    resumo = {
        "versao": versao,
        "total_regras": len(regras),
        "dry_run": dry_run,
        "db": db.db_enabled(),
    }
    if dry_run or not db.db_enabled():
        log.info(
            "seed (dry-run=%s, db=%s): %d regras, versao=%s",
            dry_run,
            db.db_enabled(),
            len(regras),
            versao,
        )
        return resumo

    placeholders = ", ".join(["%s"] * len(_COLS))
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLS if c != "codigo_val")
    for r in regras:
        vals = [db.to_jsonb(r[c]) if c == "categorias_aplicaveis" else r[c] for c in _COLS]
        db.execute(
            f"INSERT INTO exam_rules ({', '.join(_COLS)}) VALUES ({placeholders}) "
            f"ON CONFLICT (codigo_val) DO UPDATE SET {set_clause}",
            tuple(vals),
        )
    # Versão consolidada (snapshot) — §4.4.
    db.execute("UPDATE matriz_versoes SET vigente = FALSE WHERE vigente = TRUE")
    db.execute(
        """
        INSERT INTO matriz_versoes (versao, descricao, snapshot, vigente)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (versao) DO UPDATE SET snapshot = EXCLUDED.snapshot, vigente = TRUE
        """,
        (versao, f"Matriz MBEDV — {len(regras)} fichas", db.to_jsonb(regras)),
    )
    log.info("seed aplicado: %d regras, versao=%s vigente", len(regras), versao)
    return resumo


if __name__ == "__main__":  # pragma: no cover
    import sys

    logging.basicConfig(level=logging.INFO)
    r = seed(dry_run="--dry-run" in sys.argv)
    print(json.dumps(r, ensure_ascii=False))
