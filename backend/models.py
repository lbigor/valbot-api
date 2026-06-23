"""Contratos pydantic de toda a plataforma Val Auditor Exames.

Cada bloco corresponde a uma saída de motor da Especificação Funcional v2.0:

    §5.4  PayloadExame          — entrada do Motor de Evidências
    §6.3  EventoDetectado       — saída do Motor de Detecção (evento bruto)
    §7.3  Enquadramento         — saída do Motor Normativo
    §8.3  ResultadoPontuacao    — saída do Motor de Pontuação
    §9.4  Comparacao            — saída do Motor de Comparação (5 divergências)
    §10.3 LaudoComite           — saída do Comitê de IA
    §11   ParecerAuditor / DecisaoSupervisor — fluxo humano de 4 níveis
    §12   OrdemServico          — gestão de OS

Os enums são a fonte da verdade de vocabulário; o resto do backend importa
daqui em vez de repetir strings literais.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Vocabulário canônico (enums)
# ---------------------------------------------------------------------------


class Natureza(StrEnum):
    """Natureza da infração — define o peso (spec §3.2)."""

    LEVE = "leve"
    MEDIA = "media"
    GRAVE = "grave"
    GRAVISSIMA = "gravissima"


PESO_POR_NATUREZA: dict[Natureza, int] = {
    Natureza.LEVE: 1,
    Natureza.MEDIA: 2,
    Natureza.GRAVE: 4,
    Natureza.GRAVISSIMA: 6,
}

LIMITE_APROVACAO = 10
"""Pontuação acumulada ≤ 10 → aprovado (Resolução CONTRAN 1.020/2025, Art. 45)."""


class ResultadoExame(StrEnum):
    """Decisão de um exame (oficial ou calculada)."""

    APROVADO = "aprovado"
    REPROVADO = "reprovado"
    INTERROMPIDO = "interrompido"
    NAO_AVALIADO = "nao_avaliado"


# Mapeamento do código compacto do integrador (A/R/N) ↔ ResultadoExame.
CODIGO_PARA_RESULTADO: dict[str, ResultadoExame] = {
    "A": ResultadoExame.APROVADO,
    "R": ResultadoExame.REPROVADO,
    "N": ResultadoExame.NAO_AVALIADO,
    "I": ResultadoExame.INTERROMPIDO,
}
RESULTADO_PARA_CODIGO: dict[ResultadoExame, str] = {
    ResultadoExame.APROVADO: "A",
    ResultadoExame.REPROVADO: "R",
    ResultadoExame.NAO_AVALIADO: "N",
    ResultadoExame.INTERROMPIDO: "I",
}


class TipoExame(StrEnum):
    PRIMEIRA_HABILITACAO = "primeira_habilitacao"
    ADICAO = "adicao"
    MUDANCA = "mudanca"
    RENOVACAO = "renovacao"
    DESCONHECIDO = "desconhecido"


class CategoriaCNH(StrEnum):
    ACC = "ACC"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class TipoDivergencia(StrEnum):
    """Os 5 tipos de divergência (spec §9.2) + ausência de divergência."""

    SEM_DIVERGENCIA = "sem_divergencia"
    RESULTADO = "1_resultado"
    PONTUACAO = "2_pontuacao"
    INFRACAO = "3_infracao"
    ENQUADRAMENTO = "4_enquadramento"
    EVIDENCIA_INSUFICIENTE = "5_evidencia_insuficiente"


class Encaminhamento(StrEnum):
    """Para onde o exame vai após o Motor de Comparação (spec §2.3)."""

    ENCERRAMENTO = "encerramento"  # sem divergência → arquiva
    COMITE_DE_IA = "comite_de_ia"  # com divergência → aprofunda e abre OS


class StatusOS(StrEnum):
    """Ciclo de vida da Ordem de Serviço (spec §12.2).

    A OS nasce no ``init_upload`` (cada vídeo é uma OS), passa pela análise da
    IA e só então bifurca: sem divergência encerra (arquiva sem humano), com
    divergência segue Auditor → Supervisor.
    """

    CRIADA = "criada"  # criada no init_upload (relógio do SLA inicia aqui)
    EM_ANALISE_IA = "em_analise_ia"  # IA Principal + Comitê processando
    AGUARDANDO_AUDITOR = "aguardando_auditor"
    EM_ANALISE_AUDITOR = "em_analise_auditor"
    CONCLUIDA_AUDITOR = "concluida_auditor"
    AGUARDANDO_SUPERVISOR = "aguardando_supervisor"
    EM_ANALISE_SUPERVISOR = "em_analise_supervisor"
    DECISAO_FINAL = "decisao_final"
    ENCERRADA = "encerrada"


class NivelDecisao(StrEnum):
    """Os 4 níveis de decisão (spec §11.2)."""

    IA_PRINCIPAL = "1_ia_principal"
    COMITE = "2_comite"
    AUDITOR = "3_auditor"
    SUPERVISOR = "4_supervisor"


class TipoCompliance(StrEnum):
    """Origem de um comentário de compliance (sinal NÃO-pontuável).

    Reúne o que não soma pontos no exame mas exige análise humana numa tela
    dedicada: conduta inadequada do examinador (§6/§10), conduta do candidato
    do MBEDV §4-5 (fraude/desacato/etc.) e condutas detectadas fora do escopo
    pontuável do MBEDV (cinto, baliza, técnicas de exame).
    """

    EXAMINADOR_INADEQUADO = "examinador_inadequado"
    CONDUTA_CANDIDATO = "conduta_candidato"
    CONDUTA_SEM_FICHA = "conduta_sem_ficha"


# ---------------------------------------------------------------------------
# §5.4 — Entrada do Motor de Evidências
# ---------------------------------------------------------------------------


class CandidatoPayload(BaseModel):
    nome: str | None = None
    cpf_mascarado: str | None = None
    categoria_pretendida: CategoriaCNH | None = None
    renach: str | None = None
    processo: str | None = None


class ExaminadorPayload(BaseModel):
    matricula: str | None = None
    nome: str | None = None
    eh_preposto: bool = False


class InfracaoOficial(BaseModel):
    """Infração apontada oficialmente pela Comissão (spec §5.4)."""

    artigo_ctb: str
    natureza: Natureza | None = None
    peso: int | None = None


class ResultadoOficial(BaseModel):
    decisao: ResultadoExame
    pontuacao: int | None = None
    houve_interrupcao: bool = False
    motivo_interrupcao: str | None = None
    infracoes: list[InfracaoOficial] = Field(default_factory=list)


class PayloadExame(BaseModel):
    """Payload completo de um exame conforme spec §5.4.

    Campos opcionais refletem a realidade da integração atual (o DETRAN/
    Techpark hoje só envia ``url`` + ``renach`` + ``categoria``); o Motor de
    Evidências valida o que está presente e marca o que falta.
    """

    exame_id: str | None = None
    url_video: str
    url_audio: str | None = None
    hash_video: str | None = None
    duracao_video_seg: float | None = None
    unidade: str | None = None
    data_hora_exame: str | None = None
    tipo_exame: TipoExame = TipoExame.DESCONHECIDO
    candidato: CandidatoPayload = Field(default_factory=CandidatoPayload)
    examinador: ExaminadorPayload = Field(default_factory=ExaminadorPayload)
    resultado_oficial: ResultadoOficial | None = None
    trajeto_definido: dict | None = None
    telemetria: dict | None = None
    veiculo: str | None = None
    auto_escola: str | None = None
    rubrica: str = "1020/2025"
    training_annotations: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# §6.3 — Saída do Motor de Detecção (eventos brutos, sem julgamento normativo)
# ---------------------------------------------------------------------------


class EventoDetectado(BaseModel):
    evento_id: str
    categoria: str  # trajetoria | sinalizacao | velocidade | comportamento | ...
    descricao: str
    timestamp_video_seg: float | None = None
    timestamp_audio_seg: float | None = None
    duracao_seg: float | None = None
    confianca: float = 0.0  # 0..1
    canal_evidencia: str = "visao"  # visao | audio | ambos
    quadrante_origem: str | None = None
    camera_origem: str | None = None
    transcricao: str | None = None
    classificacao: str | None = None  # p/ eventos do examinador (comentário inadequado)
    contexto_adicional: dict = Field(default_factory=dict)


class SaidaDeteccao(BaseModel):
    exame_id: str
    modelo_versao: str
    eventos_detectados: list[EventoDetectado] = Field(default_factory=list)
    comentarios_examinador: list[EventoDetectado] = Field(default_factory=list)
    audio_disponivel: bool = False
    evidencia_suficiente: bool = True


# ---------------------------------------------------------------------------
# §7.3 — Saída do Motor Normativo (enquadramento)
# ---------------------------------------------------------------------------


class Enquadramento(BaseModel):
    evento_id: str
    enquadrado: bool
    regra_aplicada: str | None = None
    artigo_ctb: str | None = None
    ficha_mbedv: str | None = None
    natureza: Natureza | None = None
    peso: int | None = None
    excecao_aplicada: str | None = None
    justificativa: str = ""
    confianca_enquadramento: float = 0.0
    requer_revisao_humana: bool = False
    timestamp_s: float | None = None


class EventoNaoEnquadrado(BaseModel):
    evento_id: str
    motivo: str


class SaidaNormativo(BaseModel):
    exame_id: str
    matriz_versao: str
    enquadramentos: list[Enquadramento] = Field(default_factory=list)
    eventos_nao_enquadrados: list[EventoNaoEnquadrado] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# §8.3 — Saída do Motor de Pontuação
# ---------------------------------------------------------------------------


class InfracaoCalculada(BaseModel):
    artigo_ctb: str
    regra_aplicada: str | None = None
    natureza: Natureza
    peso: int
    timestamp_s: float | None = None


class ResultadoPontuacao(BaseModel):
    exame_id: str
    resultado_calculado: ResultadoExame
    pontuacao_calculada: int | None = None
    limite_reprovacao: int = LIMITE_APROVACAO
    houve_interrupcao: bool = False
    motivo_interrupcao: str | None = None
    infracoes_calculadas: list[InfracaoCalculada] = Field(default_factory=list)
    matriz_versao: str = ""
    modelo_deteccao_versao: str = ""


# ---------------------------------------------------------------------------
# §9.4 — Saída do Motor de Comparação
# ---------------------------------------------------------------------------


class Comparacao(BaseModel):
    exame_id: str
    resultado_oficial: ResultadoExame | None = None
    resultado_calculado: ResultadoExame
    pontuacao_oficial: int | None = None
    pontuacao_calculada: int | None = None
    tipo_divergencia: TipoDivergencia
    subtipos_associados: list[TipoDivergencia] = Field(default_factory=list)
    concorda_resultado: bool = False
    concorda_pontuacao: bool = False
    concorda_infracoes: bool = False
    evidencia_suficiente: bool = True
    detalhes: dict = Field(default_factory=dict)
    encaminhamento: Encaminhamento = Encaminhamento.ENCERRAMENTO


# ---------------------------------------------------------------------------
# §10.3 — Saída do Comitê de IA
# ---------------------------------------------------------------------------


class CausaIdentificada(BaseModel):
    causa: str
    evidencia: str
    interpretacao_normativa: str = ""
    confianca_causa: float = 0.0


class VerificacaoComite(BaseModel):
    regra: str
    segmento: str
    resultado: str  # infracao_confirmada | excecao_aplicavel | nao_confirmada | ...


class ComentarioExaminador(BaseModel):
    timestamp_audio: float | None = None
    transcricao: str
    classificacao: str


class LaudoComite(BaseModel):
    exame_id: str
    comite_versao: str
    data_hora_processamento: str | None = None
    tempo_processamento_seg: float | None = None
    tipo_divergencia_analisada: TipoDivergencia
    causas_identificadas: list[CausaIdentificada] = Field(default_factory=list)
    verificacoes_executadas: list[VerificacaoComite] = Field(default_factory=list)
    comentarios_examinador_detectados: list[ComentarioExaminador] = Field(default_factory=list)
    recomendacao_para_auditor: str = ""
    conclusao_comite: str = ""  # concorda_com_examinador | manter_divergencia_com_fundamentacao
    # Decisão pós-comitê (evolução §10): após reavaliar com o prompt MBEDV, o
    # comitê pode CONCORDAR com o examinador (divergência resolvida → não vai
    # pra fila) ou MANTER a divergência (segue pro Auditor). None = não avaliado;
    # SEM_DIVERGENCIA = resolvida pelo comitê.
    tipo_divergencia_pos_comite: TipoDivergencia | None = None


# ---------------------------------------------------------------------------
# §11 / §12 — Fluxo humano e Ordens de Serviço
# ---------------------------------------------------------------------------


class ParecerAuditor(BaseModel):
    os_id: str
    auditor_email: str
    decisao: str  # concorda_ia | discorda_ia | inconclusivo
    justificativa: str
    referencia_mbedv: str | None = None


class DecisaoSupervisor(BaseModel):
    os_id: str
    supervisor_email: str
    decisao_final: ResultadoExame | str
    concorda_auditor: bool
    justificativa: str


class ComentarioCompliance(BaseModel):
    """Sinal não-pontuável encaminhado à análise de compliance (tela dedicada)."""

    exame_id: str
    tipo: TipoCompliance
    descricao: str
    origem_codigo: str | None = None  # ex: R1020-GR-f (cinto), regra/artigo de origem
    timestamp_s: float | None = None
    transcricao: str | None = None
    classificacao: str | None = None
    severidade: str | None = None  # informativo | atencao | grave (compliance, não pontua)
    status: str = "pendente"  # pendente | analisado | arquivado


class OrdemServico(BaseModel):
    os_id: str
    numero_os: str | None = None  # número de negócio = ID gerado no init_upload
    exame_id: str
    tipo_divergencia: TipoDivergencia | None = None  # só definido após a análise
    status: StatusOS = StatusOS.CRIADA
    auditor_email: str | None = None
    supervisor_email: str | None = None
    criada_em: str | None = None  # = início do SLA (momento do init_upload)
    sla_inicio: str | None = None
    sla_horas_decorridas: float | None = None
    sla_estourado: bool = False
    atualizada_em: str | None = None
    parecer_auditor: ParecerAuditor | None = None
    decisao_supervisor: DecisaoSupervisor | None = None
