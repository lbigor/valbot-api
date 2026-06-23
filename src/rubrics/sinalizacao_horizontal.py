"""
Catálogo de Sinalização Horizontal — MBST Vol IV (CONTRAN 2022).
Fonte oficial: configs/references/mbst_vol_iv_sinalizacao_horizontal.pdf
"""

from dataclasses import dataclass, field
from enum import StrEnum


class CorMarca(StrEnum):
    BRANCA = "branca"
    AMARELA = "amarela"
    VERMELHA = "vermelha"
    AZUL = "azul"


class TipoTraco(StrEnum):
    CONTINUA = "continua"
    SECCIONADA = "seccionada"
    DUPLA_CONTINUA = "dupla_continua"
    DUPLA_SECCIONADA = "dupla_seccionada"
    CONTINUA_SECCIONADA = "continua_seccionada"


@dataclass
class MarcaViaria:
    codigo: str
    nome: str
    cor: CorMarca
    traco: TipoTraco | None
    descricao_visual: str
    regra: str
    infracoes_se_descumprida: list[str] = field(default_factory=list)


MARCAS_LONGITUDINAIS: list[MarcaViaria] = [
    MarcaViaria(
        codigo="LFO-1",
        nome="Linha simples contínua (fluxos opostos)",
        cor=CorMarca.AMARELA,
        traco=TipoTraco.CONTINUA,
        descricao_visual="Faixa AMARELA CONTÍNUA no centro da via, separando sentidos opostos.",
        regra="PROIBIDO ultrapassar e transpor para conversão à esquerda em trecho não sinalizado.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="LFO-2",
        nome="Linha simples seccionada (fluxos opostos)",
        cor=CorMarca.AMARELA,
        traco=TipoTraco.SECCIONADA,
        descricao_visual="Faixa AMARELA TRACEJADA no centro da via.",
        regra="Permitido ultrapassar com segurança e sinalizando.",
    ),
    MarcaViaria(
        codigo="LFO-3",
        nome="Linha dupla contínua (fluxos opostos)",
        cor=CorMarca.AMARELA,
        traco=TipoTraco.DUPLA_CONTINUA,
        descricao_visual="DUAS faixas amarelas contínuas paralelas no centro da via.",
        regra="PROIBIDO ultrapassar em AMBOS os sentidos.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="LFO-4",
        nome="Linha contínua/seccionada",
        cor=CorMarca.AMARELA,
        traco=TipoTraco.CONTINUA_SECCIONADA,
        descricao_visual="Duas faixas amarelas paralelas: UMA CONTÍNUA e UMA SECCIONADA.",
        regra="Permitido ultrapassar apenas para o sentido cuja linha adjacente está seccionada.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="LMS-1",
        nome="Linha simples contínua (mesmo sentido)",
        cor=CorMarca.BRANCA,
        traco=TipoTraco.CONTINUA,
        descricao_visual="Faixa BRANCA CONTÍNUA entre faixas do mesmo sentido.",
        regra="PROIBIDA a mudança de faixa. Transpor é infração grave.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="LMS-2",
        nome="Linha simples seccionada (mesmo sentido)",
        cor=CorMarca.BRANCA,
        traco=TipoTraco.SECCIONADA,
        descricao_visual="Faixa BRANCA TRACEJADA entre faixas de mesmo sentido.",
        regra="Mudança de faixa permitida, com sinalização prévia (seta).",
    ),
    MarcaViaria(
        codigo="LBO",
        nome="Linha de bordo",
        cor=CorMarca.BRANCA,
        traco=TipoTraco.CONTINUA,
        descricao_visual="Faixa BRANCA CONTÍNUA nos bordos externos da pista.",
        regra="Transpor sobre calçada = subir no meio-fio = ELIMINATÓRIA.",
        infracoes_se_descumprida=["789_elim_02"],
    ),
]


MARCAS_TRANSVERSAIS: list[MarcaViaria] = [
    MarcaViaria(
        codigo="LRE",
        nome="Linha de retenção",
        cor=CorMarca.BRANCA,
        traco=TipoTraco.CONTINUA,
        descricao_visual="Faixa BRANCA espessa, CONTÍNUA, TRANSVERSAL à via. Aparece antes de semáforos e PARE.",
        regra="Veículo deve parar ATRÁS da linha. Ultrapassá-la com vermelho ou PARE = eliminatória.",
        infracoes_se_descumprida=["789_elim_01", "1020_grave_03"],
    ),
    MarcaViaria(
        codigo="LDP",
        nome="Linha de 'Dê a Preferência'",
        cor=CorMarca.BRANCA,
        traco=TipoTraco.SECCIONADA,
        descricao_visual="Série de TRIÂNGULOS brancos apontando para o condutor, ou linha transversal tracejada.",
        regra="Reduzir velocidade e ceder passagem.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="FTP",
        nome="Faixa de travessia de pedestres (zebra)",
        cor=CorMarca.BRANCA,
        traco=None,
        descricao_visual="FAIXAS BRANCAS LARGAS paralelas ao sentido de tráfego, formando 'zebra crossing'.",
        regra="Parar se houver pedestre cruzando. Nunca parar SOBRE a faixa.",
        infracoes_se_descumprida=["789_elim_01", "789_grave_05"],
    ),
    MarcaViaria(
        codigo="LRV",
        nome="Linhas de estímulo à redução de velocidade",
        cor=CorMarca.BRANCA,
        traco=TipoTraco.CONTINUA,
        descricao_visual="Várias faixas brancas transversais curtas com espaçamento decrescente.",
        regra="Sinalização de alerta — reduzir velocidade esperada.",
    ),
]


MARCAS_CANALIZACAO: list[MarcaViaria] = [
    MarcaViaria(
        codigo="LCA",
        nome="Linha de canalização",
        cor=CorMarca.BRANCA,
        traco=TipoTraco.CONTINUA,
        descricao_visual="Faixa branca contínua que delimita ilhas físicas ou virtuais.",
        regra="Proibido cruzar — direciona o veículo para a faixa correta.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="ZPA",
        nome="Zebrado de preenchimento (área não utilizável)",
        cor=CorMarca.BRANCA,
        traco=None,
        descricao_visual="Área triangular ou trapezoidal com faixas DIAGONAIS brancas paralelas.",
        regra="PROIBIDO circular, parar ou estacionar sobre o zebrado.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
]


MARCAS_ESTACIONAMENTO: list[MarcaViaria] = [
    MarcaViaria(
        codigo="LPP",
        nome="Linha de proibição de parada/estacionamento",
        cor=CorMarca.AMARELA,
        traco=TipoTraco.CONTINUA,
        descricao_visual="Faixa AMARELA CONTÍNUA pintada na guia (meio-fio) ou borda direita.",
        regra="Proibido parar e estacionar no trecho marcado.",
    ),
]


INSCRICOES_PAVIMENTO: list[MarcaViaria] = [
    MarcaViaria(
        codigo="PEM",
        nome="Seta de posicionamento na pista",
        cor=CorMarca.BRANCA,
        traco=None,
        descricao_visual="Grande seta BRANCA pintada no meio da faixa indicando movimentos permitidos.",
        regra="Candidato deve executar APENAS o movimento indicado pela seta.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="MOF",
        nome="Seta de mudança obrigatória de faixa",
        cor=CorMarca.BRANCA,
        traco=None,
        descricao_visual="Seta branca apontando diagonalmente para faixa adjacente.",
        regra="Candidato deve mudar de faixa conforme indicado.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="SIP",
        nome="Símbolo 'Dê a preferência' no pavimento",
        cor=CorMarca.BRANCA,
        traco=None,
        descricao_visual="Triângulo isósceles BRANCO apontado para o condutor.",
        regra="Ceder passagem à via transversal.",
        infracoes_se_descumprida=["789_grave_05"],
    ),
    MarcaViaria(
        codigo="SIF",
        nome="Cruz de Santo André (rodoferroviário)",
        cor=CorMarca.BRANCA,
        traco=None,
        descricao_visual="X branco gigante no pavimento antes de cruzamento com trilhos.",
        regra="Parar, olhar, prosseguir apenas se não houver trem.",
        infracoes_se_descumprida=["789_elim_01"],
    ),
]


CATALOGO_HORIZONTAL: list[MarcaViaria] = (
    MARCAS_LONGITUDINAIS
    + MARCAS_TRANSVERSAIS
    + MARCAS_CANALIZACAO
    + MARCAS_ESTACIONAMENTO
    + INSCRICOES_PAVIMENTO
)


def marcas_para_prompt(somente_criticas: bool = True) -> str:
    marcas = [
        m for m in CATALOGO_HORIZONTAL if (m.infracoes_se_descumprida or not somente_criticas)
    ]
    linhas = []
    for m in marcas:
        traco_txt = f" [{m.traco.value}]" if m.traco else ""
        linhas.append(
            f"- {m.codigo} ({m.cor.value}{traco_txt}): {m.nome}\n"
            f"    visual: {m.descricao_visual}\n"
            f"    regra: {m.regra}"
        )
    return "\n".join(linhas)


def por_codigo(codigo: str) -> MarcaViaria | None:
    for m in CATALOGO_HORIZONTAL:
        if m.codigo == codigo:
            return m
    return None
