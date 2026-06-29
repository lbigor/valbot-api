"""Gera o bloco de regras do prompt a PARTIR da Matriz vigente (spec §4.1).

A Matriz versionada passa a ser a fonte única que alimenta os próximos prompts
enviados ao Gemini (Motor de Detecção e Comitê). Assim, atualizar a Matriz muda
o comportamento da IA sem retreinar nada — e cada análise registra a
``matriz_versao`` usada (rastreabilidade §4.4).

Carrega as regras vigentes do banco (``exam_rules``) quando disponível; senão,
do seed canônico do MBEDV (``seed_mbedv.regras_canonicas``).
"""

from __future__ import annotations

from backend.core import db
from backend.core.config import settings
from backend.matriz import seed_mbedv


def _regras_vigentes() -> tuple[list[dict], str]:
    """Devolve (regras, matriz_versao). Banco tem prioridade sobre o seed."""
    if db.db_enabled():
        rows = db.fetch_all(
            "SELECT codigo_val, artigo_ctb, natureza, peso, categorias_aplicaveis, "
            "conduta_observavel, descricao, quando_pontuar, quando_nao_pontuar, "
            "comentario_juridico "
            "FROM exam_rules WHERE vigencia_fim IS NULL ORDER BY artigo_ctb"
        )
        ver = db.fetch_one("SELECT versao FROM matriz_versoes WHERE vigente = TRUE LIMIT 1")
        if rows:
            return rows, (ver["versao"] if ver else settings.matriz_versao)
    return seed_mbedv.regras_canonicas(), settings.matriz_versao


def _aplica_categoria(regra: dict, categoria: str | None) -> bool:
    if not categoria:
        return True
    cats = regra.get("categorias_aplicaveis") or []
    return not cats or categoria.upper() in cats


# Diretrizes de avaliação do Val Auditor — camada de INTERPRETAÇÃO para a IA,
# separada da ficha oficial MBEDV (não altera o texto normativo). Corrigem falsos
# positivos conhecidos por limitação do motor de visão: o vídeo é amostrado a ~1
# quadro/segundo, então uma imobilização breve pode não aparecer entre os quadros.
# Chave = número do artigo CTB.
_DIRETRIZES_VAL: dict[str, str] = {
    "208": (
        "Benefício da dúvida na PARADA OBRIGATÓRIA: só pontue se houver evidência "
        "INEQUÍVOCA de movimento contínuo cruzando a faixa de retenção SEM parar. "
        "O vídeo é amostrado a ~1 quadro por segundo, então uma parada completa "
        "breve (1–2 s) pode não aparecer entre os quadros — ver o veículo em "
        "movimento logo antes e logo depois NÃO prova que não houve parada. Na "
        "dúvida sobre a imobilização total, NÃO pontue (benefício da dúvida ao "
        "candidato). "
        "O ÁUDIO DO MOTOR É IRRELEVANTE para este artigo: numa parada de 1–2 s o "
        "motor permanece em marcha lenta, então 'som/rotação contínua do motor' ou "
        "'ausência da pausa característica de uma parada' NÃO é prova de falta de "
        "imobilização. NUNCA pontue o Art. 208 com base em áudio — descarte a "
        "infração cujo único suporte seja sonoro; a prova precisa ser VISUAL. "
        "ESTRATÉGIA DO FRAME CONGELADO: antes de pontuar, PROCURE nas câmeras "
        "EXTERNAS (FRONTAL e LATERAL_DIREITA, visão de fora do veículo) um quadro "
        "em que o veículo esteja CLARAMENTE IMÓVEL após cruzar a placa de parada "
        "obrigatória (R-1) / a faixa de retenção; priorize essas câmeras externas "
        "sobre a INTERNA, que mostra o candidato e não a posição do veículo na via. "
        "Se encontrar QUALQUER frame de imobilidade real (mesmo breve), NÃO pontue — "
        "a amostragem ~1 fps pode simplesmente não ter capturado o instante da "
        "parada. Só pontue se NENHUMA câmera externa mostrar imobilidade e houver "
        "evidência inequívoca de passagem contínua."
    ),
    "169": (
        "Art. 169 é RESIDUAL (dirigir sem atenção ou sem os cuidados "
        "indispensáveis à segurança): só pontue quando houver DESATENÇÃO genuína (ex.: não "
        "olhar o painel, não conferir os retrovisores/laterais ao sair ou mudar de "
        "faixa, dirigir distraído) E não existir enquadramento específico para a "
        "conduta. NÃO use o 169 como guarda-chuva: NÃO pontue erro de marcha ou "
        "embreagem isolado (engatar a marcha errada, arranhar o câmbio, dificuldade "
        "de engatar a ré, trepidar/apagar em aclive), nem qualquer ação executada "
        "sob INSTRUÇÃO ou CORREÇÃO VERBAL do examinador, nem ajustar/recolocar o "
        "cinto ou tentar ligar o motor já ligado — são dificuldades mecânicas "
        "pontuais ou conduzidas, não desatenção. Confiança alta não substitui "
        "evidência de desatenção: na dúvida, NÃO pontue."
    ),
    "196": (
        "GUARD DE ÁUDIO — PREVALECE sobre a lista 'Condutas que pontuam' acima: a "
        "seta/sinalização SÓ se valida por ÁUDIO (o 'tic-tac' do relé do pisca). A "
        "AUSÊNCIA do som do relé NÃO prova que o candidato não sinalizou — pode ser "
        "áudio baixo, ruído do motor ou captação ruim. 'Não vi a alavanca da seta "
        "ser acionada' ou 'não ouvi o tic-tac' NÃO é evidência suficiente: ausência "
        "visual/sonora ≠ falta de sinalização. Antes de pontuar, RE-ESCUTE o trecho "
        "e confirme em pelo menos um canal; se o áudio for inconclusivo, marque como "
        "pendente/não-detectada, NUNCA como infração. Exceções da ficha que também "
        "NÃO pontuam: conversão em entroncamento de única direção e saída de lote "
        "lindeiro em via de mão única. Na dúvida, NÃO pontue."
    ),
}

# Versão semântica das Diretrizes de avaliação Val. BUMPAR a cada alteração de
# `_DIRETRIZES_VAL` e registrar a mudança em docs/PROMPT_CHANGELOG.md. A versão
# reportada por análise é COMPOSTA — `<matriz_versao>+diretrizes-v<X.Y.Z>` — para
# rastrear qual revisão do prompt julgou cada exame (a Matriz oficial do DB e a
# camada de interpretação Val evoluem em trilhas independentes).
DIRETRIZES_VAL_VERSAO = "1.3.0"


def versao_composta(matriz_versao: str) -> str:
    """Versão reportada por análise: une a versão da Matriz à das Diretrizes Val."""
    return f"{matriz_versao}+diretrizes-v{DIRETRIZES_VAL_VERSAO}"


def _diretriz_val(artigo_ctb: str | None) -> str | None:
    """Diretriz operacional do Val Auditor para o artigo (casada por número)."""
    if not artigo_ctb:
        return None
    import re

    m = re.search(r"(\d+)", str(artigo_ctb))
    return _DIRETRIZES_VAL.get(m.group(1)) if m else None


def _num_ctb(artigo: str | None) -> str:
    """Extrai o número do artigo CTB (ex.: 'Art. 252, V' → '252')."""
    import re

    m = re.search(r"(\d+)", str(artigo or ""))
    return m.group(1) if m else ""


def construir_bloco(
    categoria: str | None = None, artigos: set[str] | list[str] | None = None
) -> tuple[str, str]:
    """Monta o bloco textual das regras a avaliar (filtrado por categoria CNH).

    Devolve (texto_do_bloco, matriz_versao). Cada regra vira um item com artigo,
    natureza/peso, condutas que pontuam e — crítico — condutas que NÃO pontuam.

    Se ``artigos`` for informado (ex.: os artigos das infrações detectadas), o
    bloco é RESTRITO a essas fichas — encolhe o prompt do Comitê (que só precisa
    das fichas em julgamento), evitando estourar o tamanho do pedido.
    """
    regras, versao = _regras_vigentes()
    aplicaveis = [r for r in regras if _aplica_categoria(r, categoria)]
    if artigos:
        nums = {_num_ctb(a) for a in artigos if _num_ctb(a)}
        if nums:
            aplicaveis = [r for r in aplicaveis if _num_ctb(r.get("artigo_ctb")) in nums]

    linhas = [
        f"MATRIZ NACIONAL DE REGRAS — versão {versao} (fonte: MBEDV/CTB). "
        f"Diretrizes de avaliação Val v{DIRETRIZES_VAL_VERSAO}.",
        "Avalie CADA artigo abaixo. Para cada um, decida se a conduta ocorreu, "
        "respeitando as exceções (condutas que NÃO pontuam).",
        "",
        "EXCEÇÕES DO NOVO MODELO MBEDV — NUNCA pontue (não geram infração nem "
        "pontos ao candidato), mesmo que pareçam falta:",
        '  - Veículo "morre" (motor apaga/cala) durante o exame, INCLUSIVE ao '
        "arrancar em aclive/rampa — o candidato pode religar normalmente. NÃO é "
        "infração (não enquadre em Art. 169 nem similar).",
        "  - Erro de baliza ISOLADO — a baliza não é mais etapa autônoma do exame; "
        "não é eliminatório nem pontua isoladamente.",
        "  - Saída de faixa em EMERGÊNCIA ou por ORIENTAÇÃO do preposto/examinador — "
        "não pontua quando há exceção válida prevista no MBEDV.",
        "  - Conduta INDUZIDA por comentário inadequado do examinador — não pontua "
        "(comentários que induzem o candidato ao erro são proibidos pelo MBEDV).",
        "",
    ]
    for r in aplicaveis:
        peso = r.get("peso")
        peso_txt = f"{peso} pts" if peso is not None else "peso por inciso (revisão humana)"
        linhas.append(
            f"### {r.get('artigo_ctb')} — {r.get('conduta_observavel')} "
            f"[{r.get('natureza')}, {peso_txt}]"
        )
        # Descrição oficial da ficha MBEDV — contextualiza o que caracteriza a falta.
        if r.get("descricao"):
            linhas.append(f"Descrição: {str(r['descricao']).strip()}")
        if r.get("quando_pontuar"):
            linhas.append("Condutas que pontuam:")
            for c in str(r["quando_pontuar"]).split("\n"):
                if c.strip():
                    linhas.append(f"  - {c.strip()}")
        if r.get("quando_nao_pontuar"):
            linhas.append("Condutas que NÃO pontuam (descartar mesmo se parecer):")
            for c in str(r["quando_nao_pontuar"]).split("\n"):
                if c.strip():
                    linhas.append(f"  - {c.strip()}")
        # Definições e procedimentos da ficha MBEDV — COMO avaliar (ponto de
        # referência da conduta, ex.: "parada antes da faixa de retenção; veículo
        # totalmente imóvel"). Crítico p/ não gerar falso positivo de parada rolante.
        if r.get("comentario_juridico"):
            linhas.append(
                f"Como avaliar (definições e procedimentos): "
                f"{str(r['comentario_juridico']).strip()}"
            )
        # Diretriz operacional do Val Auditor (interpretação p/ a IA; NÃO altera a
        # ficha oficial) — corrige falso positivo conhecido por amostragem de vídeo.
        dir_val = _diretriz_val(r.get("artigo_ctb"))
        if dir_val:
            linhas.append(f"Diretriz de avaliação (Val Auditor): {dir_val}")
        linhas.append("")
    return "\n".join(linhas), versao_composta(versao)
