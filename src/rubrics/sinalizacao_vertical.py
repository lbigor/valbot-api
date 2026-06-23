"""
Catálogo de Sinalização Vertical — CONTRAN, Anexo II do CTB.
Fonte oficial: configs/references/contran_anexo_ii_placas.pdf
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Categoria(StrEnum):
    REGULAMENTACAO = "R"
    ADVERTENCIA = "A"
    INDICACAO = "I"


class Forma(StrEnum):
    CIRCULAR = "circular"
    OCTOGONAL = "octogonal"
    TRIANGULAR = "triangular"
    QUADRADA_DIAGONAL = "quadrada_diagonal"
    RETANGULAR = "retangular"


@dataclass
class Placa:
    codigo: str
    nome: str
    categoria: Categoria
    forma: Forma
    cores: str
    descricao_visual: str
    implicacao: str
    infracoes_associadas: list[str] = field(default_factory=list)
    exige_verificacao_comportamento: bool = False


PLACAS_REGULAMENTACAO: list[Placa] = [
    Placa(
        codigo="R-1",
        nome="Parada Obrigatória (PARE)",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.OCTOGONAL,
        cores="fundo vermelho, letras brancas 'PARE', orla interna branca",
        descricao_visual="Placa octogonal (8 lados) vermelha com a palavra PARE em branco.",
        implicacao="Candidato DEVE parar COMPLETAMENTE antes da faixa de retenção. Parada rolante = eliminatória.",
        infracoes_associadas=["789_elim_01", "1020_grave_03"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-2",
        nome="Dê a Preferência",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.TRIANGULAR,
        cores="triângulo invertido vermelho com orla branca interna",
        descricao_visual="Triângulo equilátero invertido (ponta para baixo) vermelho com borda branca interna.",
        implicacao="Candidato deve reduzir e dar passagem aos veículos da via preferencial.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-3",
        nome="Sentido Proibido",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="círculo vermelho com tarja branca horizontal no centro",
        descricao_visual="Círculo totalmente vermelho com uma faixa retangular branca horizontal no meio.",
        implicacao="Entrada proibida — candidato jamais deve cruzar.",
        infracoes_associadas=["789_elim_01"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-4a",
        nome="Proibido Virar à Esquerda",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla e tarja diagonal vermelhas, seta preta",
        descricao_visual="Círculo branco com seta preta curvando à esquerda cortada por tarja diagonal vermelha.",
        implicacao="Candidato não pode realizar conversão à esquerda.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-4b",
        nome="Proibido Virar à Direita",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla e tarja diagonal vermelhas, seta preta",
        descricao_visual="Idêntica à R-4a mas com a seta apontando à direita.",
        implicacao="Candidato não pode realizar conversão à direita.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-5",
        nome="Proibido Retornar (em U)",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla vermelha, símbolo U preto cortado",
        descricao_visual="Círculo branco com seta em U preta cortada por tarja vermelha.",
        implicacao="Candidato não pode fazer retorno no local.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-6a",
        nome="Proibido Estacionar",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo azul, orla e tarja diagonal vermelhas, letra E",
        descricao_visual="Círculo azul com 'E' branco grande cortado por tarja diagonal vermelha.",
        implicacao="Candidato não pode estacionar no trecho sinalizado.",
    ),
    Placa(
        codigo="R-7",
        nome="Proibido Ultrapassar",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, dois carros lado a lado, orla vermelha",
        descricao_visual="Círculo branco mostrando dois veículos lado a lado (preto e vermelho).",
        implicacao="Ultrapassagem é infração grave no trecho sinalizado.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-19",
        nome="Velocidade Máxima Permitida",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla vermelha, número preto em km/h",
        descricao_visual="Círculo branco com número em preto (ex: 40, 60, 80) e 'km/h'. Orla vermelha grossa.",
        implicacao="Velocidade do veículo não pode exceder o valor indicado.",
        infracoes_associadas=["789_media_02"],
        exige_verificacao_comportamento=False,
    ),
    Placa(
        codigo="R-20",
        nome="Proibido Acionar Buzina",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla vermelha, símbolo de buzina preto cortado",
        descricao_visual="Círculo branco com ícone de buzina cortado por tarja vermelha.",
        implicacao="Candidato não pode buzinar no trecho.",
        infracoes_associadas=["789_grave_01"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-25a",
        nome="Vire à Esquerda (obrigatório)",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla vermelha, seta preta curvando à esquerda",
        descricao_visual="Círculo branco com seta preta OBRIGANDO conversão à esquerda.",
        implicacao="Candidato DEVE virar à esquerda.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-25b",
        nome="Vire à Direita (obrigatório)",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla vermelha, seta preta curvando à direita",
        descricao_visual="Círculo branco com seta preta OBRIGANDO conversão à direita.",
        implicacao="Candidato DEVE virar à direita.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-26",
        nome="Siga em Frente (obrigatório)",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla vermelha, seta preta reta",
        descricao_visual="Círculo branco com seta preta reta apontando para cima.",
        implicacao="Candidato DEVE prosseguir reto.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="R-33",
        nome="Sentido Circular Obrigatório",
        categoria=Categoria.REGULAMENTACAO,
        forma=Forma.CIRCULAR,
        cores="fundo branco, orla vermelha, três setas em círculo",
        descricao_visual="Círculo branco com três setas pretas formando movimento rotatório anti-horário.",
        implicacao="Candidato deve ingressar na rotatória pela direita e circular no sentido das setas.",
        infracoes_associadas=["789_grave_05"],
        exige_verificacao_comportamento=True,
    ),
]


PLACAS_ADVERTENCIA: list[Placa] = [
    Placa(
        codigo="A-1a",
        nome="Curva Acentuada à Esquerda",
        categoria=Categoria.ADVERTENCIA,
        forma=Forma.QUADRADA_DIAGONAL,
        cores="amarelo com orla preta, símbolo preto de curva fechada",
        descricao_visual="Losango amarelo com seta preta curvando fortemente à esquerda.",
        implicacao="Espera-se redução de velocidade.",
        infracoes_associadas=["789_leve_01"],
    ),
    Placa(
        codigo="A-1b",
        nome="Curva Acentuada à Direita",
        categoria=Categoria.ADVERTENCIA,
        forma=Forma.QUADRADA_DIAGONAL,
        cores="amarelo com orla preta, seta preta curvando à direita",
        descricao_visual="Losango amarelo com seta preta curvando à direita.",
        implicacao="Redução de velocidade esperada.",
        infracoes_associadas=["789_leve_01"],
    ),
    Placa(
        codigo="A-14",
        nome="Semáforo à Frente",
        categoria=Categoria.ADVERTENCIA,
        forma=Forma.QUADRADA_DIAGONAL,
        cores="amarelo com três círculos empilhados",
        descricao_visual="Losango amarelo com ícone de semáforo vertical (3 círculos).",
        implicacao="Candidato deve estar atento e reduzir.",
        infracoes_associadas=["789_elim_01"],
    ),
    Placa(
        codigo="A-15",
        nome="Parada Obrigatória à Frente",
        categoria=Categoria.ADVERTENCIA,
        forma=Forma.QUADRADA_DIAGONAL,
        cores="amarelo com ícone da placa R-1 reduzido",
        descricao_visual="Losango amarelo contendo uma mini-placa octogonal vermelha 'PARE'.",
        implicacao="Anúncio de PARE à frente — reduzir antecipadamente.",
    ),
    Placa(
        codigo="A-18",
        nome="Saliência ou Lombada",
        categoria=Categoria.ADVERTENCIA,
        forma=Forma.QUADRADA_DIAGONAL,
        cores="amarelo com silhueta de carro passando por lombada",
        descricao_visual="Losango amarelo com veículo estilizado sobre elevação do solo.",
        implicacao="Redução obrigatória — passar rápido = infração leve.",
        infracoes_associadas=["789_leve_01"],
    ),
    Placa(
        codigo="A-32a",
        nome="Passagem de Pedestres",
        categoria=Categoria.ADVERTENCIA,
        forma=Forma.QUADRADA_DIAGONAL,
        cores="amarelo com silhueta de pedestre",
        descricao_visual="Losango amarelo com figura preta de pessoa caminhando.",
        implicacao="Redução de velocidade e atenção a travessia.",
    ),
    Placa(
        codigo="A-32b",
        nome="Passagem Sinalizada de Pedestres",
        categoria=Categoria.ADVERTENCIA,
        forma=Forma.QUADRADA_DIAGONAL,
        cores="amarelo com pedestre sobre faixa riscada",
        descricao_visual="Losango amarelo com pedestre andando sobre faixas verticais.",
        implicacao="Faixa de pedestres à frente — parar se houver pedestre atravessando.",
        infracoes_associadas=["789_elim_01"],
        exige_verificacao_comportamento=True,
    ),
    Placa(
        codigo="A-33a",
        nome="Área Escolar",
        categoria=Categoria.ADVERTENCIA,
        forma=Forma.QUADRADA_DIAGONAL,
        cores="amarelo com silhueta de dois estudantes",
        descricao_visual="Losango amarelo com duas figuras pretas lado a lado.",
        implicacao="Velocidade reduzida e atenção redobrada.",
    ),
]


PLACAS_INDICACAO_RELEVANTES: list[Placa] = [
    Placa(
        codigo="I-23",
        nome="Ponto de Parada (ônibus)",
        categoria=Categoria.INDICACAO,
        forma=Forma.RETANGULAR,
        cores="fundo azul com ícone branco de ônibus",
        descricao_visual="Retângulo azul com silhueta branca de ônibus.",
        implicacao="Ponto de ônibus — estacionar aqui pode ser infração.",
    ),
]


CATALOGO_VERTICAL: list[Placa] = (
    PLACAS_REGULAMENTACAO + PLACAS_ADVERTENCIA + PLACAS_INDICACAO_RELEVANTES
)


def placas_para_prompt(apenas_comportamento: bool = True) -> str:
    placas = [
        p
        for p in CATALOGO_VERTICAL
        if (p.exige_verificacao_comportamento or not apenas_comportamento)
    ]
    linhas = []
    for p in placas:
        linhas.append(
            f"- {p.codigo} [{p.forma.value}]: {p.nome}\n"
            f"    visual: {p.descricao_visual}\n"
            f"    comportamento esperado: {p.implicacao}"
        )
    return "\n".join(linhas)


def por_codigo(codigo: str) -> Placa | None:
    for p in CATALOGO_VERTICAL:
        if p.codigo == codigo:
            return p
    return None
