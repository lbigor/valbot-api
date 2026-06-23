/* ============================================================================
   ValBot — Painel do Auditor · dados + helpers (porte fiel de .design-ref/data.jsx)
   Este VB é o dataset PRÓPRIO do Painel (rules/ruleByCode/queue/meta/normas),
   distinto do VB do SaaS (system/vb-data.ts). Os exames referenciam códigos
   "Art. NNN" da Matriz Nacional (MBEDV_RULES). gravColor/fmtDur vivem aqui pois
   são usados por todos os componentes painel-*.
   ============================================================================ */
import { MBEDV_RULES } from "./painel-matriz";

export type Grav = "gravissima" | "grave" | "media" | "leve";

export interface Enquad {
  art: string;
  ctb: string;
  mbedv: string;
}

export interface Rule {
  code: string;
  art?: string;
  grav: Grav;
  pontos: number | null;
  nome: string;
  desc?: string;
  categorias?: string;
  constatacao?: string;
  pontua?: string;
  naoPontua?: string;
  definicoes?: string;
  checks?: string;
  compl?: string;
  enquad: Enquad;
  pts?: string;
}

export interface MarkRef {
  code: string;
  t: number;
  len: number;
  grav: Grav;
  conf?: number;
  shared?: boolean;
  /**
   * Tipo do marcador na trilha:
   *  - "infra" (default): infração enquadrada (tem code "Art. NNN" + ficha em VB.ruleByCode).
   *  - "nota": observação livre do examinador (sem artigo do CTB) — não pontua,
   *    renderiza com estilo neutro e carrega o texto da anotação em `note`.
   */
  kind?: "infra" | "nota";
  /** Texto da anotação (usado quando kind === "nota" — tooltip + realce no comentário). */
  note?: string;
}

/**
 * Anotação do examinador presencial (TechPrático), extraída de
 * `training_annotations` do result.json. `t` = timestamp em segundos (parse
 * tolerante), `code` = "Art. NNN" extraído do texto (null se não houver),
 * `text` = a anotação completa do examinador.
 */
export interface TpAnnotation {
  t: number;
  code: string | null;
  text: string;
}

export interface Aval {
  result: "aprovado" | "reprovado";
  faults: string[];
  pts: number;
  conf?: number;
}

export interface AudioCue {
  t: number;
  len: number;
  label: string;
  enquad: Enquad;
}

export interface Interrupt {
  at: number;
  motivo: string;
  det: string;
}

export interface FinalLaudo {
  result: "aprovado" | "reprovado";
  faults: string[];
  note?: string;
}

export interface ExamItem {
  id: string;
  dbId: string;
  renach: string;
  receb: Date;
  aval: Date;
  tp: Aval;
  vb: Aval | null;
  status: "divergencia" | "finalizado" | "interrompido" | "processando";
  tpComment?: string;
  vbComment?: string;
  /** Anotações do examinador presencial (TechPrático) — vêm de training_annotations. */
  tpAnnotations?: TpAnnotation[];
  revisor: string | null;
  examinador: string;
  dur: number;
  cat: string;
  audio: AudioCue[];
  tsFix: Record<string, number>;
  interrupt?: Interrupt;
  final?: FinalLaudo;
}

/* ---------- fallback de regras (quando não há matriz) ---------- */
const fallbackRules: Rule[] = [
  { code: "ELIM-01", nome: "Avançar o sinal vermelho do semáforo ou o de parada obrigatória", grav: "gravissima", pontos: 6, desc: "Avançar o semáforo vermelho/amarelo ou a faixa de retenção sem efetuar a parada obrigatória diante de placa PARE.", checks: "Detecta a fase do semáforo no quadro e a posição do veículo em relação à faixa de retenção.", enquad: { art: "208", ctb: "CTB Art. 208", mbedv: "MBEDV §6.1 a" } },
  { code: "ELIM-02", nome: "Transitar com o veículo em calçadas, passeios e áreas de pedestres", grav: "gravissima", pontos: 6, desc: "Subir com qualquer roda sobre o meio-fio, guia ou calçada durante o percurso ou manobra de baliza.", checks: "Segmentação da roda e do limite da via; sobreposição com a guia.", enquad: { art: "193", ctb: "CTB Art. 193", mbedv: "MBEDV §6.1 b" } },
];

const allRules: Rule[] = MBEDV_RULES && MBEDV_RULES.length ? MBEDV_RULES : fallbackRules;
const ruleByCode: Record<string, Rule> = Object.fromEntries(allRules.map((r) => [r.code, r]));

/* ---------- Fila ---------- */
function dt(dayOffset: number, h: number, m: number): Date {
  const base = new Date(2026, 5, 5, 9, 0, 0); // 5 jun 2026
  const d = new Date(base.getTime() - dayOffset * 86400000);
  d.setHours(h, m, 0, 0);
  return d;
}
const examinadores = ["Carla M.", "Diego R.", "Patrícia L.", "Anderson T.", "Júlia F.", "Marcos V."];

function evalFrom(faults: string[]): Aval {
  const pts = faults.reduce((s, c) => {
    const g = ruleByCode[c].grav;
    return s + (ruleByCode[c].pontos || (g === "gravissima" ? 6 : g === "grave" ? 4 : g === "media" ? 2 : g === "leve" ? 1 : 0));
  }, 0);
  const hasGravissima = faults.some((c) => ruleByCode[c].grav === "gravissima");
  const result: "aprovado" | "reprovado" = hasGravissima || pts > 4 ? "reprovado" : "aprovado";
  return { result, faults, pts };
}

interface ExamSeed {
  sid: string;
  renach: string;
  cat: string;
  dur: number;
  conf: number;
  status: ExamItem["status"];
  vb: string[];
  tp: string[];
  ts: Record<string, number>;
  vbComment?: string;
  tpComment?: string;
  interrupt?: Interrupt;
}

const EXAMS: ExamSeed[] = [
  { sid: "3d70cc0d", renach: "SE031002056", cat: "B", dur: 253, conf: 0.95, status: "divergencia",
    vb: ["Art. 193", "Art. 208", "Art. 196"], tp: ["Art. 169"],
    ts: { "Art. 193": 57, "Art. 208": 151, "Art. 196": 213, "Art. 169": 40 },
    vbComment: "Visão computacional identificou avanço sobre meio-fio (Art. 193 · 0:57), avanço de parada obrigatória PARE (Art. 208 · 2:31) e conversão sem sinalização (Art. 196 · 3:33). Pontuação configura reprovação.",
    tpComment: "Examinador registrou apenas falta leve de atenção (Art. 169) e lançou o exame como apto." },
  { sid: "82c29e57", renach: "SE031426220", cat: "E", dur: 96, conf: 0.99, status: "finalizado",
    vb: [], tp: [], ts: {},
    vbComment: "Análise concluída sem infrações. Conduta estável e manobras sinalizadas com antecedência. Apto.",
    tpComment: "Candidato apto, sem ressalvas." },
  { sid: "a0d2f74a", renach: "SE031651593", cat: "B", dur: 291, conf: 0.95, status: "finalizado",
    vb: ["Art. 186", "Art. 208", "Art. 252", "Art. 196"], tp: ["Art. 186", "Art. 208", "Art. 252", "Art. 196"],
    ts: { "Art. 186": 43, "Art. 208": 172, "Art. 252": 197, "Art. 196": 213 },
    vbComment: "Contramão (Art. 186 · 0:43), não imobilizou no PARE (Art. 208 · 2:52), conduziu com uma das mãos (Art. 252 · 3:17) e não sinalizou manobra (Art. 196 · 3:33). Inapto.",
    tpComment: "Examinador confirmou as quatro infrações. Inapto." },
  { sid: "c21cde6a", renach: "SE031682235", cat: "B", dur: 233, conf: 1.0, status: "interrompido",
    vb: ["Art. 169"], tp: ["Art. 169"], ts: { "Art. 169": 156 },
    interrupt: { at: 231, motivo: "Imperícia recorrente nos comandos básicos", det: "Candidato arrancava repetidamente em 3ª marcha; examinador interrompeu o exame (cláusula de faltas gravíssimas, MBEDV)." },
    vbComment: "Tentativas repetidas de arranque em 3ª marcha (Art. 169 · 2:36). ValBot pontuou como falta leve.",
    tpComment: "Examinador interrompeu o exame por imperícia recorrente — categoria especial." },
  { sid: "e8686f16", renach: "SE031744478", cat: "A", dur: 88, conf: 0.98, status: "finalizado",
    vb: [], tp: [], ts: {},
    vbComment: "Análise concluída sem infrações. Apto.",
    tpComment: "Candidato apto, sem ressalvas." },
];
const RECT: [number, number, number][] = [[0, 9, 12], [0, 9, 40], [1, 10, 28], [1, 11, 5], [2, 9, 33]];

const queue: ExamItem[] = EXAMS.map((e, i) => {
  const tpF = e.tp.filter((c) => ruleByCode[c]);
  const vbF = e.vb.filter((c) => ruleByCode[c]);
  const tsF: Record<string, number> = {};
  Object.keys(e.ts).forEach((k) => { if (ruleByCode[k]) tsF[k] = e.ts[k]; });
  const tp = evalFrom(tpF);
  const vb: Aval = Object.assign(evalFrom(vbF), { conf: e.conf });
  const item: ExamItem = {
    id: "VB-" + String(4821 + i),
    dbId: e.sid,
    renach: e.renach,
    receb: dt(RECT[i][0], RECT[i][1], RECT[i][2]),
    aval: dt(RECT[i][0], RECT[i][1], RECT[i][2] + 8),
    tp, vb, status: e.status,
    tpComment: e.tpComment, vbComment: e.vbComment,
    revisor: e.status === "finalizado" ? "Renata Moura" : null,
    examinador: examinadores[i],
    dur: e.dur, cat: e.cat,
    audio: [], tsFix: tsF,
  };
  if (e.interrupt) item.interrupt = e.interrupt;
  return item;
});

const counts = {
  processando: queue.filter((q) => q.status === "processando").length,
  divergencia: queue.filter((q) => q.status === "divergencia").length,
  finalizado: queue.filter((q) => q.status === "finalizado").length,
  interrompido: queue.filter((q) => q.status === "interrompido").length,
};

export interface GravMeta {
  label: string;
  color: string;
  bg: string;
  ring: string;
  pontos: number;
}

export const meta = {
  status: {
    processando: { label: "Processando", cls: "badge-proc" },
    divergencia: { label: "Divergência", cls: "badge-bad" },
    finalizado: { label: "Finalizado", cls: "badge-ok" },
  },
  grav: {
    gravissima: { label: "Gravíssima", color: "#BE123C", bg: "#FCEAEF", ring: "#F3C2CF", pontos: 6 },
    grave: { label: "Grave", color: "#B45309", bg: "#FBF1E3", ring: "#F0D9B3", pontos: 4 },
    media: { label: "Média", color: "#1D4ED8", bg: "#E7EEFD", ring: "#C5D6F8", pontos: 2 },
    leve: { label: "Leve", color: "#6B7689", bg: "#F1F4F9", ring: "#E5E9F0", pontos: 1 },
  } as Record<Grav, GravMeta>,
};

const normas = [
  { sigla: "CTB", titulo: "Código de Trânsito Brasileiro", ref: "Lei nº 9.503/1997", conteudo: "Define as infrações de trânsito que servem de base para a pontuação no exame." },
  { sigla: "CONTRAN", titulo: "Resolução CONTRAN nº 1.020/2025", ref: "vigente", conteudo: "Sistemática do exame, pesos por gravidade e limite de aprovação." },
  { sigla: "MBEDV", titulo: "Manual Brasileiro de Exames de Direção Veicular", ref: "Senatran · 01/02/2026", conteudo: "Parâmetros vinculantes nacionais e fichas de avaliação, artigo por artigo." },
  { sigla: "DETRAN", titulo: "Portarias estaduais de adequação", ref: "SP · MG · MS · RS", conteudo: "Normativos estaduais em adequação à Resolução 1.020/2025." },
];

/* ---------- helpers globais do painel ---------- */
export function gravColor(g: Grav | string): string {
  return ({ gravissima: "var(--g-elim)", grave: "var(--g-grave)", media: "var(--g-media)", leve: "var(--g-leve)" } as Record<string, string>)[g];
}
export const fmtDur = (s: number): string => `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2, "0")}`;

/* ---------- VB do Painel (espelha o window.VB de data.jsx) ---------- */
export const VB = { rules: allRules, ruleByCode, queue, counts, meta, normas };
export default VB;
