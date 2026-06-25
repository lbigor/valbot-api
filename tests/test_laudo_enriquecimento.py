"""Regressão do enriquecimento conservador do laudo-json.

As funções de enriquecimento (`_enriquecer_infracao`, `_enriquecer_evento` e
os helpers `_fmt_mmss`/`_conf_pct`/`_norm_camera_label`/`_camera_label_legivel`)
acrescentam campos DERIVADOS por infração/evento (ângulo de câmera, tempo
formatado, % de confiança, posição relativa) SEM remover nem sobrescrever nada
que já exista no registro cru.

Estes testes travam o build se alguém quebrar essa garantia conservadora:
- formatação mm:ss / hh:mm:ss correta e resiliente a lixo;
- confiança normalizada (fração 0–1 OU já-percentual) → inteiro 0–100;
- inferência quadrante⇄câmera consistente com o layout do pipeline;
- campos crus PRESERVADOS (precedência do registro original).

Carregamos só os helpers via AST para não exigir o FastAPI no ambiente de CI
(mesma estratégia leve dos demais testes deste diretório).
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

_SERVER = Path(__file__).resolve().parents[1] / "tooling" / "api_stub" / "server.py"
_WANT_FUNCS = {
    "_fmt_mmss",
    "_conf_pct",
    "_norm_camera_label",
    "_camera_label_legivel",
    "_enriquecer_infracao",
    "_enriquecer_evento",
}
_WANT_CONSTS = {"_QUADRANTE_CAMERA", "_CAMERA_QUADRANTE", "_CAMERA_LABEL"}


@pytest.fixture(scope="module")
def helpers():
    """Extrai os helpers de enriquecimento do server.py sem importar o app."""
    src = _SERVER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    chunks: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in _WANT_FUNCS:
            chunks.append("".join(lines[node.lineno - 1 : node.end_lineno]))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in _WANT_CONSTS:
                    chunks.append("".join(lines[node.lineno - 1 : node.end_lineno]))
    mod_src = "\n".join(chunks)
    spec = importlib.util.spec_from_loader("laudo_helpers", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(mod_src, "<laudo_helpers>", "exec"), mod.__dict__)  # noqa: S102 — código próprio extraído do server, não input externo
    sys.modules["laudo_helpers"] = mod
    return mod


class TestFmtMmss:
    def test_segundos(self, helpers):
        assert helpers._fmt_mmss(14) == "00:14"
        assert helpers._fmt_mmss(134) == "02:14"

    def test_horas(self, helpers):
        assert helpers._fmt_mmss(3661) == "1:01:01"

    def test_invalido_retorna_none(self, helpers):
        assert helpers._fmt_mmss(None) is None
        assert helpers._fmt_mmss("abc") is None
        assert helpers._fmt_mmss(-5) is None


class TestConfPct:
    def test_fracao(self, helpers):
        assert helpers._conf_pct(0.95) == 95
        assert helpers._conf_pct(0.6) == 60
        assert helpers._conf_pct(1) == 100

    def test_ja_percentual(self, helpers):
        assert helpers._conf_pct(85) == 85

    def test_invalido_retorna_none(self, helpers):
        assert helpers._conf_pct(None) is None
        assert helpers._conf_pct("x") is None


class TestCamera:
    def test_norm_quadrante(self, helpers):
        assert helpers._norm_camera_label("BL") == "interna"
        assert helpers._norm_camera_label("TL") == "frontal"

    def test_norm_snake(self, helpers):
        assert helpers._norm_camera_label("lateral_direita") == "lateral_direita"

    def test_norm_vazio(self, helpers):
        assert helpers._norm_camera_label("") is None
        assert helpers._norm_camera_label(None) is None

    def test_label_legivel(self, helpers):
        assert helpers._camera_label_legivel("interna") == "Interna"
        assert helpers._camera_label_legivel("lateral_direita") == "Lateral Direita"
        assert helpers._camera_label_legivel(None) is None


class TestEnriquecerInfracao:
    def test_acrescenta_derivados(self, helpers):
        inf = {
            "timestamp_inicio": "02:14",
            "confianca": "ALTA",
            "confianca_raw": 0.95,
            "cameras": ["interna", "lateral_direita"],
            "gravidade": "grave",
        }
        out = helpers._enriquecer_infracao(dict(inf), 510.0)
        assert out["timestamp_inicio_seg"] == 134
        assert out["confianca_pct"] == 95
        assert out["camera_principal"] == "interna"
        assert out["angulo_camera"] == "Interna"
        assert out["quadrante_origem"] == "BL"
        assert out["cameras_norm"] == ["interna", "lateral_direita"]
        assert out["posicao_pct"] == round(134 / 510 * 100, 1)

    def test_preserva_existente(self, helpers):
        # campos crus já presentes nunca são sobrescritos pelo enriquecedor.
        inf = {"timestamp_inicio": "02:14", "confianca": "ALTA", "gravidade": "grave"}
        out = helpers._enriquecer_infracao(dict(inf), 510.0)
        assert out["timestamp_inicio"] == "02:14"
        assert out["confianca"] == "ALTA"
        assert out["gravidade"] == "grave"

    def test_quadrante_existente_nao_sobrescrito(self, helpers):
        inf = {"timestamp_inicio": "02:14", "quadrante_origem": "TR", "cameras": ["interna"]}
        out = helpers._enriquecer_infracao(dict(inf), 0)
        assert out["quadrante_origem"] == "TR"


class TestEnriquecerEvento:
    def test_acrescenta_derivados(self, helpers):
        ev = {
            "evento_id": "E1",
            "timestamp_video_seg": 134,
            "duracao_seg": 2,
            "confianca": 0.92,
            "camera_origem": "interna",
            "quadrante_origem": None,
            "descricao": "candidato sem cinto",
        }
        out = helpers._enriquecer_evento(dict(ev), 510.0)
        assert out["timestamp_fmt"] == "02:14"
        assert out["timestamp_seg"] == 134
        assert out["timestamp_fim_fmt"] == "02:16"
        assert out["duracao_fmt"] == "00:02"
        assert out["confianca_pct"] == 92
        assert out["camera_norm"] == "interna"
        assert out["angulo_camera"] == "Interna"
        # quadrante era None no cru → inferido a partir da câmera.
        assert out["quadrante_origem"] == "BL"
        assert out["descricao"] == "candidato sem cinto"

    def test_quadrante_cru_preservado(self, helpers):
        ev = {"timestamp_video_seg": 10, "camera_origem": "interna", "quadrante_origem": "TL"}
        out = helpers._enriquecer_evento(dict(ev), 0)
        assert out["quadrante_origem"] == "TL"

    def test_fallback_audio_timestamp(self, helpers):
        ev = {"timestamp_video_seg": None, "timestamp_audio_seg": 60}
        out = helpers._enriquecer_evento(dict(ev), 0)
        assert out["timestamp_fmt"] == "01:00"

    def test_nao_dict_passa_direto(self, helpers):
        assert helpers._enriquecer_evento("foo", 0) == "foo"
