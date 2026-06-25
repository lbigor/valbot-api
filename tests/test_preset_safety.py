"""Regressão de segurança: garante que o princípio "in dubio, não apontar"
e demais salvaguardas críticas permanecem nos prompts do VALBOT.

Esses testes falham deliberadamente o build se alguém (humano ou refactor
automático) remover acidentalmente as regras de conservadorismo do preset
ou do user prompt do backend.

Justificativa: o princípio é o que torna o sistema juridicamente defensável
no fluxo administrativo (3 níveis de revisão). Removê-lo silenciosamente
muda o caráter do produto — falsos positivos disparariam acusações
indevidas. O teste é cheap insurance contra esse modo de falha.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRESET_DIR = PROJECT_ROOT / "tooling" / "bench_demo" / "presets"


# ============================================================================
# Preset v25 — system prompt do Gemini
# ============================================================================


@pytest.fixture(scope="module")
def preset_v25() -> str:
    path = PRESET_DIR / "v25" / "valbot-r1-vip-v25.md"
    assert path.exists(), f"Preset v25 não encontrado em {path}"
    return path.read_text(encoding="utf-8")


class TestPresetV25InDubioPrinciple:
    """O princípio supremo deve estar presente, em destaque, no final do preset."""

    def test_principle_header_present(self, preset_v25: str):
        assert "IN DUBIO, NÃO APONTAR" in preset_v25, (
            "Cabeçalho do princípio supremo foi removido. Releia "
            "tests/test_preset_safety.py — esta regra é INVIOLÁVEL."
        )

    def test_principle_at_end_of_preset(self, preset_v25: str):
        """O princípio precisa estar no final (precedência sobre regras anteriores)."""
        idx = preset_v25.find("IN DUBIO, NÃO APONTAR")
        assert idx > 0, "Cabeçalho ausente"
        # Deve estar nos últimos 30% do arquivo (regra de precedência por posição)
        assert idx > 0.65 * len(preset_v25), (
            "Princípio supremo precisa ficar no FINAL do preset (precedência). "
            "Hoje está em posição inicial — mover para o fim do arquivo."
        )

    def test_explicit_precedence_clause(self, preset_v25: str):
        assert "precedência" in preset_v25.lower() or "precedencia" in preset_v25.lower(), (
            "A cláusula de precedência sobre demais regras foi removida"
        )

    def test_confidence_threshold_explicit(self, preset_v25: str):
        """Deve existir um limiar in-dubio de confiança explícito e numérico
        (ex.: '< 0.60'). O VALOR pode evoluir (o Tier B foi rebaixado 0.70→0.60,
        documentado no preset; Tier A segue 0.70) — o que este teste garante é
        que HÁ um critério objetivo de 'dúvida'. Sem ele o modelo não tem piso
        para não-apontar."""
        assert re.search(r"<\s*0[.,]\d", preset_v25), (
            "Limiar in-dubio de confidence (ex.: '< 0.NN') ausente. Sem ele, o "
            "modelo não tem critério objetivo para 'dúvida'."
        )

    def test_authorized_command_clause(self, preset_v25: str):
        """Cláusula de comando autorizador do examinador deve estar."""
        text_lower = preset_v25.lower()
        assert "comando autorizador" in text_lower or (
            "autoriz" in text_lower and "examinador" in text_lower
        ), (
            "Cláusula de comando autorizador foi removida — sem ela, "
            "o modelo pode acusar manobras que o examinador autorizou."
        )

    def test_audit_self_question_present(self, preset_v25: str):
        """Auto-verificação ('eu defenderia em auditoria?') deve estar."""
        assert (
            "defenderia esta detecção" in preset_v25
            or "defenderia esta deteccao" in preset_v25
            or "defenderia em auditoria" in preset_v25.lower()
        ), "Pergunta de auto-verificação removida do preset"

    def test_omit_not_pendente_humana(self, preset_v25: str):
        """Preset deve instruir OMISSÃO, não atalho via pendente_revisao_humana."""
        assert "OMISSÃO TOTAL" in preset_v25 or "OMITIR" in preset_v25, (
            "Instrução explícita de OMISSÃO ausente — modelo pode usar pendente_* como atalho"
        )

    def test_reward_function_present(self, preset_v25: str):
        """Função de recompensa (PUNIDO / RECOMPENSADO) deve estar codificada."""
        assert "PUNIDO" in preset_v25 and "RECOMPENSADO" in preset_v25, (
            "Função de recompensa do benchmark foi removida — sem ela, "
            "o modelo perde a sinalização de qual comportamento é desejável."
        )


# ============================================================================
# User prompt do backend Vertex Gemini
# ============================================================================


@pytest.fixture(scope="module")
def backend_user_prompt() -> str:
    """Reproduz o user prompt que o backend monta em toda chamada."""
    from src.analysis.openrouter_gemini import _build_user_prompt

    return _build_user_prompt("1020/2025")


class TestBackendUserPromptSafety:
    """A regra também precisa estar no user prompt (segunda linha de defesa)."""

    def test_in_dubio_in_user_prompt(self, backend_user_prompt: str):
        assert "IN DUBIO, NÃO APONTAR" in backend_user_prompt, (
            "Princípio supremo ausente no user prompt do backend. "
            "Defesa em profundidade exige a regra em preset E user prompt."
        )

    def test_user_prompt_has_threshold(self, backend_user_prompt: str):
        assert "0.70" in backend_user_prompt or "0,70" in backend_user_prompt, (
            "Limiar de confidence ausente no user prompt"
        )

    def test_user_prompt_audit_question(self, backend_user_prompt: str):
        text_lower = backend_user_prompt.lower()
        assert "defenderia" in text_lower and "auditoria" in text_lower, (
            "Pergunta de auto-verificação ausente no user prompt"
        )

    def test_user_prompt_audio_video_correlation(self, backend_user_prompt: str):
        """Correlação áudio + vídeo (diferencial vs frame extraction) deve estar."""
        text = backend_user_prompt
        assert "áudio" in text.lower() or "audio" in text.lower()
        assert "visão" in text.lower() or "visao" in text.lower() or "vídeo" in text.lower()
        assert "correla" in text.lower(), (
            "Instrução de correlação áudio-visual ausente — perde diferencial técnico"
        )

    def test_user_prompt_layout_4_cameras(self, backend_user_prompt: str):
        """As 4 câmeras fixas devem estar enumeradas."""
        for camera in ("frontal", "lateral_direita", "interna", "traseira_esq"):
            assert camera in backend_user_prompt, (
                f"Câmera '{camera}' ausente do user prompt — quebra a "
                f"identificação de layout dinâmico"
            )


# ============================================================================
# Sanity check geral
# ============================================================================


class TestPresetIntegrity:
    """Testes gerais de integridade do preset."""

    def test_preset_has_minimum_length(self, preset_v25: str):
        """Preset v25 tem ~50KB; alarme se ficar pequeno demais (= alguém apagou)."""
        assert len(preset_v25) > 30_000, (
            f"Preset v25 com apenas {len(preset_v25)} chars — esperado >30k. "
            f"Alguém pode ter apagado seções por engano."
        )

    def test_schema_output_present(self, preset_v25: str):
        """Schema de saída obrigatório precisa estar definido."""
        assert "SCHEMA DE SAÍDA OBRIGATÓRIO" in preset_v25
        assert "ts_seconds" in preset_v25
        assert "infracoes" in preset_v25
