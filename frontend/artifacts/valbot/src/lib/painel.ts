// src/lib/painel.ts — camada de dados REAL da Fila do Auditor.
// Consome a API de produção: /api/videos, /api/analyses/hash/{hash}/result, /api/rubricas/1020-2025,
// vídeo em /api/exams/{hash}/video. Pontuação fiel (pesos da rubrica/infração); ficha vem da própria
// infração detectada (garante abrir sempre) com fallback na rubrica.
import type { VideoItem, LaudoResponse, Infracao, RubricaFull, RubricaInfracao, Gravidade } from "../types/laudo";

export type Grav = "gravissima" | "grave" | "media" | "leve";

export interface Enquad { art: string; ctb: string; mbedv: string; }
export interface Rule { code: string; nome: string; grav: Grav; pontos: number; desc: string; checks: string; enquad: Enquad; }
export interface Mark { code: string; t: number; len: number; grav: Grav; conf?: number; ator?: string | null; kind?: "infra" | "nota"; note?: string; }
export interface Avaliacao { result: "aprovado" | "reprovado"; faults: string[]; pts: number; conf?: number; }
export type Status = "divergencia" | "processando" | "finalizado" | "interrompido";
export interface TpAnnotation { t: number; code: string | null; text: string; }
export interface QueueItem {
  id: string; hash: string; renach: string; examinador: string; dur: number; cat: string;
  status: Status; resultadoExame: "A" | "R" | "N" | null;
  tp: Avaliacao; vb: Avaliacao | null;
  tpComment: string; vbComment: string;
  tpAnnotations?: TpAnnotation[];
}
export interface ClipMarks { tp: Mark[]; vb: Mark[]; onlyTp: Mark[]; onlyVb: Mark[]; divRegions: { from: number; to: number }[]; processing: boolean; interrupt: null; }

// ---------- gravidade ----------
export function normGrav(g: Gravidade | string): Grav {
  if (g === "eliminatoria" || g === "gravissima") return "gravissima";
  if (g === "grave") return "grave";
  if (g === "etica" || g === "media") return "media";
  return "leve";
}
export function gravColor(g: Grav): string {
  return { gravissima: "var(--g-elim)", grave: "var(--g-grave)", media: "var(--g-media)", leve: "var(--g-leve)" }[g];
}
export const meta = {
  grav: {
    gravissima: { label: "Gravíssima", color: "#BE123C", pontos: 6 },
    grave: { label: "Grave", color: "#B45309", pontos: 4 },
    media: { label: "Média", color: "#1D4ED8", pontos: 2 },
    leve: { label: "Leve", color: "#6B7689", pontos: 1 },
  } as Record<Grav, { label: string; color: string; pontos: number }>,
};
export function fmtDur(s: number): string {
  const sec = Math.max(0, Math.round(s)); const m = Math.floor(sec / 60), r = sec % 60;
  return m + ":" + String(r).padStart(2, "0");
}
function parseMMSS(s: string | undefined | null): number {
  if (!s) return 0;
  const p = String(s).split(":").map(Number);
  if (p.length === 3) return p[0] * 3600 + p[1] * 60 + p[2];
  if (p.length === 2) return p[0] * 60 + p[1];
  return Number(s) || 0;
}

/* ---------- anotações do examinador (training_annotations) ---------- */
interface TrainingAnnotationRaw { timestamp?: string | null; anotacoes?: string | null }
// parse TOLERANTE de timestamp -> segundos (clampa lixo/>24h em 0; nunca NaN).
function parseAnnoTs(s: string | undefined | null): number {
  if (!s) return 0;
  const parts = String(s).trim().split(":").map((x) => Number(x));
  if (parts.some((n) => !Number.isFinite(n) || n < 0)) return 0;
  let secs = 0;
  if (parts.length === 3) secs = parts[0] * 3600 + parts[1] * 60 + parts[2];
  else if (parts.length === 2) secs = parts[0] * 60 + parts[1];
  else if (parts.length === 1) secs = parts[0];
  else return 0;
  if (!Number.isFinite(secs) || secs < 0 || secs > 86400) return 0;
  return Math.round(secs);
}
const ART_RE = /\bart\.?\s*(\d{1,4})/i;
function extractArtCode(text: string | undefined | null): string | null {
  if (!text) return null;
  const m = ART_RE.exec(String(text));
  return m ? "Art. " + m[1] : null;
}
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

// ---------- catálogo de regras (rubrica + infrações reais) ----------
const RULES: Record<string, Rule> = {};
export function rulesList(): Rule[] { return Object.values(RULES); }
export function ruleByCode(code: string): Rule {
  return RULES[code] || { code, nome: code, grav: "media", pontos: 0, desc: "—", checks: "—", enquad: { art: "", ctb: code, mbedv: "" } };
}
function ruleFromRubrica(r: RubricaInfracao): Rule {
  return {
    code: r.id, nome: r.descricao || r.id, grav: normGrav(r.gravidade), pontos: r.pontos || meta.grav[normGrav(r.gravidade)].pontos,
    desc: r.descricao || "", checks: r.vlm_prompt_hint || "", enquad: { art: "", ctb: r.base_legal || r.id, mbedv: r.base_legal || "" },
  };
}
function ruleFromInfra(i: Infracao): Rule {
  return {
    code: i.id, nome: i.titulo || i.id, grav: normGrav(i.gravidade), pontos: i.pontos || meta.grav[normGrav(i.gravidade)].pontos,
    desc: i.descricao_longa || i.descricao || "", checks: i.evidencia || "", enquad: { art: "", ctb: i.base_legal || i.id, mbedv: i.base_legal || "" },
  };
}
export function loadRubricaRules(rf: RubricaFull): void {
  (rf?.infracoes || []).forEach((r) => { RULES[r.id] = ruleFromRubrica(r); });
}

// ---------- scoring ----------
export function ptsOf(codes: string[]): { pts: number; grav: boolean; label: string } {
  const pts = codes.reduce((s, c) => s + (ruleByCode(c).pontos || 0), 0);
  const grav = codes.some((c) => ruleByCode(c).grav === "gravissima");
  return { pts, grav, label: pts + (pts === 1 ? " pt" : " pts") };
}
export function verdictOf(codes: string[]): "aprovado" | "reprovado" {
  const s = ptsOf(codes); return s.grav || s.pts > 10 ? "reprovado" : "aprovado";
}

// hashCode determinístico (FNV-1a) — base de Waveform/frameScene (protótipo painel-model.jsx)
export function hashCode(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

// ---------- API ----------
async function jget<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: "include", headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error("HTTP " + r.status + " em " + url);
  return r.json() as Promise<T>;
}

// POST JSON resiliente: devolve o corpo parseado; lança em erro de rede/HTTP.
async function jpost<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("HTTP " + r.status + " em " + url);
  return r.json() as Promise<T>;
}

// retry com backoff exponencial leve (default 3 tentativas: 0ms, 350ms, 900ms).
async function withRetry<T>(fn: () => Promise<T>, tries = 3, baseDelay = 350): Promise<T> {
  let lastErr: unknown;
  for (let i = 0; i < tries; i++) {
    try { return await fn(); }
    catch (e) {
      lastErr = e;
      if (i < tries - 1) await new Promise((res) => setTimeout(res, baseDelay * (i + 1)));
    }
  }
  throw lastErr;
}

// Persistência do parecer do Auditor. A fila é indexada por hash; o backend
// resolve hash→os_id e grava em auditor_pareceres (endpoint resiliente: nunca 500).
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
export async function fetchRubrica(): Promise<void> {
  try { const rf = await jget<RubricaFull>("/api/rubricas/1020-2025"); loadRubricaRules(rf); } catch { /* picker fica limitado */ }
}

// ---------- timeline real: filmstrip (thumbnails) + waveform ----------
// GET /api/exams/{hash}/thumbnails?n=48 -> { n, frames: string[] (data URLs) }.
// Resiliente: qualquer falha -> [] (a Filmstrip degrada pro gradiente).
export async function fetchThumbnails(hash: string, n = 48): Promise<string[]> {
  try {
    const d = await jget<{ frames?: string[] }>(`/api/exams/${hash}/thumbnails?n=${n}`);
    return Array.isArray(d?.frames) ? d.frames : [];
  } catch { return []; }
}
// GET /api/exams/{hash}/waveform?buckets=400 -> { buckets, peaks: number[] (0..1) }.
// Resiliente: qualquer falha -> [] (a Waveform cai no placeholder por hashCode).
export async function fetchWaveform(hash: string, buckets = 400): Promise<number[]> {
  try {
    const d = await jget<{ peaks?: number[] }>(`/api/exams/${hash}/waveform?buckets=${buckets}`);
    return Array.isArray(d?.peaks) ? d.peaks : [];
  } catch { return []; }
}
export async function fetchVideos(): Promise<VideoItem[]> {
  // Fila do Auditor: só exames que AINDA divergem após o Comitê de IA (prompt MBEDV).
  const d = await jget<VideoItem[] | { videos?: VideoItem[]; items?: VideoItem[] }>("/api/videos?only_unresolved=true");
  const arr = Array.isArray(d) ? d : (d.videos || d.items || []);
  return arr.filter((v) => v.has_result && v.status === "processed");
}
export function videoToQueueItem(v: VideoItem): QueueItem {
  const tpRes: "aprovado" | "reprovado" = v.resultado_exame === "R" ? "reprovado" : "aprovado";
  const vbAprov = v.resultado === "APROVADO" || v.aprovado === true;
  const vbAval = v.resultado && v.resultado !== "SEM_AVALIACAO" && v.resultado !== "PENDENTE" && v.resultado !== "PROCESSANDO";
  // Decisão do Comitê de IA: "sem_divergencia" = resolvida; presente e != = ainda diverge.
  const posResolved = v.tipo_divergencia_pos_comite === "sem_divergencia";
  const posDivergent = v.tipo_divergencia_pos_comite != null && !posResolved;
  return {
    id: v.hash, hash: v.hash, renach: (v as { renach?: string }).renach || v.hash.slice(0, 10), examinador: "—",
    dur: 0, cat: v.categoria_cnh || "—",
    status: posDivergent ? "divergencia" : posResolved ? "finalizado" : (v.resultado_exame == null ? "divergencia" : "finalizado"),
    resultadoExame: v.resultado_exame ?? null,
    tp: { result: tpRes, faults: [], pts: 0 },
    vb: vbAval ? { result: vbAprov ? "aprovado" : "reprovado", faults: [], pts: v.pontuacao_total || 0, conf: 0.95 } : null,
    tpComment: "", vbComment: "",
  };
}

// detalhe carregado do result.json real
export interface ExamDetail { q: QueueItem; marks: ClipMarks; dur: number; videoUrl: string; recomendacao: string; }
export async function fetchExamDetail(item: QueueItem): Promise<ExamDetail> {
  const res = await withRetry(() => jget<LaudoResponse>(`/api/analyses/hash/${item.hash}/result`));
  const infra = res.scored?.infracoes || [];
  // registra cada infração como regra (ficha sempre abre) e como marcador VB
  const vb: Mark[] = infra.map((i) => {
    RULES[i.id] = RULES[i.id] || ruleFromInfra(i);
    if (!RULES[i.id].desc) RULES[i.id] = ruleFromInfra(i);
    const t = parseMMSS(i.timestamp_inicio);
    return { code: i.id, t, len: Math.max(2, i.duracao_seg || 4), grav: normGrav(i.gravidade), conf: 0.95, ator: i.ator };
  }).sort((a, b) => a.t - b.t);
  // anotações do examinador presencial (training_annotations top-level ou em exame)
  const tpAnnotations = parseTrainingAnnotations(res);
  const tpComment = tpAnnotations
    .map((a) => (a.t > 0 ? `[${fmtDur(a.t)}] ` : "") + a.text)
    .join("\n");

  // dur PRIMEIRO (necessário p/ posicionar anotações órfãs em sequência).
  const validAnnoTs = tpAnnotations.filter((a) => a.t > 0).map((a) => a.t);
  const dur = res.summary?.duracao_seg
    || (vb.length || validAnnoTs.length
      ? Math.max(...[...vb.map((m) => m.t + m.len), ...validAnnoTs]) + 10
      : 60);

  // TODAS as anotações viram marcador na trilha TechPrático (com E sem Art.):
  //  - 0 < t <= dur -> marcador em t;  - órfãs (t==0 ou t > dur) -> em SEQUÊNCIA a
  //    partir de 00:00 (1ª em 0:00, próximas logo após), na ordem original.
  // Com Art. -> kind "infra" (pontua); sem Art. -> kind "nota" (observação neutra).
  const ORPHAN_GAP = 5; // segundos entre órfãs em sequência
  let orphanIdx = 0;
  const tpMarks: Mark[] = tpAnnotations
    .map((a) => {
      const inWindow = a.t > 0 && a.t <= dur;
      const t = inWindow ? a.t : Math.min(Math.max(0, dur - 4), (orphanIdx++) * ORPHAN_GAP);
      if (a.code) {
        const code = a.code;
        return { code, t, len: 4, grav: ruleByCode(code).grav, kind: "infra" as const };
      }
      return { code: "", t, len: 4, grav: "leve" as Grav, kind: "nota" as const, note: a.text };
    })
    .sort((a, b) => a.t - b.t);
  // só infrações (com Art.) contam para faults/pontuação.
  const tpFaults = Array.from(new Set(tpMarks.filter((m) => m.kind !== "nota" && m.code).map((m) => m.code)));

  const ex = res.exame || ({} as { renach?: string; examinador?: string; categoria?: string });
  const q: QueueItem = {
    ...item,
    renach: ex.renach || item.renach,
    examinador: ex.examinador || item.examinador,
    cat: ex.categoria || item.cat,
    dur,
    tp: { ...item.tp, faults: tpFaults, pts: ptsOf(tpFaults).pts },
    vb: { result: res.summary?.aprovado ? "aprovado" : "reprovado", faults: vb.map((m) => m.code), pts: res.summary?.pontuacao_total || 0, conf: (res.summary?.confianca_media || 95) / 100 },
    tpComment,
    vbComment: (res.pontos_atencao && res.pontos_atencao.length ? res.pontos_atencao.join(" · ") : (res.positivos || []).join(" · ")) || "Análise concluída pela IA (Gemini).",
    tpAnnotations,
  };
  const tpSet = new Set(tpFaults);
  const vbSet = new Set(vb.map((m) => m.code));
  const onlyVb = vb.filter((m) => !tpSet.has(m.code));
  // divergência só entre infrações; notas não contam.
  const onlyTp = tpMarks.filter((m) => m.kind !== "nota" && m.code && !vbSet.has(m.code));
  const divRegions = [...onlyVb, ...onlyTp].map((m) => ({ from: m.t, to: m.t + m.len }));
  const marks: ClipMarks = { tp: tpMarks, vb, onlyTp, onlyVb, divRegions, processing: false, interrupt: null };
  const videoUrl = `/api/exams/${item.hash}/video`;
  const recomendacao = q.vbComment;
  return { q, marks, dur, videoUrl, recomendacao };
}

export function initLaudo(): Mark[] { return []; }
