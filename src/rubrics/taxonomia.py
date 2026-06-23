"""
Taxonomia de infrações — Res. CONTRAN 1.020/2025.
Fonte única da verdade para IDs, severidades, pontuações, câmeras e
detectabilidade com a infraestrutura atual (4 cams VIP Intelbras 1280×720
+ Whisper, sem OBD/painel/GPS sincronizado).

A 789/2020 foi descontinuada deste pipeline em 2026-04-25 — o projeto
avalia exclusivamente a 1.020/2025.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Rubrica(StrEnum):
    RES_1020_2025 = "1020_2025"


class Severidade(StrEnum):
    GRAVISSIMA = "gravissima"
    GRAVE = "grave"
    MEDIA = "media"
    LEVE = "leve"


class Camera(StrEnum):
    FRONTAL = "frontal"
    LATERAL_DIREITA = "lateral_direita"
    INTERNA = "interna"
    TRASEIRA_ESQ = "traseira_esq"
    AUDIO = "audio"


class Tier(StrEnum):
    """Detectabilidade com a infra atual.
    A — busca ativa, alta confiança.
    B — varredura passiva; só vira detecção formal se evidência for inequívoca; em dúvida, status = pendente_infraestrutura.
    C — não detectável com sensor atual; status sempre pendente_infraestrutura.
    """

    A = "A"
    B = "B"
    C = "C"


class StatusAvaliacao(StrEnum):
    AVALIADO = "avaliado"
    PENDENTE_INFRAESTRUTURA = "pendente_infraestrutura"


PONTOS = {
    Rubrica.RES_1020_2025: {
        Severidade.GRAVISSIMA: 6,
        Severidade.GRAVE: 4,
        Severidade.MEDIA: 2,
        Severidade.LEVE: 1,
    },
}

LIMITE_APROVACAO = 10  # ≤ 10 pontos cumulativos = aprovado na 1.020/2025


@dataclass
class Infracao:
    id: str
    rubrica: Rubrica
    severidade: Severidade
    descricao: str
    base_legal: str
    cameras_relevantes: list[Camera]
    checklist_visual: list[str]
    tier: Tier
    infra_faltante: list[str] = field(default_factory=list)
    requer_obd: bool = False

    @property
    def pontos(self) -> int:
        return PONTOS[self.rubrica][self.severidade]

    @property
    def status_default(self) -> StatusAvaliacao:
        if self.tier in (Tier.A, Tier.B):
            return StatusAvaliacao.AVALIADO
        return StatusAvaliacao.PENDENTE_INFRAESTRUTURA

    @property
    def detectavel_v1(self) -> bool:
        """Mantido por retrocompatibilidade: True para Tier A/B, False para C."""
        return self.tier in (Tier.A, Tier.B)


CATALOGO: list[Infracao] = [
    # ========================================================================
    # Gravíssimas (6 pts)
    # ========================================================================
    Infracao(
        id="R1020-G-a",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVISSIMA,
        descricao="Desobedecer à sinalização semafórica ou de parada obrigatória",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL],
        checklist_visual=[
            "Semáforo vermelho visível e veículo cruzou faixa de retenção?",
            "Placa PARE visível e veículo não parou completamente?",
        ],
        tier=Tier.A,
    ),
    Infracao(
        id="R1020-G-b",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVISSIMA,
        descricao="Avançar sobre o meio-fio",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.TRASEIRA_ESQ, Camera.LATERAL_DIREITA],
        checklist_visual=["Roda tocou ou subiu no meio-fio?"],
        tier=Tier.C,
        infra_faltante=["câmera traseira-baixa-esquerda dedicada"],
    ),
    Infracao(
        id="R1020-G-c",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVISSIMA,
        descricao="Não concluir a baliza dentro da área balizada em 3 tentativas",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL, Camera.TRASEIRA_ESQ],
        checklist_visual=["Foi um exercício de baliza?", "Quantas tentativas?", "Concluiu na 3ª?"],
        tier=Tier.C,
        infra_faltante=["segmentação do exercício no metadata da prova", "GPS/odometria"],
    ),
    Infracao(
        id="R1020-G-d",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVISSIMA,
        descricao="Transitar em contramão de direção",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL],
        checklist_visual=[
            "LFO (linha amarela) à direita do veículo?",
            "Tráfego oposto vindo de frente?",
        ],
        tier=Tier.B,
    ),
    Infracao(
        id="R1020-G-e",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVISSIMA,
        descricao="Avançar via preferencial",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL],
        checklist_visual=["Há placa DÊ A PREFERÊNCIA (R-2)?", "Cruzou sem parar/ceder?"],
        tier=Tier.B,
    ),
    Infracao(
        id="R1020-G-f",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVISSIMA,
        descricao="Provocar acidente durante a realização do exame",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[
            Camera.FRONTAL,
            Camera.LATERAL_DIREITA,
            Camera.TRASEIRA_ESQ,
            Camera.AUDIO,
        ],
        checklist_visual=["Impacto visível?", "(áudio) ruído de colisão?"],
        tier=Tier.B,
        infra_faltante=["acelerômetro/IMU", "áudio limpo de impacto"],
    ),
    Infracao(
        id="R1020-G-g",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVISSIMA,
        descricao="Exceder a velocidade regulamentada para a via",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL],
        checklist_visual=["Placa de velocidade R-19 visível?", "Velocidade real do veículo?"],
        tier=Tier.C,
        infra_faltante=["leitura velocímetro/painel ou GPS sincronizado", "OCR da placa R-19"],
    ),
    # ========================================================================
    # Graves (4 pts)
    # ========================================================================
    Infracao(
        id="R1020-GR-a",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVE,
        descricao="Desobedecer à sinalização da via ou ao agente da autoridade",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL],
        checklist_visual=[
            "Sinalização vertical/horizontal específica?",
            "Conduta contrária à sinalização?",
        ],
        tier=Tier.B,
    ),
    Infracao(
        id="R1020-GR-b",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVE,
        descricao="Não observar regras de ultrapassagem ou mudança de direção",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.LATERAL_DIREITA, Camera.INTERNA, Camera.FRONTAL],
        checklist_visual=["Sinalizou seta?", "Olhou retrovisor?", "Local permitido?"],
        tier=Tier.C,
        infra_faltante=["leitura de seta no painel", "câmera retrovisor traseiro"],
    ),
    Infracao(
        id="R1020-GR-c",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVE,
        descricao="Não observar a preferência do pedestre",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL],
        checklist_visual=["Pedestre sobre a FTP?", "Veículo parou para ceder?"],
        tier=Tier.B,
    ),
    Infracao(
        id="R1020-GR-d",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVE,
        descricao="Manter a porta do veículo aberta ou semiaberta durante o percurso",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.LATERAL_DIREITA, Camera.INTERNA],
        checklist_visual=["Porta visivelmente aberta com veículo em movimento?"],
        tier=Tier.B,
    ),
    Infracao(
        id="R1020-GR-e",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVE,
        descricao="Não sinalizar com antecedência a manobra pretendida",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.INTERNA],
        checklist_visual=["Seta acionada antes da manobra?"],
        tier=Tier.C,
        infra_faltante=["leitura de seta no painel"],
    ),
    Infracao(
        id="R1020-GR-f",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVE,
        descricao="Não usar devidamente o cinto de segurança",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.INTERNA],
        checklist_visual=["Cinto cruzando o peito do condutor (lado direito da imagem)?"],
        tier=Tier.A,
    ),
    Infracao(
        id="R1020-GR-g",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.GRAVE,
        descricao="Perder o controle da direção do veículo em movimento",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL, Camera.INTERNA],
        checklist_visual=["Movimento brusco/zigue-zague visível?"],
        tier=Tier.C,
        infra_faltante=["acelerômetro/IMU", "GPS sincronizado"],
    ),
    # ========================================================================
    # Médias (2 pts)
    # ========================================================================
    Infracao(
        id="R1020-M-a",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Executar percurso sem o freio de mão inteiramente livre",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.AUDIO],
        checklist_visual=[
            "(áudio) ranger do tambor de freio?",
            "(áudio) reclamação do examinador?",
        ],
        tier=Tier.C,
        infra_faltante=["áudio motor limpo", "OBD freio de mão"],
    ),
    Infracao(
        id="R1020-M-b",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Trafegar em velocidade inadequada para as condições adversas",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL],
        checklist_visual=["Condição adversa (chuva, escuro, tráfego)?", "Velocidade compatível?"],
        tier=Tier.C,
        infra_faltante=["leitura velocímetro", "classificador de condições adversas"],
    ),
    Infracao(
        id="R1020-M-c",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Interromper o funcionamento do motor sem justa razão",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.AUDIO],
        checklist_visual=["(áudio) motor calou?", "Cenário estático seguido de re-partida?"],
        tier=Tier.C,
        infra_faltante=["áudio motor limpo", "OBD RPM"],
    ),
    Infracao(
        id="R1020-M-d",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Fazer conversão incorretamente",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.FRONTAL],
        checklist_visual=["Conversão fechada/aberta demais?", "Invadiu mão contrária?"],
        tier=Tier.B,
    ),
    Infracao(
        id="R1020-M-e",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Usar buzina sem necessidade ou em local proibido",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.AUDIO],
        checklist_visual=["(áudio) buzina sem motivo claro?"],
        tier=Tier.C,
        infra_faltante=["transcript Whisper limpo", "classificador de áudio para buzina"],
    ),
    Infracao(
        id="R1020-M-f",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Desengrenar o veículo nos declives",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.AUDIO],
        checklist_visual=["Cenário em declive?", "(áudio) motor em marcha lenta enquanto desce?"],
        tier=Tier.C,
        infra_faltante=["sensor câmbio/OBD", "sensor inclinação", "áudio motor"],
    ),
    Infracao(
        id="R1020-M-g",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Colocar o veículo em movimento sem observar as cautelas necessárias",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.INTERNA, Camera.FRONTAL],
        checklist_visual=["Olhou retrovisor antes de partir?", "Sinalizou?"],
        tier=Tier.C,
        infra_faltante=["câmera frontal alta orientada ao rosto", "leitura de seta"],
    ),
    Infracao(
        id="R1020-M-h",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Usar embreagem antes do freio nas frenagens",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[],
        checklist_visual=[],
        tier=Tier.C,
        infra_faltante=["OBD pedais"],
        requer_obd=True,
    ),
    Infracao(
        id="R1020-M-i",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Entrar em curvas com a engrenagem em ponto neutro",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[],
        checklist_visual=[],
        tier=Tier.C,
        infra_faltante=["OBD câmbio"],
        requer_obd=True,
    ),
    Infracao(
        id="R1020-M-j",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.MEDIA,
        descricao="Engrenar ou utilizar as marchas de maneira incorreta",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.AUDIO],
        checklist_visual=["(áudio) RPM muito alto/baixo para a marcha?"],
        tier=Tier.C,
        infra_faltante=["áudio motor limpo", "OBD câmbio"],
    ),
    # ========================================================================
    # Leves (1 pt)
    # ========================================================================
    Infracao(
        id="R1020-L-a",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.LEVE,
        descricao="Provocar movimentos irregulares no veículo sem motivo justificado",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.AUDIO, Camera.INTERNA],
        checklist_visual=["Solavanco visível?", "(áudio) estol?"],
        tier=Tier.C,
        infra_faltante=["áudio motor", "acelerômetro"],
    ),
    Infracao(
        id="R1020-L-b",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.LEVE,
        descricao="Ajustar incorretamente o banco do veículo",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.INTERNA],
        checklist_visual=["Postura do condutor (banco) na partida?"],
        tier=Tier.C,
        infra_faltante=["frame pré-prova garantido (banco antes do início)"],
    ),
    Infracao(
        id="R1020-L-c",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.LEVE,
        descricao="Não ajustar devidamente os espelhos retrovisores",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.INTERNA],
        checklist_visual=["Espelhos retrovisores apontando corretamente?"],
        tier=Tier.C,
        infra_faltante=["câmera focando os retrovisores"],
    ),
    Infracao(
        id="R1020-L-d",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.LEVE,
        descricao="Apoiar o pé no pedal da embreagem com o veículo engrenado em movimento",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[],
        checklist_visual=[],
        tier=Tier.C,
        infra_faltante=["OBD pedais"],
        requer_obd=True,
    ),
    Infracao(
        id="R1020-L-e",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.LEVE,
        descricao="Utilizar ou interpretar incorretamente os instrumentos do painel",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[],
        checklist_visual=[],
        tier=Tier.C,
        infra_faltante=["leitura do painel"],
    ),
    Infracao(
        id="R1020-L-f",
        rubrica=Rubrica.RES_1020_2025,
        severidade=Severidade.LEVE,
        descricao="Dar partida ao veículo com engrenagem de tração ligada",
        base_legal="Res. CONTRAN 1.020/2025, Anexo II",
        cameras_relevantes=[Camera.AUDIO],
        checklist_visual=["(áudio) motor partiu com solavanco?"],
        tier=Tier.C,
        infra_faltante=["áudio motor limpo", "OBD câmbio"],
    ),
]


def por_rubrica(
    rubrica: Rubrica = Rubrica.RES_1020_2025, apenas_avaliaveis: bool = True
) -> list[Infracao]:
    """Retorna infrações da rubrica. Por default só Tier A/B (avaliáveis)."""
    items = [i for i in CATALOGO if i.rubrica == rubrica]
    if apenas_avaliaveis:
        items = [i for i in items if i.tier in (Tier.A, Tier.B)]
    return items


def por_camera(camera: Camera, rubrica: Rubrica = Rubrica.RES_1020_2025) -> list[Infracao]:
    return [
        i
        for i in CATALOGO
        if i.rubrica == rubrica and i.tier in (Tier.A, Tier.B) and camera in i.cameras_relevantes
    ]


def por_tier(tier: Tier, rubrica: Rubrica = Rubrica.RES_1020_2025) -> list[Infracao]:
    return [i for i in CATALOGO if i.rubrica == rubrica and i.tier == tier]


def por_id(infracao_id: str) -> Infracao | None:
    for i in CATALOGO:
        if i.id == infracao_id:
            return i
    return None


def pendentes_infraestrutura(rubrica: Rubrica = Rubrica.RES_1020_2025) -> list[Infracao]:
    """Infrações que NÃO podem ser avaliadas com a infra atual."""
    return [i for i in CATALOGO if i.rubrica == rubrica and i.tier == Tier.C]
