"""Detector de Art. 208 (parada obrigatória / sinal vermelho) em 2 estágios.

Estágio 1 (vídeo inteiro, fps baixo) localiza candidatos (semáforo/placa PARE);
estágio 2 (janela recortada de cada candidato, fps alto) decide com critério
rigoroso. Fundamentado em como o Gemini amostra vídeo (frame=1 tile; recortar a
janela dá foco/recall, fps dá resolução temporal localizada) — ver memória
reference-gemini-video-processamento.

Import sem efeito de rede: a chamada ao Vertex (call_fn) é injetada; o default
(rest.vertex_generate_content) só é carregado quando call_fn is None. No CI os
testes passam um call_fn fake.
"""

from __future__ import annotations

from collections.abc import Callable

from . import core, prompts
from .core import Evento208, Resultado208
from .prompts import DETECTOR_208_VERSION

__all__ = ["DETECTOR_208_VERSION", "Evento208", "Resultado208", "detectar_208"]


def detectar_208(
    gs_uri: str,
    *,
    call_fn: Callable[[dict], dict] | None = None,
    fps_estagio1: int = 1,
    fps_estagio2: int = 5,
    janela_s: int = 5,
    limiar_confianca: float = 0.0,
    max_candidatos: int = 5,
    model_name: str = "gemini-2.5-pro",
    project_id: str | None = None,
    location: str | None = None,
) -> Resultado208:
    """Roda os 2 estágios e devolve o veredito + custo. call_fn(payload)->resp_json."""
    if call_fn is None:  # default real: rede (lazy import — não toca rede no import do módulo)
        from . import rest

        def call_fn(payload: dict) -> dict:  # type: ignore[misc]
            return rest.vertex_generate_content(
                payload, project_id=project_id, location=location, model_name=model_name
            )

    custo = 0.0
    # ---- estágio 1: localizar candidatos ----
    p1 = core.montar_payload(
        gs_uri,
        prompts.PROMPT_ESTAGIO1_LOCALIZAR,
        fps=fps_estagio1,
        response_schema=prompts.RESPONSE_SCHEMA_E1,
    )
    r1 = call_fn(p1)
    custo += core.custo_da_resposta(r1, model_name)["usd"]
    candidatos = core.parse_candidatos(r1)[:max_candidatos]

    # ---- estágio 2: decidir cada janela ----
    janelas = []
    for c in candidatos:
        s0, s1 = core.janela_offsets(c["ts_seg"], janela_s)
        p2 = core.montar_payload(
            gs_uri,
            prompts.PROMPT_ESTAGIO2_DECIDIR,
            fps=fps_estagio2,
            start_offset=s0,
            end_offset=s1,
            response_schema=prompts.RESPONSE_SCHEMA_E2,
        )
        r2 = call_fn(p2)
        custo += core.custo_da_resposta(r2, model_name)["usd"]
        v = core.parse_veredito_janela(r2)
        v["ts_seg"] = c["ts_seg"]
        janelas.append(v)

    houve, eventos = core.agregar_janelas(janelas, limiar_confianca=limiar_confianca)
    return Resultado208(
        houve_208=houve,
        eventos=eventos,
        custo_usd=round(custo, 6),
        versao=DETECTOR_208_VERSION,
        n_candidatos=len(candidatos),
        detalhe={"janelas": janelas},
    )
