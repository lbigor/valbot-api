"""Eventos que NÃO pontuam (spec §3.5) — exceções vinculantes do MBEDV.

O MBEDV é explícito ao definir o que NÃO é infração no exame. Este módulo
centraliza essas regras para que o Motor Normativo as aplique de forma
auditável (cada não-pontuação carrega o motivo). Casos cobertos:

  1. Veículo "morre" durante o exame  → não pontua; candidato pode religar.
  2. Erro de baliza ISOLADO           → não pontua (baliza não é mais etapa
                                         autônoma; só a falha em 3 tentativas).
  3. Saída da faixa em emergência ou por orientação do preposto → exceção.
  4. Conduta INDUZIDA por comentário inadequado do examinador → não pontua
     (comentários que induzem ao erro são proibidos pelo MBEDV).

Cada função recebe um ``EventoDetectado`` (e, quando relevante, os comentários
do examinador) e devolve o código da exceção aplicável ou ``None``.
"""

from __future__ import annotations

from backend.models import EventoDetectado

# Janela (s) em torno da infração na qual um comentário inadequado do
# examinador é considerado indutor da conduta.
JANELA_INDUCAO_SEG = 6.0


def veiculo_morreu(ev: EventoDetectado) -> str | None:
    """Caso 1 — veículo que "morre" NÃO pontua (spec §3.5). Regra DURA.

    O candidato pode religar normalmente. R1020-M-c pune apenas "interromper o
    funcionamento do motor SEM justa razão" — o que NÃO é o mesmo que o carro
    calar. Por isso o default aqui é proteger o candidato: o motor calando só
    vira infração quando há sinal EXPLÍCITO de que foi sem justa razão
    (desligamento voluntário em movimento ou falha reiterada). Na ausência
    desse sinal, não pontua — jamais penalizamos alguém por deixar o carro
    morrer.
    """
    ctx = ev.contexto_adicional or {}
    if ctx.get("motor_morreu") or ctx.get("veiculo_morreu"):
        return "veiculo_morreu_nao_pontua"
    if ctx.get("regra_id") == "R1020-M-c":
        sem_justa_razao = (
            ctx.get("sem_justa_razao") or ctx.get("desligamento_voluntario") or ctx.get("reiterado")
        )
        if not sem_justa_razao:
            return "veiculo_morreu_nao_pontua"
    return None


def baliza_isolada(ev: EventoDetectado) -> str | None:
    """Caso 2 — erro de baliza só pontua após 3 tentativas falhas (R1020-G-c)."""
    ctx = ev.contexto_adicional or {}
    if ctx.get("regra_id") == "R1020-G-c":
        tentativas = ctx.get("tentativas_baliza")
        if tentativas is not None and tentativas < 3:
            return "baliza_isolada_nao_eliminatoria"
        if ctx.get("baliza_isolada"):
            return "baliza_isolada_nao_eliminatoria"
    return None


def excecao_contexto(ev: EventoDetectado) -> str | None:
    """Caso 3 — emergência / orientação do preposto / comando autorizado."""
    ctx = ev.contexto_adicional or {}
    if ctx.get("comando_examinador") or ctx.get("comando_autorizado"):
        return "comando_autorizado_examinador"
    if ctx.get("havia_emergencia"):
        return "emergencia"
    if ctx.get("intervencao_preposto"):
        return "orientacao_preposto"
    return None


def conduta_induzida(
    ev: EventoDetectado,
    comentarios_examinador: list[EventoDetectado],
) -> str | None:
    """Caso 4 — conduta induzida por comentário inadequado do examinador.

    Se um comentário classificado como inadequado/indutor ocorreu na janela
    temporal da infração, a conduta NÃO pontua (proibido pelo MBEDV).
    """
    t = ev.timestamp_video_seg or ev.timestamp_audio_seg
    if t is None or not comentarios_examinador:
        return None
    for c in comentarios_examinador:
        classif = (c.classificacao or "").lower()
        if "inadequado" not in classif and "induz" not in classif and "intimidat" not in classif:
            continue
        tc = c.timestamp_audio_seg or c.timestamp_video_seg
        if tc is None:
            continue
        if abs(tc - t) <= JANELA_INDUCAO_SEG:
            return "conduta_induzida_comentario_examinador"
    return None


def avaliar(
    ev: EventoDetectado,
    comentarios_examinador: list[EventoDetectado] | None = None,
) -> str | None:
    """Aplica todas as regras da §3.5 em ordem. Devolve o 1º motivo aplicável."""
    comentarios_examinador = comentarios_examinador or []
    for fn, arg in (
        (veiculo_morreu, None),
        (baliza_isolada, None),
        (excecao_contexto, None),
    ):
        motivo = fn(ev)  # type: ignore[operator]
        if motivo:
            return motivo
    return conduta_induzida(ev, comentarios_examinador)
