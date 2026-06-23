/* ============================================================================
   ValBot — camada de dados (mock) que ESPELHA o backend de produção (lbigor/valbot@v2)
   Porte fiel de .design-ref/vb-data.js → TypeScript determinístico.
   Schemas reais refletidos: exams / v_exams_overview (004), exam_infractions (004),
   ordens_servico + pareceres + decisoes + comite (013/017), auditor_telemetria (020),
   cron_jobs + cron_job_runs (021), admin_users (018), exam_rules (017),
   métricas do dashboard (backend/dashboard/metrics.py) e modelo de custo (PLANILHA_CUSTOS.csv).
   Tudo determinístico (PRNG com seed) para os números baterem entre as páginas.

   IMPORTANTE: a sequência de chamadas ao PRNG global define os valores. A ordem de
   geração (exams → ordens → telemetria → cron_runs) é preservada exatamente como no
   protótipo. As funções de métricas que consomem rng() (custos, etc.) permanecem
   não-determinísticas entre chamadas — comportamento idêntico ao original.

   `fmt` é re-exportado de ./ui (NÃO redefinido aqui).
   ============================================================================ */
import { fmt } from "./ui";

/* ---- PRNG determinístico (mulberry32) ---- */
let _seed = 0x9e3779b9;
function rng(): number {
  _seed |= 0;
  _seed = (_seed + 0x6d2b79f5) | 0;
  let t = Math.imul(_seed ^ (_seed >>> 15), 1 | _seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const ri = (a: number, b: number): number => a + Math.floor(rng() * (b - a + 1));
const pick = <T>(arr: T[]): T => arr[Math.floor(rng() * arr.length)];
const chance = (p: number): boolean => rng() < p;

/* ============================================================================
   TIPOS EXPORTADOS — shapes consumidos pelas telas
   ============================================================================ */

export type Gravidade = "gravissima" | "grave" | "media" | "leve";

export interface GravMeta {
  label: string;
  pontos: number;
  color: string;
  bg: string;
  ring: string;
}

export interface Rule {
  codigo: string;
  grav: Gravidade;
  nome: string;
  ctb: string;
  pontos: number;
}

export interface Engine {
  model: string;
  preset: string;
  tin: number;
  tout: number;
}

export interface ModeloCusto {
  nome: string;
  provider: string;
  tin: number;
  tout: number;
  in_M: number;
  out_M: number;
  video_usd: number;
  tempo_s: number;
  atual?: boolean;
}

export interface Infracao {
  regra_id: string;
  gravidade: Gravidade;
  pontos: number;
  descricao: string;
  timestamp_s: number;
  duracao_s: number;
  confianca: number;
  cameras: string[];
  base_legal: string;
  status: string;
}

export type ExamStatus = "running" | "queued" | "failed" | "done";
export type Resultado =
  | "PROCESSANDO"
  | "PENDENTE"
  | "FALHOU"
  | "SEM_AVALIACAO"
  | "APROVADO"
  | "INAPTO";
export type TipoDivergencia =
  | "1_resultado"
  | "2_pontuacao"
  | "3_infracao"
  | "4_enquadramento"
  | "5_evidencia_insuficiente";

export interface Exame {
  id: string;
  hash: string;
  external_id: string;
  candidato_nome: string;
  candidato_cpf: string;
  renach: string;
  examinador: string;
  unidade: string;
  local_unidade: string;
  auto_escola: string;
  categoria: string;
  veiculo: string;
  status: ExamStatus;
  resultado: Resultado;
  aprovado: boolean | null;
  pontuacao_total: number;
  gate_rejected: boolean;
  gate_motivo: string | null;
  houve_interrupcao: boolean;
  size_mb: number;
  duration_s: number;
  num_infracoes: number;
  cost_usd: number | null;
  cost_tokens_in: number | null;
  cost_tokens_out: number | null;
  gemini_elapsed_s: number | null;
  engine_model: string;
  engine_preset: string;
  infracoes: Infracao[];
  resultado_oficial: string | null;
  resultado_calculado: string | null;
  diverge: boolean;
  tipo_divergencia: TipoDivergencia | null;
  created_at: Date;
  /* preenchidos na fase de telemetria */
  num_acessos?: number;
  ultimo_acesso?: Date | null;
}

export type StatusOS =
  | "aguardando_auditor"
  | "em_analise_auditor"
  | "aguardando_supervisor"
  | "encerrada";

export interface Ordem {
  os_id: string;
  numero_os: string;
  exam_id: string;
  exam_hash: string;
  candidato_nome: string;
  renach: string;
  categoria: string;
  unidade: string;
  examinador: string;
  tipo_divergencia: TipoDivergencia | null;
  tipo_label: string;
  status: StatusOS;
  prioridade: number;
  resultado_oficial: string | null;
  resultado_calculado: string | null;
  pontuacao_oficial: number;
  pontuacao_calculada: number;
  auditor_email: string | null;
  supervisor_email: string | null;
  aberta_em: Date;
  sla_horas: number;
  sla_due_at: Date;
  sla_estourado: boolean;
  conf: number;
}

export interface TelemetriaAgg {
  auditor: string;
  exam_hash: string;
  assistido_ate_seg: number;
  dur_seg: number;
  tempo_sessao_s: number;
  avancos_bloqueados: number;
  created_at: Date;
}

export interface Acesso {
  exam_id: string;
  exam_hash: string;
  usuario: string;
  auditor: string;
  papel: string;
  entrou_em: Date;
  created_at: Date;
  saiu_em: Date;
  tempo_sessao_s: number;
  assistido_ate_seg: number;
  dur_seg: number;
  assistido_pct: number;
  avancos_bloqueados: number;
  dispositivo: string;
  ip: string;
  acao: string;
}

export interface CronJob {
  id: string;
  nome: string;
  enabled: boolean;
  schedule_kind: "daily" | "hourly" | "interval" | "cron";
  horario: string | null;
  cron_expr: string | null;
  batch_limit: number;
  retry: number;
  escopo: string;
}

export interface CronRun {
  id: string;
  cron_job_id: string;
  nome: string;
  iniciado_em: Date;
  finalizado_em: Date | null;
  n_processados: number;
  n_falhas: number;
  custo_usd: number;
  status: "running" | "failed" | "success";
}

export interface Usuario {
  id: string;
  email: string;
  nome: string;
  role: "admin" | "supervisor" | "auditor";
  created_at: Date;
  last_login_at: Date;
  revoked_at: Date | null;
}

export interface OperacionaisMetrics {
  periodo_dias: number;
  total_recebidos: number;
  total_processados: number;
  por_status: Record<string, number>;
  taxa_erro: number;
  tempo_medio_analise_s: number;
  custo_total_usd: number;
  os_pendentes_por_status: Record<string, number>;
}

export interface RegulatoriosMetrics {
  periodo_dias: number;
  concordancia_resultado_pct: number;
  concordancia_pontuacao_pct: number;
  distribuicao_divergencias: Record<string, number>;
  top_infracoes: Record<string, number>;
  divergencia_por_unidade: Record<string, number>;
  divergencia_por_examinador: Record<string, number>;
  divergencia_por_categoria: Record<string, number>;
  taxa_interrupcao_pct: number;
  taxa_evidencia_insuficiente_pct: number;
  comentarios_inadequados_examinador: number;
}

export interface CustoSerieDia {
  dia: string;
  num_exames: number;
  custo_usd: number;
}

export interface CustoRotuloItem {
  rotulo: string;
  num_exames: number;
  custo_usd: number;
}

export interface CustosMetrics {
  periodo_dias: number;
  custo_total_usd: number;
  num_exames_cobrados: number;
  custo_medio_por_exame_usd: number;
  tokens_in_total: number;
  tokens_out_total: number;
  serie_diaria: CustoSerieDia[];
  por_unidade: CustoRotuloItem[];
  por_categoria: CustoRotuloItem[];
}

export interface SupervisorMetrics {
  periodo_dias: number;
  total_decisoes: number;
  homologadas: number;
  reformadas: number;
  concordancia_supervisor_auditor_pct: number;
  concordancia_supervisor_ia_pct: number;
}

export interface ComplianceMetrics {
  pendente: number;
  examinador_inadequado: number;
  conduta_candidato: number;
  conduta_sem_ficha: number;
}

export interface ResumoMetrics {
  periodo_dias: number;
  operacionais: OperacionaisMetrics;
  regulatorios: RegulatoriosMetrics;
  custos: CustosMetrics;
  supervisor: SupervisorMetrics;
  compliance: ComplianceMetrics;
}

/* ============================================================================
   CONSTANTES DE DOMÍNIO
   ============================================================================ */
const USD_BRL = 5.42;
const VM_USD_MES = 1500; // 1x H100 24/7 (PLANILHA_CUSTOS §7 self-host)
const UNIDADES = [
  "Aracaju · Centro",
  "Aracaju · Norte",
  "Nossa Senhora do Socorro",
  "Itabaiana",
  "Lagarto",
  "Estância",
  "Propriá",
  "Tobias Barreto",
];
const EXAMINADORES = [
  "Carla Menezes",
  "Diego Ramos",
  "Patrícia Lima",
  "Anderson Teles",
  "Júlia Farias",
  "Marcos Vieira",
  "Renata Souza",
  "Paulo Andrade",
  "Beatriz Cunha",
  "Rafael Mota",
];
const CANDIDATOS = [
  "João",
  "Maria",
  "Pedro",
  "Ana",
  "Lucas",
  "Beatriz",
  "Gabriel",
  "Larissa",
  "Mateus",
  "Sofia",
  "Rafael",
  "Helena",
  "Bruno",
  "Camila",
  "Felipe",
  "Letícia",
  "Thiago",
  "Mariana",
  "Gustavo",
  "Isabela",
];
const SOBRENOMES = [
  "Silva",
  "Santos",
  "Oliveira",
  "Souza",
  "Lima",
  "Pereira",
  "Costa",
  "Almeida",
  "Nascimento",
  "Araújo",
  "Ribeiro",
  "Carvalho",
  "Gomes",
  "Martins",
  "Rocha",
];
const CATEGORIAS = ["A", "B", "AB", "C", "D", "E"];
const ENGINES: Engine[] = [
  { model: "gemini-2.5-pro", preset: "v25", tin: 77000, tout: 2000 },
  { model: "gemini-3.1-pro-preview", preset: "v25", tin: 77000, tout: 2000 },
  { model: "qwen2.5-vl-7b", preset: "local", tin: 77000, tout: 2000 },
];

// Catálogo de modelos VLM (PLANILHA_CUSTOS.csv §1_Modelo) — custo por vídeo (USD)
const MODELOS_CUSTO: ModeloCusto[] = [
  { nome: "Gemini 2.5 Pro", provider: "Google", tin: 77000, tout: 2000, in_M: 1.25, out_M: 10.0, video_usd: 0.12, tempo_s: 45, atual: true },
  { nome: "Gemini 3.1 Pro Preview", provider: "Google", tin: 77000, tout: 2000, in_M: 2.0, out_M: 12.0, video_usd: 0.18, tempo_s: 75 },
  { nome: "GPT-5.5 (low-res)", provider: "OpenAI", tin: 25000, tout: 2000, in_M: 5.0, out_M: 30.0, video_usd: 0.19, tempo_s: 105 },
  { nome: "Claude Opus 4.7 (low-res)", provider: "Anthropic", tin: 25000, tout: 2000, in_M: 5.0, out_M: 25.0, video_usd: 0.18, tempo_s: 95 },
  { nome: "Qwen3-VL-235B-A22B", provider: "Alibaba", tin: 77000, tout: 2000, in_M: 0.2, out_M: 0.88, video_usd: 0.017, tempo_s: 45 },
  { nome: "Nemotron-12B-VL", provider: "NVIDIA", tin: 77000, tout: 2000, in_M: 0.2, out_M: 0.6, video_usd: 0.017, tempo_s: 35 },
  { nome: "Kimi K2.6", provider: "Moonshot", tin: 77000, tout: 2000, in_M: 0.74, out_M: 3.49, video_usd: 0.064, tempo_s: 55 },
  { nome: "Ernie 4.5 VL 424B", provider: "Baidu", tin: 77000, tout: 2000, in_M: 0.42, out_M: 1.25, video_usd: 0.035, tempo_s: 50 },
  { nome: "DeepSeek V3.2 (texto)", provider: "DeepSeek", tin: 5000, tout: 2000, in_M: 0.25, out_M: 0.38, video_usd: 0.002, tempo_s: 8 },
];

// Matriz de regras (exam_rules — taxonomia 1.020/2025). Subconjunto representativo do MBEDV.
const META_GRAV: Record<Gravidade, GravMeta> = {
  gravissima: { label: "Gravíssima", pontos: 6, color: "#BE123C", bg: "#FCEAEF", ring: "#F3C2CF" },
  grave: { label: "Grave", pontos: 4, color: "#B45309", bg: "#FBF1E3", ring: "#F0D9B3" },
  media: { label: "Média", pontos: 2, color: "#1D4ED8", bg: "#E7EEFD", ring: "#C5D6F8" },
  leve: { label: "Leve", pontos: 1, color: "#6B7689", bg: "#F1F4F9", ring: "#E5E9F0" },
};

const RULES: Rule[] = [
  { codigo: "Art. 161", grav: "leve", nome: "Desobedecer sinalização — geral", ctb: "CTB Art. 161", pontos: 0 },
  { codigo: "Art. 169", grav: "leve", nome: "Dirigir sem atenção ou cuidados de segurança", ctb: "CTB Art. 169", pontos: 0 },
  { codigo: "Art. 178", grav: "media", nome: "Parar o veículo fora da faixa", ctb: "CTB Art. 178", pontos: 0 },
  { codigo: "Art. 181", grav: "media", nome: "Estacionar em local/forma proibida", ctb: "CTB Art. 181", pontos: 0 },
  { codigo: "Art. 182", grav: "media", nome: "Parar em local proibido", ctb: "CTB Art. 182", pontos: 0 },
  { codigo: "Art. 186", grav: "grave", nome: "Transitar pela contramão", ctb: "CTB Art. 186", pontos: 0 },
  { codigo: "Art. 192", grav: "grave", nome: "Deixar de guardar distância de segurança", ctb: "CTB Art. 192", pontos: 0 },
  { codigo: "Art. 195", grav: "grave", nome: "Desobedecer ordem do agente/examinador", ctb: "CTB Art. 195", pontos: 0 },
  { codigo: "Art. 199", grav: "grave", nome: "Ultrapassar pela direita", ctb: "CTB Art. 199", pontos: 0 },
  { codigo: "Art. 170", grav: "gravissima", nome: "Dirigir ameaçando pedestres ou veículos", ctb: "CTB Art. 170", pontos: 0 },
  { codigo: "Art. 175", grav: "gravissima", nome: "Manobra perigosa / arrancada brusca", ctb: "CTB Art. 175", pontos: 0 },
  { codigo: "Art. 193", grav: "gravissima", nome: "Transitar em calçadas e passeios", ctb: "CTB Art. 193", pontos: 0 },
  { codigo: "Art. 208", grav: "gravissima", nome: "Avançar sinal vermelho / parada obrigatória", ctb: "CTB Art. 208", pontos: 0 },
  { codigo: "Art. 218", grav: "gravissima", nome: "Exceder a velocidade máxima da via", ctb: "CTB Art. 218", pontos: 0 },
];
RULES.forEach((r) => {
  r.pontos = META_GRAV[r.grav].pontos;
});

/* ---- helpers de data ---- */
const NOW = new Date(2026, 5, 14, 23, 15, 0); // 14 jun 2026 (alinhado à ref de produção)
const dayMs = 86400000;
function dt(daysAgo: number, h?: number, m?: number): Date {
  const d = new Date(NOW.getTime() - daysAgo * dayMs);
  if (h != null) d.setHours(h, m || 0, 0, 0);
  return d;
}
function renach(i: number): string {
  const n = (31000000 + i * 91357 + ri(0, 900)) % 100000000;
  return "SE0" + String(n).padStart(8, "0");
}
function os_numero(i: number): string {
  return "OS-2026-" + String(1000 + i).padStart(6, "0");
}

/* ---- geração de exames (espelha colunas de v_exams_overview) ---- */
const N_DETALHE = 140; // linhas detalhadas (tabelas)
const exams: Exame[] = [];
for (let i = 0; i < N_DETALHE; i++) {
  const eng = chance(0.82) ? ENGINES[0] : pick(ENGINES);
  const cat = pick(CATEGORIAS);
  const unidade = pick(UNIDADES);
  const examinador = pick(EXAMINADORES);
  const dur = ri(78, 320);
  // resultado computed (004): PENDENTE/PROCESSANDO/FALHOU/SEM_AVALIACAO/APROVADO/INAPTO
  const r = rng();
  let status: ExamStatus,
    resultado: Resultado,
    aprovado: boolean | null = null,
    gate_rejected = false,
    gate_motivo: string | null = null;
  if (r < 0.04) {
    status = "running";
    resultado = "PROCESSANDO";
  } else if (r < 0.06) {
    status = "queued";
    resultado = "PENDENTE";
  } else if (r < 0.08) {
    status = "failed";
    resultado = "FALHOU";
  } else if (r < 0.13) {
    status = "done";
    resultado = "SEM_AVALIACAO";
    gate_rejected = true;
    gate_motivo = pick(["nao_cat_b", "layout_incompleto", "fab_desconhecido"]);
  } else if (r < 0.74) {
    status = "done";
    resultado = "APROVADO";
    aprovado = true;
  } else {
    status = "done";
    resultado = "INAPTO";
    aprovado = false;
  }

  const terminal = ["APROVADO", "INAPTO", "SEM_AVALIACAO", "FALHOU"].includes(resultado);
  const tin = eng.tin + ri(-4000, 6000),
    tout = eng.tout + ri(-300, 600);
  const cost =
    terminal && resultado !== "FALHOU"
      ? +((tin / 1e6) * MODELOS_CUSTO[0].in_M + (tout / 1e6) * MODELOS_CUSTO[0].out_M).toFixed(4)
      : resultado === "FALHOU"
        ? +((tin / 1e6) * 0.4).toFixed(4)
        : null;

  // pontuação calculada (modelo 1·2·4·6, reprova > 10)
  let pontuacao = 0;
  const infr: Infracao[] = [];
  if (resultado === "APROVADO" || resultado === "INAPTO") {
    const nInf = resultado === "INAPTO" ? ri(2, 5) : chance(0.55) ? 0 : ri(1, 2);
    for (let k = 0; k < nInf; k++) {
      const rule =
        resultado === "INAPTO" && k < 2
          ? pick(RULES.filter((x) => x.grav === "gravissima" || x.grav === "grave"))
          : pick(RULES);
      infr.push({
        regra_id: rule.codigo,
        gravidade: rule.grav,
        pontos: rule.pontos,
        descricao: rule.nome,
        timestamp_s: ri(8, dur - 5),
        duracao_s: ri(2, 9),
        confianca: +(0.62 + rng() * 0.37).toFixed(2),
        cameras: pick([["frontal"], ["interna"], ["frontal", "lateral_dir"], ["traseira_esq"]]),
        base_legal: rule.ctb,
        status: "detectada",
      });
      pontuacao += rule.pontos;
    }
    if (resultado === "INAPTO" && pontuacao <= 10) {
      const g = pick(RULES.filter((x) => x.grav === "gravissima"));
      infr.push({
        regra_id: g.codigo,
        gravidade: g.grav,
        pontos: g.pontos,
        descricao: g.nome,
        timestamp_s: ri(8, dur - 5),
        duracao_s: ri(2, 9),
        confianca: 0.9,
        cameras: ["frontal"],
        base_legal: g.ctb,
        status: "detectada",
      });
      pontuacao += g.pontos;
    }
  }
  const houve_interrupcao = resultado === "INAPTO" && chance(0.06);

  // resultado oficial (presencial) — diverge do calculado em ~6%
  let oficial: string | null =
    resultado === "APROVADO"
      ? "A"
      : resultado === "INAPTO"
        ? "R"
        : resultado === "SEM_AVALIACAO"
          ? "N"
          : null;
  const calc: string | null =
    resultado === "APROVADO" ? "A" : resultado === "INAPTO" ? "R" : null;
  let diverge = false,
    tipo_div: TipoDivergencia | null = null;
  if (terminal && calc && chance(0.065)) {
    diverge = true;
    // tipo de divergência
    if (chance(0.4)) {
      oficial = oficial === "A" ? "R" : "A";
      tipo_div = "1_resultado";
    } else if (chance(0.5)) {
      tipo_div = "2_pontuacao";
    } else {
      tipo_div = chance(0.5) ? "3_infracao" : "4_enquadramento";
    }
  } else if (terminal && calc && chance(0.02)) {
    diverge = true;
    tipo_div = "5_evidencia_insuficiente";
  }

  const minsAgo = i * 11 + ri(0, 9);
  const created = new Date(NOW.getTime() - minsAgo * 60000);
  const cnome = pick(CANDIDATOS) + " " + pick(SOBRENOMES);
  exams.push({
    id: "ex_" + i,
    hash: (0x1000000 + i * 7919).toString(16).padStart(8, "0"),
    external_id: "VB-" + String(48210 + i),
    candidato_nome: cnome,
    candidato_cpf: "***." + ri(100, 999) + "." + ri(100, 999) + "-**",
    renach: renach(i),
    examinador,
    unidade,
    local_unidade: unidade,
    auto_escola: pick(["CFC Avenida", "CFC Sergipe", "CFC Modelo", "CFC Pinheiro", "—"]),
    categoria: cat,
    veiculo: pick(["VW Gol", "Fiat Mobi", "Hyundai HB20", "Honda CG 160", "Renault Kwid"]),
    status,
    resultado,
    aprovado,
    pontuacao_total: pontuacao,
    gate_rejected,
    gate_motivo,
    houve_interrupcao,
    size_mb: +(dur * 1.6 + ri(0, 40)).toFixed(1),
    duration_s: dur,
    num_infracoes: infr.length,
    cost_usd: cost,
    cost_tokens_in: terminal ? tin : null,
    cost_tokens_out: terminal ? tout : null,
    gemini_elapsed_s:
      terminal && resultado !== "FALHOU"
        ? +(eng === ENGINES[0] ? 45 + rng() * 22 : 60 + rng() * 30).toFixed(1)
        : null,
    engine_model: eng.model,
    engine_preset: eng.preset,
    infracoes: infr,
    resultado_oficial: oficial,
    resultado_calculado: calc,
    diverge,
    tipo_divergencia: tipo_div,
    created_at: created,
  });
}

/* ---- Ordens de Serviço (uma por exame divergente) ---- */
const STATUS_OS: StatusOS[] = [
  "aguardando_auditor",
  "em_analise_auditor",
  "aguardando_supervisor",
  "encerrada",
];
const TIPO_DIV_LABEL: Record<TipoDivergencia, string> = {
  "1_resultado": "Resultado",
  "2_pontuacao": "Pontuação",
  "3_infracao": "Infração",
  "4_enquadramento": "Enquadramento",
  "5_evidencia_insuficiente": "Evidência insuficiente",
};
const ordens: Ordem[] = [];
let osi = 0;
exams
  .filter((e) => e.diverge)
  .forEach((e) => {
    const prio =
      e.tipo_divergencia === "1_resultado" ? 1 : e.tipo_divergencia === "2_pontuacao" ? 2 : 3;
    const st = pick(STATUS_OS);
    const aberta = e.created_at;
    const slaH = (NOW.getTime() - aberta.getTime()) / 3600000;
    ordens.push({
      os_id: "os_" + osi,
      numero_os: os_numero(osi),
      exam_id: e.id,
      exam_hash: e.hash,
      candidato_nome: e.candidato_nome,
      renach: e.renach,
      categoria: e.categoria,
      unidade: e.unidade,
      examinador: e.examinador,
      tipo_divergencia: e.tipo_divergencia,
      tipo_label: e.tipo_divergencia ? TIPO_DIV_LABEL[e.tipo_divergencia] : "",
      status: st,
      prioridade: prio,
      resultado_oficial: e.resultado_oficial,
      resultado_calculado: e.resultado_calculado,
      pontuacao_oficial:
        e.tipo_divergencia === "2_pontuacao"
          ? Math.max(0, e.pontuacao_total + pick([-4, -2, 2, 4]))
          : e.pontuacao_total,
      pontuacao_calculada: e.pontuacao_total,
      auditor_email:
        st !== "aguardando_auditor"
          ? pick(EXAMINADORES).split(" ")[0].toLowerCase() + "@valmatech.com.br"
          : null,
      supervisor_email: st === "encerrada" ? "rodrigo@valmatech.com.br" : null,
      aberta_em: aberta,
      sla_horas: +slaH.toFixed(1),
      sla_due_at: new Date(aberta.getTime() + 48 * 3600000),
      sla_estourado: slaH > 48,
      conf: e.infracoes.length ? e.infracoes[0].confianca : 0.8,
    });
    osi++;
  });

/* ---- telemetria / log de acessos por vídeo (020 auditor_telemetria) ----
   Cada acesso é uma sessão de visualização de UM exame: quem entrou, quando,
   por quanto tempo e quanto do vídeo assistiu (usage metadata por vídeo). */
interface Revisor {
  nome: string;
  papel: string;
}
const REVISORES: Revisor[] = [
  { nome: "Carla Menezes", papel: "auditor" },
  { nome: "Diego Ramos", papel: "auditor" },
  { nome: "Patrícia Lima", papel: "auditor" },
  { nome: "Anderson Teles", papel: "auditor" },
  { nome: "Júlia Farias", papel: "supervisor" },
  { nome: "Renata Moura", papel: "supervisor" },
  { nome: "Marcos Vieira", papel: "auditor" },
  { nome: "Rodrigo Valença", papel: "admin" },
];
const DISPOSITIVOS = [
  "Chrome · Windows",
  "Chrome · macOS",
  "Edge · Windows",
  "Safari · macOS",
  "Firefox · Linux",
];
const telemetria: TelemetriaAgg[] = [];
const acessosByExam: Record<string, Acesso[]> = {};
// exames terminais (revisáveis) recebem 0–N acessos
exams
  .filter((e) => ["APROVADO", "INAPTO", "SEM_AVALIACAO"].includes(e.resultado))
  .forEach((e) => {
    // divergentes/abertos tendem a ter mais acessos (revisão + arbitragem)
    const base = e.diverge ? ri(2, 5) : chance(0.55) ? ri(1, 2) : 0;
    const list: Acesso[] = [];
    for (let k = 0; k < base; k++) {
      const rev =
        e.diverge && k >= base - 1 && chance(0.6)
          ? (REVISORES.find((r) => r.papel === "supervisor") as Revisor)
          : pick(REVISORES);
      const dur = e.duration_s;
      const pct = Math.min(1, 0.45 + rng() * 0.55);
      const assistido = Math.round(dur * pct);
      const tempoSessao = Math.round(assistido * (1.15 + rng() * 0.9)); // pausas/replays
      const entrou = dt(ri(0, 21), ri(8, 19), ri(0, 59));
      const ac: Acesso = {
        exam_id: e.id,
        exam_hash: e.hash,
        usuario: rev.nome,
        auditor: rev.nome,
        papel: rev.papel,
        entrou_em: entrou,
        created_at: entrou,
        saiu_em: new Date(entrou.getTime() + tempoSessao * 1000),
        tempo_sessao_s: tempoSessao,
        assistido_ate_seg: assistido,
        dur_seg: dur,
        assistido_pct: pct,
        avancos_bloqueados: chance(0.28) ? ri(1, 4) : 0,
        dispositivo: pick(DISPOSITIVOS),
        ip: `10.${ri(0, 9)}.${ri(0, 255)}.${ri(2, 254)}`,
        acao: e.diverge ? pick(["revisão", "parecer", "arbitragem"]) : "revisão",
      };
      list.push(ac);
      // espelho no array agregado usado por Supervisor/Medição
      telemetria.push({
        auditor: rev.nome,
        exam_hash: e.hash,
        assistido_ate_seg: assistido,
        dur_seg: dur,
        tempo_sessao_s: tempoSessao,
        avancos_bloqueados: ac.avancos_bloqueados,
        created_at: entrou,
      });
    }
    list.sort((a, b) => a.entrou_em.getTime() - b.entrou_em.getTime());
    e.num_acessos = list.length;
    e.ultimo_acesso = list.length ? list[list.length - 1].entrou_em : null;
    acessosByExam[e.id] = list;
  });

/* ---- cron jobs (021) ---- */
const cron_jobs: CronJob[] = [
  { id: "cj_1", nome: "Lote noturno — pendentes", enabled: true, schedule_kind: "daily", horario: "02:00", cron_expr: null, batch_limit: 200, retry: 2, escopo: "pending" },
  { id: "cj_2", nome: "Reprocessar falhas", enabled: true, schedule_kind: "hourly", horario: null, cron_expr: null, batch_limit: 50, retry: 3, escopo: "failed" },
  { id: "cj_3", nome: "Fila contínua (15 min)", enabled: true, schedule_kind: "interval", horario: "*/15", cron_expr: null, batch_limit: 30, retry: 1, escopo: "queued" },
  { id: "cj_4", nome: "Varredura semanal completa", enabled: false, schedule_kind: "cron", horario: null, cron_expr: "0 3 * * 0", batch_limit: 1000, retry: 1, escopo: "all" },
];
const cron_runs: CronRun[] = [];
cron_jobs.forEach((cj, ci) => {
  const n = ri(6, 14);
  for (let k = 0; k < n; k++) {
    const ini = dt(ri(0, 20), ri(0, 23), ri(0, 59));
    const proc = ri(8, cj.batch_limit);
    const fail = chance(0.3) ? ri(0, 4) : 0;
    const stt: CronRun["status"] =
      k === 0 && ci === 2 ? "running" : fail > 3 ? "failed" : "success";
    cron_runs.push({
      id: "run_" + ci + "_" + k,
      cron_job_id: cj.id,
      nome: cj.nome,
      iniciado_em: ini,
      finalizado_em: stt === "running" ? null : new Date(ini.getTime() + ri(40, 600) * 1000),
      n_processados: proc,
      n_falhas: fail,
      custo_usd: +(proc * 0.12).toFixed(2),
      status: stt,
    });
  }
});
cron_runs.sort((a, b) => b.iniciado_em.getTime() - a.iniciado_em.getTime());

/* ---- usuários (018 admin_users) ---- */
const usuarios: Usuario[] = [
  { id: "u1", email: "rodrigo@valmatech.com.br", nome: "Rodrigo Valença", role: "admin", created_at: dt(180), last_login_at: dt(0, 22, 40), revoked_at: null },
  { id: "u2", email: "renata.moura@valmatech.com.br", nome: "Renata Moura", role: "supervisor", created_at: dt(150), last_login_at: dt(0, 21, 12), revoked_at: null },
  { id: "u3", email: "carla.menezes@valmatech.com.br", nome: "Carla Menezes", role: "auditor", created_at: dt(120), last_login_at: dt(0, 18, 5), revoked_at: null },
  { id: "u4", email: "diego.ramos@valmatech.com.br", nome: "Diego Ramos", role: "auditor", created_at: dt(110), last_login_at: dt(1, 17, 30), revoked_at: null },
  { id: "u5", email: "patricia.lima@valmatech.com.br", nome: "Patrícia Lima", role: "auditor", created_at: dt(95), last_login_at: dt(0, 16, 48), revoked_at: null },
  { id: "u6", email: "anderson.teles@valmatech.com.br", nome: "Anderson Teles", role: "auditor", created_at: dt(80), last_login_at: dt(2, 14, 0), revoked_at: null },
  { id: "u7", email: "julia.farias@valmatech.com.br", nome: "Júlia Farias", role: "supervisor", created_at: dt(70), last_login_at: dt(0, 19, 20), revoked_at: null },
  { id: "u8", email: "marcos.vieira@valmatech.com.br", nome: "Marcos Vieira", role: "auditor", created_at: dt(60), last_login_at: dt(5, 11, 0), revoked_at: null },
  { id: "u9", email: "ex.estagio@valmatech.com.br", nome: "Bruno Estágio", role: "auditor", created_at: dt(40), last_login_at: dt(20, 9, 0), revoked_at: dt(8) },
];

/* ============================================================================
   MÉTRICAS — espelham backend/dashboard/metrics.py (parametrizadas por dias)
   ============================================================================ */
const TOTAL_MES = 1580; // volume mensal real (ref produção)
function scaleFactor(dias: number): number {
  return Math.max(dias, 1) / 30;
}

function operacionais(dias: number): OperacionaisMetrics {
  const f = scaleFactor(dias);
  const recebidos = Math.round(TOTAL_MES * f);
  const processados = Math.round(recebidos * 0.962);
  const det = exams;
  const por_status: Record<string, number> = {};
  det.forEach((e) => {
    por_status[e.resultado] = (por_status[e.resultado] || 0) + 1;
  });
  // escala a distribuição detalhada para o volume
  const k = recebidos / det.length;
  Object.keys(por_status).forEach((s) => (por_status[s] = Math.round(por_status[s] * k)));
  const os_pend: Record<string, number> = {};
  ordens
    .filter((o) => o.status !== "encerrada")
    .forEach((o) => (os_pend[o.status] = (os_pend[o.status] || 0) + 1));
  return {
    periodo_dias: dias,
    total_recebidos: recebidos,
    total_processados: processados,
    por_status,
    taxa_erro: 0.018,
    tempo_medio_analise_s: 52.4,
    custo_total_usd: +(processados * 0.121).toFixed(2),
    os_pendentes_por_status: os_pend,
  };
}

function regulatorios(dias: number): RegulatoriosMetrics {
  const dist: Record<string, number> = {};
  ordens.forEach(
    (o) => (dist[o.tipo_divergencia as string] = (dist[o.tipo_divergencia as string] || 0) + 1)
  );
  const top: Record<string, number> = {};
  exams.forEach((e) => e.infracoes.forEach((i) => (top[i.regra_id] = (top[i.regra_id] || 0) + 1)));
  const topSorted = Object.fromEntries(
    Object.entries(top)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
  );
  const porUnidade: Record<string, number> = {},
    porExam: Record<string, number> = {},
    porCat: Record<string, number> = {};
  ordens.forEach((o) => {
    porUnidade[o.unidade] = (porUnidade[o.unidade] || 0) + 1;
    porExam[o.examinador] = (porExam[o.examinador] || 0) + 1;
    porCat[o.categoria] = (porCat[o.categoria] || 0) + 1;
  });
  return {
    periodo_dias: dias,
    concordancia_resultado_pct: 96.4,
    concordancia_pontuacao_pct: 92.1,
    distribuicao_divergencias: dist,
    top_infracoes: topSorted,
    divergencia_por_unidade: porUnidade,
    divergencia_por_examinador: porExam,
    divergencia_por_categoria: porCat,
    taxa_interrupcao_pct: 3.2,
    taxa_evidencia_insuficiente_pct: 2.1,
    comentarios_inadequados_examinador: 14,
  };
}

function custos(dias: number): CustosMetrics {
  const f = scaleFactor(dias);
  const num = Math.round(TOTAL_MES * 0.93 * f);
  const tin = num * 78000,
    tout = num * 2050;
  const total = +(num * 0.121).toFixed(2);
  // série diária
  const serie: CustoSerieDia[] = [];
  const ndays = Math.min(dias, 30);
  for (let d = ndays - 1; d >= 0; d--) {
    const ne = Math.round((TOTAL_MES / 30) * (0.8 + rng() * 0.5));
    serie.push({ dia: dt(d).toISOString().slice(0, 10), num_exames: ne, custo_usd: +(ne * 0.121).toFixed(2) });
  }
  const porU: CustoRotuloItem[] = UNIDADES.map((u) => {
    const ne = Math.round((num / UNIDADES.length) * (0.5 + rng()));
    return { rotulo: u, num_exames: ne, custo_usd: +(ne * 0.121).toFixed(2) };
  }).sort((a, b) => b.custo_usd - a.custo_usd);
  const porC: CustoRotuloItem[] = CATEGORIAS.map((c) => {
    const ne = Math.round((num / CATEGORIAS.length) * (0.4 + rng() * 1.2));
    return { rotulo: c, num_exames: ne, custo_usd: +(ne * 0.121).toFixed(2) };
  });
  return {
    periodo_dias: dias,
    custo_total_usd: total,
    num_exames_cobrados: num,
    custo_medio_por_exame_usd: +(total / num).toFixed(4),
    tokens_in_total: tin,
    tokens_out_total: tout,
    serie_diaria: serie,
    por_unidade: porU,
    por_categoria: porC,
  };
}

function supervisor(dias: number): SupervisorMetrics {
  const enc = ordens.filter((o) => o.status === "encerrada");
  const total = enc.length + 38;
  const homolog = Math.round(total * 0.83),
    reform = total - homolog;
  return {
    periodo_dias: dias,
    total_decisoes: total,
    homologadas: homolog,
    reformadas: reform,
    concordancia_supervisor_auditor_pct: +((100 * homolog) / total).toFixed(1),
    concordancia_supervisor_ia_pct: 79.4,
  };
}

function compliance(): ComplianceMetrics {
  return { pendente: 9, examinador_inadequado: 5, conduta_candidato: 2, conduta_sem_ficha: 2 };
}

function resumo(dias?: number): ResumoMetrics {
  dias = dias || 30;
  return {
    periodo_dias: dias,
    operacionais: operacionais(dias),
    regulatorios: regulatorios(dias),
    custos: custos(dias),
    supervisor: supervisor(dias),
    compliance: compliance(),
  };
}

/* ============================================================================
   EXPORT — objeto VB (espelha window.VB do protótipo)
   ============================================================================ */
export const VB = {
  NOW,
  USD_BRL,
  VM_USD_MES,
  TOTAL_MES,
  UNIDADES,
  EXAMINADORES,
  CATEGORIAS,
  META_GRAV,
  RULES,
  MODELOS_CUSTO,
  TIPO_DIV_LABEL,
  exams,
  ordens,
  telemetria,
  cron_jobs,
  cron_runs,
  usuarios,
  acessos: acessosByExam,
  acessosDe: (examId: string): Acesso[] => acessosByExam[examId] || [],
  acessosDoExame: (hash: string): Acesso[] => {
    const e = exams.find((x) => x.hash === hash);
    return e ? acessosByExam[e.id] || [] : [];
  },
  metrics: { operacionais, regulatorios, custos, supervisor, compliance, resumo },
  fmt,
};

export default VB;
