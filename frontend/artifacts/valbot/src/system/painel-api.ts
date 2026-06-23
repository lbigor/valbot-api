/* ============================================================================
   ValBot — Painel do Auditor · CAMADA DE DADOS REAL (substitui o mock da fila).
   Consome a API de produção e ADAPTA pro shape que os componentes painel-* já
   usam (ExamItem / MarkRef / Rule de painel-data.ts). Mantém gravColor/fmtDur/meta
   e o catálogo de regras (rules/ruleByCode) como CONFIG; só a `queue` (lista de
   exames) e o detalhe (vídeo + infrações da IA) passam a vir do backend.

   Endpoints:
     GET  /api/videos?only_unresolved=true            -> fila de exames divergentes
     GET  /api/analyses/hash/{hash}/result            -> laudo (infrações da IA)
     GET  /api/exams/{hash}/video                      -> stream do vídeo
     GET  /api/rubricas/1020-2025                       -> catálogo de regras (picker)
     POST /api/exams/{hash}/parecer-auditor            -> salvar parecer
   ============================================================================ */
import { VB, meta, type Grav, type Rule, type MarkRef, type ExamItem, type Aval, type TpAnnotation } from "./painel-data";
import type { VideoItem, LaudoResponse, Infracao, RubricaFull, RubricaInfracao, Gravidade } from "../types/laudo";
import type { ClipMarks } from "@/pages-v2/fila/PainelModel";

/* ---------- gravidade real -> Grav do painel ---------- */
function normGrav(g: Gravidade | string): Grav {
  if (g === "eliminatoria" || g === "gravissima") return "gravissima";
  if (g === "grave") return "grave";
  if (g === "etica" || g === "media") return "media";
  return "leve";
}

/* ---------- catálogo de regras (config) — hidrata VB.ruleByCode/VB.rules ---------- */
// Os componentes leem VB.ruleByCode[code] SEM fallback. Garantimos que todo código
// referenciado (rubrica + infrações reais) exista no registro antes do render, e
// deixamos uma regra-fallback defensiva pra qualquer código órfão (nunca quebra).
function registerRule(r: Rule): void {
  VB.ruleByCode[r.code] = r;
  if (!VB.rules.some((x) => x.code === r.code)) VB.rules.push(r);
}
function ensureRule(code: string, grav: Grav): Rule {
  if (VB.ruleByCode[code]) return VB.ruleByCode[code];
  const r: Rule = {
    code, nome: code, grav, pontos: meta.grav[grav].pontos,
    desc: "Infração detectada pela análise da IA.", checks: "",
    enquad: { art: "", ctb: code, mbedv: "" },
  };
  registerRule(r);
  return r;
}
function ruleFromRubrica(r: RubricaInfracao): Rule {
  const grav = normGrav(r.gravidade);
  return {
    code: r.id, nome: r.descricao || r.id, grav, pontos: r.pontos || meta.grav[grav].pontos,
    desc: r.descricao || "", checks: r.vlm_prompt_hint || "",
    enquad: { art: "", ctb: r.base_legal || r.id, mbedv: r.base_legal || "" },
  };
}
function ruleFromInfra(i: Infracao): Rule {
  const grav = normGrav(i.gravidade);
  return {
    code: i.id, nome: i.titulo || i.id, grav, pontos: i.pontos || meta.grav[grav].pontos,
    desc: i.descricao_longa || i.descricao || "", checks: i.evidencia || "",
    enquad: { art: "", ctb: i.base_legal || i.id, mbedv: i.base_legal || "" },
  };
}

/* ---------- pontuação / veredito (mesma regra do mock evalFrom) ---------- */
function ptsOf(codes: string[]): number {
  return codes.reduce((s, c) => {
    const r = VB.ruleByCode[c];
    const g = r ? r.grav : "leve";
    return s + ((r && r.pontos != null ? r.pontos : meta.grav[g].pontos) || 0);
  }, 0);
}
function verdictFrom(codes: string[]): "aprovado" | "reprovado" {
  const grav = codes.some((c) => (VB.ruleByCode[c]?.grav) === "gravissima");
  return grav || ptsOf(codes) > 4 ? "reprovado" : "aprovado";
}

/* ---------- HTTP ---------- */
async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: "include", headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error("HTTP " + r.status + " em " + url);
  return r.json() as Promise<T>;
}
async function jpost<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST", credentials: "include",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("HTTP " + r.status + " em " + url);
  return r.json() as Promise<T>;
}
async function withRetry<T>(fn: () => Promise<T>, tries = 3, baseDelay = 350): Promise<T> {
  let lastErr: unknown;
  for (let i = 0; i < tries; i++) {
    try { return await fn(); }
    catch (e) { lastErr = e; if (i < tries - 1) await new Promise((res) => setTimeout(res, baseDelay * (i + 1))); }
  }
  throw lastErr;
}
function parseMMSS(s: string | undefined | null): number {
  if (!s) return 0;
  const p = String(s).split(":").map(Number);
  if (p.length === 3) return p[0] * 3600 + p[1] * 60 + p[2];
  if (p.length === 2) return p[0] * 60 + p[1];
  return Number(s) || 0;
}

function fmtMMSS(s: number): string {
  const sec = Math.max(0, Math.round(s)); const m = Math.floor(sec / 60), r = sec % 60;
  return m + ":" + String(r).padStart(2, "0");
}

/* ---------- anotações do examinador (training_annotations) ---------- */
// Formato bruto vindo do backend: { timestamp: "HH:MM:SS" | "MM:SS", anotacoes: "texto…" }.
interface TrainingAnnotationRaw { timestamp?: string | null; anotacoes?: string | null }

// Parse TOLERANTE de timestamp -> segundos. Aceita "00:00:34" (hh:mm:ss ou
// mm:ss) e "MM:SS". Se vier absurdo (ex. "82:08:55" => >24h) ou inválido,
// clampa em 0 (o texto ainda é exibido). Nunca lança / nunca NaN.
function parseAnnoTs(s: string | undefined | null): number {
  if (!s) return 0;
  const parts = String(s).trim().split(":").map((x) => Number(x));
  if (parts.some((n) => !Number.isFinite(n) || n < 0)) return 0;
  let secs = 0;
  if (parts.length === 3) secs = parts[0] * 3600 + parts[1] * 60 + parts[2];
  else if (parts.length === 2) secs = parts[0] * 60 + parts[1];
  else if (parts.length === 1) secs = parts[0];
  else return 0;
  if (!Number.isFinite(secs) || secs < 0) return 0;
  // guarda contra valores absurdos (> 24h): provavelmente lixo no dado.
  if (secs > 86400) return 0;
  return Math.round(secs);
}

// Extrai o código "Art. NNN" (+ inciso opcional, ex. "Art. 252, V") do texto da
// anotação. Regex tolerante: aceita "Art." / "Art" / "art" e espaços variados.
// Retorna o código normalizado "Art. NNN" (sem inciso, casa com os codes da Matriz)
// ou null se não casar.
const ART_RE = /\bart\.?\s*(\d{1,4})/i;
function extractArtCode(text: string | undefined | null): string | null {
  if (!text) return null;
  const m = ART_RE.exec(String(text));
  return m ? "Art. " + m[1] : null;
}

// Normaliza training_annotations (top-level OU exame.training_annotations) em
// TpAnnotation[] estruturado (timestamp em segundos + texto + código extraído).
function parseTrainingAnnotations(res: unknown): TpAnnotation[] {
  const r = res as { training_annotations?: unknown; exame?: { training_annotations?: unknown } } | null;
  const raw = (r?.training_annotations ?? r?.exame?.training_annotations) as TrainingAnnotationRaw[] | undefined;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((a) => {
      const text = (a?.anotacoes ?? "").toString().trim();
      if (!text) return null;
      return { t: parseAnnoTs(a?.timestamp), code: extractArtCode(text), text };
    })
    .filter((x): x is TpAnnotation => x != null)
    .sort((a, b) => a.t - b.t);
}

/* ---------- catálogo: carrega a rubrica 1x (picker/fichas) ---------- */
let rubricaLoaded = false;
export async function loadRubrica(): Promise<void> {
  if (rubricaLoaded) return;
  try {
    const rf = await jget<RubricaFull>("/api/rubricas/1020-2025");
    (rf?.infracoes || []).forEach((r) => registerRule(ruleFromRubrica(r)));
  } catch { /* picker fica limitado à matriz local + infrações dos exames */ }
  rubricaLoaded = true;
}

/* ---------- fila: GET /api/videos?only_unresolved=true ---------- */
export async function fetchQueue(): Promise<ExamItem[]> {
  const d = await jget<VideoItem[] | { videos?: VideoItem[]; items?: VideoItem[] }>("/api/videos?only_unresolved=true");
  const arr = Array.isArray(d) ? d : (d.videos || d.items || []);
  return arr.filter((v) => v.has_result && v.status === "processed").map(videoToExamItem);
}

// VideoItem -> ExamItem (shape que os componentes painel-* usam). As infrações
// detalhadas (faults/timestamps) só vêm no detalhe (lazy); aqui montamos o veredito
// IA a partir de `aprovado`/`resultado` + pontuação total.
export function videoToExamItem(v: VideoItem): ExamItem {
  const tpResult: "aprovado" | "reprovado" = v.resultado_exame === "R" ? "reprovado" : "aprovado";
  const vbAprov = v.resultado === "APROVADO" || v.aprovado === true;
  const vbAval = v.resultado != null && v.resultado !== "SEM_AVALIACAO" && v.resultado !== "PENDENTE" && v.resultado !== "PROCESSANDO";
  const posResolved = v.tipo_divergencia_pos_comite === "sem_divergencia";
  const posDivergent = v.tipo_divergencia_pos_comite != null && !posResolved;
  const status: ExamItem["status"] =
    posDivergent ? "divergencia" : posResolved ? "finalizado" : (v.resultado_exame == null ? "divergencia" : "finalizado");
  const tp: Aval = { result: tpResult, faults: [], pts: 0 };
  const vb: Aval | null = vbAval
    ? { result: vbAprov ? "aprovado" : "reprovado", faults: [], pts: v.pontuacao_total || 0, conf: 0.95 }
    : null;
  return {
    id: v.hash, dbId: v.hash,
    renach: (v as { renach?: string }).renach || v.hash.slice(0, 10),
    receb: new Date(v.mtime || Date.now()), aval: new Date(v.mtime || Date.now()),
    tp, vb, status,
    tpComment: "", vbComment: "",
    revisor: status === "finalizado" ? "Renata Moura" : null,
    examinador: "—",
    dur: 0, cat: v.categoria_cnh || "—",
    audio: [], tsFix: {},
  };
}

/* ---------- detalhe: GET /api/analyses/hash/{hash}/result ---------- */
export interface ExamDetail {
  q: ExamItem;              // ExamItem enriquecido (renach/examinador/cat/dur/vb reais)
  marks: ClipMarks;         // trilhas TP (vazia) + ValBot (infrações reais) + divergências
  laudo: MarkRef[];         // laudo inicial (vazio — auditor monta)
  videoUrl: string;         // /api/exams/{hash}/video
  recomendacao: string;     // parecer do ValBot (pontos de atenção / positivos)
}

export async function fetchExamDetail(item: ExamItem): Promise<ExamDetail> {
  const res = await withRetry(() => jget<LaudoResponse>(`/api/analyses/hash/${item.dbId}/result`));
  const infra = res.scored?.infracoes || [];

  // cada infração real -> regra (ficha sempre abre) + marcador na trilha ValBot
  const vb: MarkRef[] = infra.map((i) => {
    if (!VB.ruleByCode[i.id]) registerRule(ruleFromInfra(i));
    const grav = normGrav(i.gravidade);
    const t = parseMMSS(i.timestamp_inicio);
    const len = Math.max(2, i.duracao_seg || (parseMMSS(i.timestamp_fim) - t) || 4);
    return { code: i.id, t, len, grav, conf: 0.95 };
  }).sort((a, b) => a.t - b.t);

  // anotações do examinador presencial (training_annotations top-level ou em exame)
  const tpAnnotations = parseTrainingAnnotations(res);
  // comentário consolidado do examinador (todas as anotações, com timestamp)
  const tpComment = tpAnnotations
    .map((a) => (a.t > 0 ? `[${fmtMMSS(a.t)}] ` : "") + a.text)
    .join("\n");

  // dur PRIMEIRO (precisa do dur p/ posicionar as anotações órfãs em sequência).
  // Base: timestamps válidos das anotações (0 < t) + infrações VB + duracao_seg.
  const validAnnoTs = tpAnnotations.filter((a) => a.t > 0).map((a) => a.t);
  const dur = res.summary?.duracao_seg
    || (vb.length || validAnnoTs.length
      ? Math.max(...[...vb.map((m) => m.t + m.len), ...validAnnoTs]) + 10
      : 60);

  // TODAS as anotações viram marcador na trilha TechPrático (com E sem Art.):
  //  - timestamp dentro do vídeo (0 < t <= dur) -> marcador exatamente em t;
  //  - "órfãs" (t==0 do clamp, ou t > dur — ex. horários de relógio "82:08:55")
  //    -> em SEQUÊNCIA a partir de 00:00 (1ª em 0:00, próximas logo após), ordem original.
  // Marcador com Art. -> kind "infra" (entra no cálculo de faults). Sem Art. -> "nota".
  const ORPHAN_GAP = 5; // segundos entre órfãs em sequência
  let orphanIdx = 0;
  const tpMarks: MarkRef[] = tpAnnotations
    .map((a) => {
      const inWindow = a.t > 0 && a.t <= dur;
      const t = inWindow
        ? a.t
        : Math.min(Math.max(0, dur - 4), (orphanIdx++) * ORPHAN_GAP); // órfãs: 0,5,10… desde 00:00
      if (a.code) {
        const code = a.code;
        const grav = VB.ruleByCode[code] ? VB.ruleByCode[code].grav : ensureRule(code, "leve").grav;
        return { code, t, len: 4, grav, kind: "infra" as const };
      }
      // anotação sem artigo do CTB -> nota/observação (não pontua, estilo neutro)
      return { code: "", t, len: 4, grav: "leve" as Grav, kind: "nota" as const, note: a.text };
    })
    .sort((a, b) => a.t - b.t);
  // só os marcadores de infração (com Art.) contam para faults/pontuação/divergência.
  const tpCodes = Array.from(new Set(tpMarks.filter((m) => m.kind !== "nota" && m.code).map((m) => m.code)));

  const ex = res.exame || ({} as { renach?: string; examinador?: string; categoria?: string });
  const vbCodes = vb.map((m) => m.code);
  const vbComment =
    (res.pontos_atencao && res.pontos_atencao.length ? res.pontos_atencao.join(" · ") : (res.positivos || []).join(" · "))
    || "Análise concluída pela IA (Gemini).";

  const q: ExamItem = {
    ...item,
    renach: ex.renach || item.renach,
    examinador: ex.examinador || item.examinador,
    cat: ex.categoria || item.cat,
    dur,
    tp: { ...item.tp, faults: tpCodes, pts: ptsOf(tpCodes) },
    vb: {
      result: res.summary?.aprovado ? "aprovado" : "reprovado",
      faults: vbCodes,
      pts: res.summary?.pontuacao_total || ptsOf(vbCodes),
      conf: (res.summary?.confianca_media || 95) / 100,
    },
    tpComment,
    vbComment,
    tpAnnotations,
  };

  // Trilha TechPrático agora vem das anotações do examinador (training_annotations).
  // Divergência = infração que só uma das trilhas marcou.
  const tpSet = new Set(tpCodes);
  const vbSet = new Set(vbCodes);
  const onlyVb = vb.filter((m) => !tpSet.has(m.code));
  // divergência só entre infrações (com Art.); notas não contam como divergência.
  const onlyTp = tpMarks.filter((m) => m.kind !== "nota" && m.code && !vbSet.has(m.code));
  const divRegions = [...onlyVb, ...onlyTp].map((m) => ({ from: m.t, to: m.t + m.len }));
  const marks: ClipMarks = {
    tp: tpMarks, vb, onlyTp, onlyVb, divRegions,
    processing: false, audio: [], interrupt: null,
  };

  return { q, marks, laudo: [], videoUrl: `/api/exams/${item.dbId}/video`, recomendacao: vbComment };
}

/* ---------- persistência do parecer ---------- */
export interface ParecerInput {
  decisao: "concorda" | "discorda";
  resultado_final: "aprovado" | "reprovado";
  infracoes: { code: string; t: number; len: number; grav: string }[];
  justificativa: string;
  referencia_mbedv?: string | null;
}
export interface ParecerResult { persisted: boolean; os_id: string | null; source?: string }
export async function postParecerAuditor(hash: string, input: ParecerInput): Promise<ParecerResult> {
  const r = await jpost<{ persisted?: boolean; os_id?: string | null; source?: string }>(
    `/api/exams/${hash}/parecer-auditor`, input,
  );
  return { persisted: r?.persisted !== false, os_id: r?.os_id ?? null, source: r?.source };
}

// fila local de pareceres salvos quando a rede falha (não perde o trabalho).
const LS_PENDING = "vb-painel-pareceres-pendentes";
export function savePendingParecer(hash: string, payload: unknown): void {
  try {
    const cur = JSON.parse(localStorage.getItem(LS_PENDING) || "{}");
    cur[hash] = { ...(payload as object), savedAt: new Date().toISOString() };
    localStorage.setItem(LS_PENDING, JSON.stringify(cur));
  } catch { /* noop */ }
}

export { ensureRule, normGrav, verdictFrom, ptsOf };
