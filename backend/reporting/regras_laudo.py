"""Regras determinísticas do Laudo v2.0 — funções puras, sem rede, sem I/O.

Tudo o que num laudo OFICIAL do DETRAN tem de ser fixo e reproduzível vive aqui:
semáforo de divergência (5 cores), código único do laudo, numeração de
infrações (INF-NNN), confiança agregada, recomendação técnica e o mapeamento de
cor por severidade. São funções puras (constitution §VII) — a mesma entrada
produz sempre a mesma saída, o que é o requisito central de um documento
juridicamente defensável.

Nenhuma destas funções altera pontuação (constitution §V): elas só CLASSIFICAM e
FORMATAM dados já calculados pelos motores determinísticos.
"""

from __future__ import annotations

# ── Vocabulário controlado (enums como constantes — sem dependência externa) ──

# Semáforo do Sumário Executivo (FR-LAU-02 / doc §5.3).
SEMAFORO_VERDE = "verde"  # concordância de resultado
SEMAFORO_VERMELHO = "vermelho"  # divergência de RESULTADO (Tipo 1)
SEMAFORO_LARANJA = "laranja"  # divergência silenciosa (Tipo 2/3/4)
SEMAFORO_CINZA = "cinza"  # evidência insuficiente (Tipo 5)
SEMAFORO_ROXO = "roxo"  # interrupção

# Recomendação técnica por infração (FR-LAU-07).
REC_CONFIRMAR = "CONFIRMAR"
REC_REVISAR = "REVISAR"
REC_DESCARTAR = "DESCARTAR"

# Itens críticos do checklist Anexo K (doc §10 / FR-LAU-10).
ITENS_CRITICOS_ANEXO_K = frozenset({1, 2, 8, 9, 10})

# Cor (classe CSS) por severidade — usada no template PDF.
_COR_SEVERIDADE = {
    "gravissima": "gravissima",
    "grave": "grave",
    "media": "media",
    "leve": "leve",
    "eliminatoria": "eliminatoria",
}


def cor_semaforo(
    *,
    concorda_resultado: bool,
    tipo_divergencia: str | None,
    houve_interrupcao: bool = False,
) -> str:
    """Cor determinística do semáforo do Sumário Executivo (doc §5.3).

    Precedência: interrupção (roxo) → concordância (verde) → tipo de divergência.
    `tipo_divergencia` é o valor do enum do motor de comparação, ex.:
    ``"1_resultado"``, ``"2_pontuacao"``, ``"3_infracao"``, ``"4_enquadramento"``,
    ``"5_evidencia_insuficiente"`` (ou ``None`` / ``"sem_divergencia"``).
    """
    if houve_interrupcao:
        return SEMAFORO_ROXO
    if (concorda_resultado and not tipo_divergencia) or tipo_divergencia in (
        None,
        "sem_divergencia",
    ):
        return SEMAFORO_VERDE
    t = (tipo_divergencia or "").lower()
    if t.startswith("1") or "resultado" in t:
        return SEMAFORO_VERMELHO
    if t.startswith("5") or "evidencia" in t:
        return SEMAFORO_CINZA
    if t.startswith(("2", "3", "4")) or any(
        k in t for k in ("pontuacao", "infracao", "enquadramento")
    ):
        return SEMAFORO_LARANJA
    return SEMAFORO_VERDE


def rotulo_divergencia(tipo_divergencia: str | None) -> str:
    """Rótulo legível do tipo de divergência (ex.: 'TIPO 4 (Enquadramento)')."""
    mapa = {
        "1_resultado": "TIPO 1 (Resultado)",
        "2_pontuacao": "TIPO 2 (Pontuação)",
        "3_infracao": "TIPO 3 (Infração)",
        "4_enquadramento": "TIPO 4 (Enquadramento)",
        "5_evidencia_insuficiente": "TIPO 5 (Evidência insuficiente)",
    }
    if not tipo_divergencia or tipo_divergencia == "sem_divergencia":
        return "SEM DIVERGÊNCIA"
    return mapa.get(tipo_divergencia, tipo_divergencia.upper())


def codigo_laudo(*, ano: int, mes: int, video_hash: str | None, prefixo: str = "VAL-LAU") -> str:
    """Código único e estável do laudo: ``VAL-LAU-2026-06-76FD9ED62196``.

    Deriva dos 12 primeiros hexadígitos do hash do vídeo (sem o prefixo
    ``sha256:``), em maiúsculas. Sem hash → ``XXXXXXXXXXXX`` (placeholder
    determinístico, não aleatório — preserva reprodutibilidade).
    """
    h = (video_hash or "").split(":")[-1].strip()
    slug = (h[:12] or "XXXXXXXXXXXX").upper()
    return f"{prefixo}-{ano:04d}-{mes:02d}-{slug}"


def confianca_agregada(confidences: list[float] | None) -> tuple[int, str]:
    """Média das confianças → (percentual_inteiro, rótulo alta|media|baixa).

    Limiares: alta ≥ 80%, média ≥ 60%, baixa < 60%. Lista vazia → (0, 'baixa').
    """
    vals = [float(c) for c in (confidences or []) if c is not None]
    if not vals:
        return 0, "baixa"
    pct = round(sum(vals) / len(vals) * 100)
    if pct >= 80:
        rotulo = "alta"
    elif pct >= 60:
        rotulo = "media"
    else:
        rotulo = "baixa"
    return pct, rotulo


def recomendacao_tecnica(
    *,
    confidence: float | None,
    requer_revisao_humana: bool = False,
    canal_evidencia: str | None = None,
) -> str:
    """Recomendação técnica determinística por infração (FR-LAU-07).

    - CONFIRMAR: confiança alta (≥0.85) e sem flag de revisão humana.
    - REVISAR: confiança média/baixa, ou flag de revisão humana, ou evidência
      de um único canal num caso que pede correlação.
    A IA nunca "decide" — recomenda ao auditor humano (constitution §I).
    """
    c = float(confidence) if confidence is not None else 0.0
    if requer_revisao_humana or c < 0.85:
        return REC_REVISAR
    if canal_evidencia and canal_evidencia not in ("ambos", "visao", "audio"):
        return REC_REVISAR
    return REC_CONFIRMAR


def numerar_infracoes(infracoes: list[dict]) -> list[dict]:
    """Atribui ``inf_id`` sequencial (INF-001, INF-002…) por ordem de timestamp.

    Não muta a entrada: devolve cópias com a chave ``inf_id`` adicionada. Itens
    sem timestamp vão para o fim, preservando ordem estável (determinístico).
    """

    def _ts(d: dict) -> float:
        for k in ("timestamp_s", "ts_seconds", "timestamp_inicio_s"):
            v = d.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        return float("inf")

    ordenadas = sorted(enumerate(infracoes), key=lambda p: (_ts(p[1]), p[0]))
    saida: list[dict] = []
    for posicao, (_, inf) in enumerate(ordenadas, start=1):
        copia = dict(inf)
        copia["inf_id"] = f"INF-{posicao:03d}"
        saida.append(copia)
    return saida


def item_critico(numero: int) -> bool:
    """True se o item do checklist Anexo K é crítico (1,2,8,9,10) — doc §10."""
    return int(numero) in ITENS_CRITICOS_ANEXO_K


def cor_severidade(severidade: str | None) -> str:
    """Classe CSS de cor para a severidade (gravissima|grave|media|leve)."""
    return _COR_SEVERIDADE.get((severidade or "").lower(), "leve")


def camadas_tecnicas(
    layout: dict | None, *, tem_audio: bool = True, tem_telemetria: bool = False
) -> list[str]:
    """Lista legível das camadas técnicas utilizadas (Bloco 5 do mockup).

    Ex.: ['Visão computacional (4 câmeras)', 'Análise de áudio',
          'Telemetria (não disponível neste exame)'].
    """
    camadas: list[str] = []
    n_cams = 0
    if isinstance(layout, dict):
        n_cams = sum(1 for q in ("TL", "TR", "BL", "BR") if layout.get(q))
    camadas.append(f"Visão computacional ({n_cams or 4} câmeras)")
    camadas.append("Análise de áudio" if tem_audio else "Análise de áudio (indisponível)")
    camadas.append("Telemetria" if tem_telemetria else "Telemetria (não disponível neste exame)")
    return camadas
