// src/pages/FilaAuditor.tsx — Fila do Auditor (tela imersiva) ligada à API REAL de produção.
// /api/videos (fila) · /api/analyses/hash/{hash}/result (Gemini) · /api/exams/{hash}/video · /api/rubricas/1020-2025.
import { useState, useEffect, useMemo, useRef } from "react";
import type * as React from "react";
import type { QueueItem, Mark, Rule, ClipMarks, Grav, ExamDetail } from "../lib/painel";
import {
  fetchRubrica, fetchVideos, fetchExamDetail, videoToQueueItem, rulesList, ruleByCode,
  gravColor, fmtDur, ptsOf, verdictOf, meta, fetchThumbnails, fetchWaveform, hashCode,
  postParecerAuditor,
} from "../lib/painel";
import "../styles/painel.css";
import { HowItWorks } from "@/components/painel/HowItWorks";
import { TourOverlay } from "@/components/painel/TourOverlay";
import { DetailModal as DetailModalNew } from "@/components/painel/DetailModal";
import { FaultPicker as FaultPickerNew, type Rule as PickerRule, type Suggestion as PickerSuggestion } from "@/components/painel/FaultPicker";

type IcoProps = { width?: number; height?: number; style?: React.CSSProperties };
const svg = (p: IcoProps, path: React.ReactNode, fill = false) => (
  <svg width={p.width || 16} height={p.height || 16} viewBox="0 0 24 24" fill={fill ? "currentColor" : "none"} stroke={fill ? "none" : "currentColor"} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" style={p.style}>{path}</svg>
);
const I = {
  close: (p: IcoProps = {}) => svg(p, <path d="M6 6l12 12M18 6L6 18" />),
  user: (p: IcoProps = {}) => svg(p, <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /></>),
  dash: (p: IcoProps = {}) => svg(p, <><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" /></>),
  video: (p: IcoProps = {}) => svg(p, <><rect x="3" y="6" width="13" height="12" rx="2" /><path d="M16 10l5-3v10l-5-3z" /></>),
  search: (p: IcoProps = {}) => svg(p, <><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>),
  arrow: (p: IcoProps = {}) => svg(p, <path d="M5 12h14M13 6l6 6-6 6" />),
  target: (p: IcoProps = {}) => svg(p, <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /></>),
  check: (p: IcoProps = {}) => svg(p, <path d="M20 6L9 17l-5-5" />),
};

const LS = "vb-painel-v3";
function loadState(): Record<string, unknown> { try { return JSON.parse(localStorage.getItem(LS) || "{}"); } catch { return {}; } }
function saveState(p: Record<string, unknown>) { try { localStorage.setItem(LS, JSON.stringify({ ...loadState(), ...p })); } catch { /* noop */ } }
// Fila de pareceres salvos localmente quando a rede falha (sincroniza depois).
const LS_PENDING = "vb-painel-pareceres-pendentes";
function savePendingParecer(hash: string, payload: unknown) {
  try {
    const cur = JSON.parse(localStorage.getItem(LS_PENDING) || "{}");
    cur[hash] = { ...(payload as object), savedAt: new Date().toISOString() };
    localStorage.setItem(LS_PENDING, JSON.stringify(cur));
  } catch { /* noop */ }
}
function tk(g: Grav) { return { color: gravColor(g), bg: "color-mix(in oklab," + gravColor(g) + ", transparent 84%)" }; }

/* ---------- adapters p/ componentes painel/ ---------- */
// rulesList() já é estruturalmente um PickerRule[]; helper só fixa o tipo.
function pickerRules(): PickerRule[] { return rulesList() as unknown as PickerRule[]; }
// marcadores VB viram sugestões de proximidade do FaultPicker novo.
function toSuggestions(marks: ClipMarks): PickerSuggestion[] {
  return marks.vb.map((m) => ({ code: m.code, grav: m.grav, t: m.t }));
}
// monta o `rule` (à prova de falhas) do DetailModal novo a partir do Mark + exame.
function toDetailRule(m: Mark, q: QueueItem | null) {
  const r = ruleByCode(m.code), g = meta.grav[m.grav];
  return {
    code: r.code, nome: r.nome, desc: r.desc || r.nome, grav: m.grav, pontos: r.pontos,
    checks: r.checks || undefined,
    enquad: { art: r.enquad.art, ctb: r.enquad.ctb, mbedv: r.enquad.mbedv },
    detectadoPor: m.ator || (q && q.vb && q.vb.faults.includes(m.code) ? "ValBot · IA Gemini" : "Laudo do auditor"),
    ocorrencia: fmtDur(m.t) + " – " + fmtDur(m.t + m.len),
    comentarios: [
      { source: "vb", avatar: "IA", author: "ValBot · Gemini", meta: fmtDur(m.t), text: r.desc || r.nome },
    ],
  };
}

/* ---------- StatStrip ---------- */
function StatStrip({ divCount, laudoLen, q }: { divCount: number; laudoLen: number; q: QueueItem }) {
  const st = { divergencia: { t: "Em análise", c: "var(--proc)" }, finalizado: { t: "Finalizado", c: "var(--ok)" }, processando: { t: "Processando", c: "var(--warn)" }, interrompido: { t: "Interrompido", c: "var(--bad)" } }[q.status];
  const conf = q.vb ? Math.round((q.vb.conf || 0.95) * 100) : null;
  const items = [
    { label: "Divergências", value: divCount, unit: "encontradas", color: divCount > 0 ? "var(--bad)" : "var(--ok)" },
    { label: "Infrações (IA)", value: q.vb ? q.vb.faults.length : 0, unit: "detectadas", color: "var(--warn)" },
    { label: "Status", value: st.t, unit: "", color: st.c },
    { label: "Confiança ValBot", value: conf == null ? "—" : "Alta " + conf + "%", unit: "", color: "var(--ok)" },
  ];
  void laudoLen;
  return (
    <div className="statstrip">
      {items.map((it, i) => (
        <div className="ss-cell" key={i}>
          <span className="ss-ic"><I.target width={20} height={20} /></span>
          <div className="ss-body"><div className="ss-label">{it.label}</div><div className="ss-value"><b style={{ color: it.color }}>{it.value}</b>{it.unit ? <span className="ss-unit"> {it.unit}</span> : null}</div></div>
        </div>
      ))}
    </div>
  );
}

/* ---------- FrameAnno (anotação on-frame + ticker lower-third) ---------- */
// Reúne os marcadores TP/ValBot/Auditor, mantém só os ativos no playhead (com dedup
// por fonte+código) e desenha a moldura pulsante + a tarja TV com a infração corrente.
function FrameAnno({ marks, pos, dur }: { marks: { tp: Mark[]; vb: Mark[]; laudo: Mark[] }; pos: number; dur: number }) {
  const srcLabel: Record<"tp" | "vb" | "laudo", string> = { tp: "TechPrático", vb: "ValBot", laudo: "Auditor" };
  // janela efetiva = mesma largura visual do marcador na timeline (mín. 30px)
  const ppsApprox = Math.max(0.4, (window.innerWidth - 132) / (dur || 1));
  const minSec = 30 / ppsApprox;
  const all: (Mark & { src: "tp" | "vb" | "laudo" })[] = [
    ...(marks.tp || []).map((m) => ({ ...m, src: "tp" as const })),
    ...(marks.vb || []).map((m) => ({ ...m, src: "vb" as const })),
    ...(marks.laudo || []).map((m) => ({ ...m, src: "laudo" as const })),
  ];
  // dedup por código+fonte, mantém só ativos no playhead
  const seen = new Set<string>();
  const active = all.filter((m) => {
    const end = m.t + Math.max(m.len, minSec);
    if (pos < m.t - 0.3 || pos > end) return false;
    const k = m.src + m.code; if (seen.has(k)) return false; seen.add(k); return true;
  });
  if (!active.length) return null;
  return (
    <>
      {active.map((m, i) => (
        <div key={m.src + m.code} className="frame-anno" style={{ ["--gc" as string]: gravColor(m.grav), inset: (12 + i * 9) + "px", zIndex: 3 + i } as React.CSSProperties} />
      ))}
      <div className="fa-legend">
        {active.map((m) => (
          <span key={"lg" + m.src + m.code} className="fa-badge" style={{ background: gravColor(m.grav) }}>{srcLabel[m.src]}</span>
        ))}
      </div>
      {active.map((m, i) => {
        const r = ruleByCode(m.code);
        const run = r.nome + " — " + (r.desc || r.nome) + " · " + srcLabel[m.src] + (m.conf != null ? " " + Math.round(m.conf * 100) + "%" : "") + " · " + fmtDur(m.t);
        return (
          <div key={"tk" + m.src + m.code} className="anno-ticker" style={{ ["--gc" as string]: gravColor(m.grav), bottom: (16 + i * 38) + "px" } as React.CSSProperties}>
            <span className="tk-tag mono">{r.enquad.ctb}</span>
            <div className="tk-viewport">
              <div className="tk-run">
                <span className="tk-text">{run}</span>
                <span className="tk-text" aria-hidden="true">{run}</span>
              </div>
            </div>
          </div>
        );
      })}
    </>
  );
}

/* ---------- Viewer (vídeo REAL) ---------- */
function Viewer({ q, marks, laudo, pos, dur, playing, setPlaying, onSeek, onWatch, videoUrl, videoRef, onVideoError, onLoadedMeta }: {
  q: QueueItem; marks: ClipMarks; laudo: Mark[]; pos: number; dur: number; playing: boolean;
  setPlaying: (f: (p: boolean) => boolean) => void; onSeek: (t: number) => void; onWatch: (t: number) => void;
  videoUrl: string; videoRef: React.RefObject<HTMLVideoElement | null>; onVideoError: () => void;
  onLoadedMeta: (d: number) => void;
}) {
  const scrubRef = useRef<HTMLDivElement | null>(null);
  const scrub = (e: React.MouseEvent) => { const r = scrubRef.current!.getBoundingClientRect(); onSeek(Math.max(0, Math.min(dur, (e.clientX - r.left) / r.width * dur))); };
  const initials = q.examinador && q.examinador !== "—" ? q.examinador.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase() : "VB";
  return (
    <div className="viewer-wrap">
      <div className="viewer-bar"><span className="vb-renach mono">{q.renach}</span><span className="vb-exam"><span className="vb-exam-av">{initials}</span>Cat {q.cat} · {q.examinador !== "—" ? "Exam. " + q.examinador : "exame"}</span></div>
      <StatStrip divCount={marks.onlyVb.length} laudoLen={0} q={q} />
      <div className={"viewer" + (playing ? " playing" : "")} onClick={() => setPlaying((p) => !p)}>
        <video ref={videoRef} src={videoUrl} className="viewer-video" playsInline preload="metadata"
          onLoadedMetadata={(e) => onLoadedMeta((e.target as HTMLVideoElement).duration)}
          onDurationChange={(e) => onLoadedMeta((e.target as HTMLVideoElement).duration)}
          onTimeUpdate={(e) => onWatch((e.target as HTMLVideoElement).currentTime)} onEnded={() => setPlaying(() => false)}
          onError={onVideoError} />
        <div className="viewer-grid" />
        <div className="viewer-safe" />
        <div className="viewer-play">{I.video({ width: 24, height: 24 })}</div>
        <FrameAnno marks={{ tp: marks.tp, vb: marks.vb, laudo }} pos={pos} dur={dur} />
        <div className="viewer-vign" />
      </div>
      <div ref={scrubRef} onMouseDown={scrub} style={{ height: 18, marginTop: 8, position: "relative", cursor: "text", display: "flex", alignItems: "center" }}>
        <div style={{ height: 4, borderRadius: 3, background: "var(--inset)", width: "100%", position: "relative" }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: (dur ? pos / dur * 100 : 0) + "%", background: "var(--accent)", borderRadius: 3 }} />
          {marks.vb.map((m, i) => <span key={i} style={{ position: "absolute", left: (dur ? m.t / dur * 100 : 0) + "%", top: -2, width: 2, height: 8, background: gravColor(m.grav) }} />)}
          <span style={{ position: "absolute", left: "calc(" + (dur ? pos / dur * 100 : 0) + "% - 6px)", top: -4, width: 12, height: 12, borderRadius: "50%", background: "#fff", boxShadow: "0 1px 4px rgba(0,0,0,.4)" }} />
        </div>
      </div>
    </div>
  );
}

function Transport({ queue: q, selId, setSel, pos, dur, playing, setPlaying, onSeek }: {
  queue: QueueItem[]; selId: string | null; setSel: (c: QueueItem) => void; pos: number; dur: number;
  playing: boolean; setPlaying: (f: (p: boolean) => boolean) => void; onSeek: (t: number) => void;
}) {
  const idx = q.findIndex((x) => x.id === selId);
  const go = (d: number) => { const n = q[idx + d]; if (n) setSel(n); };
  return (
    <div className="transport">
      <span className="tc-read mono">{fmtDur(Math.round(pos))}<span className="sep">/</span><span className="tot">{fmtDur(dur)}</span></span>
      <div className="tp-btns">
        <button className="tp-btn" title="-5s" onClick={() => onSeek(Math.max(0, pos - 5))}>«</button>
        <button className="tp-btn play" title="Reproduzir (espaço)" onClick={() => setPlaying((p) => !p)}>{playing ? "❚❚" : "►"}</button>
        <button className="tp-btn" title="+5s" onClick={() => onSeek(Math.min(dur, pos + 5))}>»</button>
      </div>
      <div className="tp-right">
        <button className="tp-nav" onClick={() => go(-1)} disabled={idx <= 0}>← Anterior</button>
        <span className="tp-meta mono">Exame {idx + 1}/{q.length}</span>
        <button className="tp-nav" onClick={() => go(1)} disabled={idx >= q.length - 1}>Próximo exame →</button>
      </div>
    </div>
  );
}

/* ---------- Timeline ---------- */
const GUTTER = 132;
function niceStep(pps: number): number { const t = 72 / pps, steps = [1, 2, 5, 10, 15, 20, 30, 60]; return steps.find((s) => s >= t) || 60; }

// Régua de timecodes — replica `Ruler` do protótipo (tick a cada ~72px, label nos pares).
function Ruler({ dur, pps }: { dur: number; pps: number }) {
  const step = niceStep(pps);
  const ticks: number[] = [];
  for (let t = 0; t <= dur; t += step) ticks.push(t);
  return (
    <div className="tl-track tl-ruler">
      <div className="tl-label"><span style={{ fontSize: 10, color: "var(--faint)", letterSpacing: ".5px" }}>TIMECODE</span></div>
      <div className="tl-lane" style={{ width: dur * pps }}>
        {ticks.map((t, i) => (
          <div key={i} className={"tl-tick" + (t % (step * 2) === 0 ? " major" : "")} style={{ left: t * pps }}>
            {t % (step * 2) === 0 && <span className="mono">{fmtDur(t)}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// Filmstrip — miniaturas REAIS do vídeo (`/thumbnails`) como `.film-cell` com
// background-image; sem frames, cada célula cai no gradiente do CSS (fallback).
function Filmstrip({ dur, pps, thumbs }: { dur: number; pps: number; thumbs: string[] }) {
  const w = dur * pps;
  const n = thumbs.length || Math.max(6, Math.round(w / 78));
  return (
    <div className="tl-track tl-film">
      <div className="tl-label"><I.video width={13} height={13} style={{ color: "var(--muted)" }} /><div style={{ minWidth: 0 }}><div>Vídeo</div><div className="tl-sub">imagem</div></div></div>
      <div className="tl-lane" style={{ width: w }}>
        <div className="film-frames">
          {Array.from({ length: n }, (_, i) => (
            <div key={i} className="film-cell" style={thumbs[i] ? { backgroundImage: `url(${thumbs[i]})` } : undefined} />
          ))}
        </div>
      </div>
    </div>
  );
}

// Waveform — desenha o SVG path a partir dos peaks REAIS (`/waveform`, 0..1).
// Sem peaks, usa hashCode determinístico (placeholder estável por hash do exame).
function Waveform({ dur, pps, seed, peaks }: { dur: number; pps: number; seed: string; peaks: number[] }) {
  const w = Math.round(dur * pps);
  const h = 40;
  const mid = h / 2;
  const real = peaks.length > 0;
  const n = real ? peaks.length : Math.min(360, Math.max(40, Math.round(w / 3)));
  const amp = (i: number): number => {
    if (real) return Math.max(0, Math.min(1, peaks[i])) * (mid - 3);
    const hsh = hashCode(seed + ":" + i) / 4294967295;
    const env = 0.35 + 0.65 * Math.abs(Math.sin((i / n) * Math.PI * 5) * Math.cos(i / 13));
    return (0.12 + 0.88 * hsh) * env * (mid - 3);
  };
  let d = `M0 ${mid}`;
  for (let i = 0; i < n; i++) { const x = (i / (n - 1)) * w; d += ` L${x.toFixed(1)} ${(mid - amp(i)).toFixed(1)}`; }
  for (let i = n - 1; i >= 0; i--) { const x = (i / (n - 1)) * w; d += ` L${x.toFixed(1)} ${(mid + amp(i)).toFixed(1)}`; }
  d += " Z";
  return (
    <div className="tl-track tl-wave">
      <div className="tl-label"><span className="tl-led" style={{ background: "var(--accent)" }} /><div style={{ minWidth: 0 }}><div>Áudio</div><div className="tl-sub">Examinador</div></div></div>
      <div className="tl-lane" style={{ width: w }}>
        <svg width={w} height={h} style={{ display: "block" }} preserveAspectRatio="none">
          <path d={d} fill="color-mix(in oklab, var(--accent), transparent 58%)" stroke="var(--accent)" strokeWidth={0.6} />
        </svg>
      </div>
    </div>
  );
}
function Marker({ m, pps, sel, onClick, accept, onAccept, onResize }: { m: Mark; pps: number; sel: boolean; onClick: (m: Mark) => void; accept?: boolean; onAccept?: (m: Mark) => void; onResize?: (code: string, t: number, len: number) => void; }) {
  const r = ruleByCode(m.code);
  const drag = (side: "l" | "r") => (e: React.MouseEvent) => {
    e.stopPropagation(); e.preventDefault();
    const sx = e.clientX, stt = m.t, sl = m.len;
    const move = (ev: MouseEvent) => { const d = (ev.clientX - sx) / pps; if (side === "l") { const nt = Math.max(0, Math.min(stt + sl - 1, stt + d)); onResize!(m.code, nt, sl - (nt - stt)); } else onResize!(m.code, stt, Math.max(1, sl + d)); };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
  };
  return (
    <div className={"marker" + (sel ? " sel" : "")} style={{ left: m.t * pps, width: Math.max(30, m.len * pps), ["--gc" as string]: gravColor(m.grav) } as React.CSSProperties}
      onClick={(e) => { e.stopPropagation(); onClick(m); }} title={r.enquad.ctb + " · " + r.nome + " · " + fmtDur(m.t)}>
      <span className="m-frame" /><span className="m-cap mono">{r.enquad.ctb}</span>
      {onResize && <span className="m-h m-h-l" onMouseDown={drag("l")} />}
      {onResize && <span className="m-h m-h-r" onMouseDown={drag("r")} />}
      {accept && onAccept && <button className="m-accept-big" title="Adicionar ao laudo" onClick={(e) => { e.stopPropagation(); onAccept(m); }}>+</button>}
    </div>
  );
}
function MarkerTrack(props: { label: string; sub: string | null; led: string; ledLogo?: boolean; marks: Mark[]; pps: number; dur: number; selCode: string | null; onMarker: (m: Mark) => void; accept?: boolean; onAccept?: (m: Mark) => void; region?: { from: number; to: number }[]; verdict?: { result: string; pts: number } | null; onResize?: (code: string, t: number, len: number) => void; emptyHint?: string; }) {
  const { label, sub, led, ledLogo, marks, pps, dur, selCode, onMarker, accept, onAccept, region, verdict, onResize, emptyHint } = props;
  return (
    <div className="tl-track tl-markers">
      <div className="tl-label">
        {ledLogo ? <span className="tl-led-logo">VB</span> : <span className="tl-led" style={{ background: led }} />}
        <div style={{ minWidth: 0 }}>
          <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
          {sub && <div className="tl-sub">{sub}</div>}
          {verdict && <div className={"tl-verdict " + (verdict.result === "aprovado" ? "ok" : "bad")}>{verdict.result === "aprovado" ? "Aprovado" : "Reprovado"}{verdict.result !== "aprovado" && verdict.pts ? " · " + verdict.pts + " pts" : ""}</div>}
        </div>
      </div>
      <div className="tl-lane" style={{ width: dur * pps }}>
        {region && region.map((rg, i) => <div key={"r" + i} className="div-region" style={{ left: rg.from * pps, width: (rg.to - rg.from) * pps }} />)}
        {marks.map((m, i) => <Marker key={m.code + i} m={m} pps={pps} sel={selCode === m.code} onClick={onMarker} accept={accept} onAccept={onAccept} onResize={onResize} />)}
        {!marks.length && emptyHint && <div className="lane-empty">{emptyHint}</div>}
      </div>
    </div>
  );
}
function Timeline({ q, marks, laudo, pos, dur, onSeek, selCode, onMarker, onAccept, onLaudoResize, divCount, thumbs, peaks }: { q: QueueItem; marks: ClipMarks; laudo: Mark[]; pos: number; dur: number; onSeek: (t: number) => void; selCode: string | null; onMarker: (m: Mark) => void; onAccept: (m: Mark) => void; onLaudoResize: (c: string, t: number, l: number) => void; divCount: number; thumbs: string[]; peaks: number[]; }) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [laneW, setLaneW] = useState(900);
  const [open, setOpen] = useState(() => loadState().tlOpen !== false);
  useEffect(() => { const el = scrollRef.current; if (!el) return; const upd = () => setLaneW(el.clientWidth); upd(); const ro = new ResizeObserver(upd); ro.observe(el); return () => ro.disconnect(); }, []);
  const pps = Math.max(0.4, (laneW - GUTTER) / (dur || 1));
  const ls = ptsOf(laudo.map((l) => l.code));
  const laudoVerd = laudo.length === 0 ? null : { result: ls.grav || ls.pts > 10 ? "reprovado" : "aprovado", pts: ls.pts };
  const seekLane = (e: React.MouseEvent) => { if ((e.target as HTMLElement).closest(".marker")) return; const lane = (e.currentTarget as HTMLElement).querySelector(".tl-lane"); if (!lane) return; const r = lane.getBoundingClientRect(); onSeek(Math.max(0, Math.min(dur, (e.clientX - r.left) / pps))); };
  return (
    <div className={"timeline" + (open ? "" : " timeline-collapsed")}>
      <div className="tl-bar">
        <button className="tl-toggle" onClick={() => setOpen((o) => { saveState({ tlOpen: !o }); return !o; })}><span className="tl-title">Linha do tempo</span></button>
        {divCount > 0 ? <span className="tl-divcount"><span className="dot" />{divCount} {divCount === 1 ? "divergência" : "divergências"}</span> : <span style={{ fontSize: 11.5, color: "var(--ok)", fontWeight: 600 }}>Sem divergências</span>}
        <span className="tl-fit mono">vídeo inteiro · {fmtDur(dur)}</span>
        <button className="tl-hide" onClick={() => setOpen((o) => { saveState({ tlOpen: !o }); return !o; })}>{open ? "Ocultar" : "Mostrar"}</button>
      </div>
      {open && (
        <div className="tl-scroll" ref={scrollRef}>
          <div className="tl-inner" style={{ width: GUTTER + dur * pps }} onMouseDown={seekLane}>
            <Ruler dur={dur} pps={pps} />
            <Filmstrip dur={dur} pps={pps} thumbs={thumbs} />
            <Waveform dur={dur} pps={pps} seed={q.hash} peaks={peaks} />
            <MarkerTrack label="TechPrático" sub="Examinador" led="#6b7689" marks={marks.tp} pps={pps} dur={dur} selCode={selCode} onMarker={onMarker} verdict={{ result: q.tp.result, pts: q.tp.pts }} emptyHint={"Resultado do examinador: " + (q.resultadoExame === "R" ? "Reprovado" : q.resultadoExame === "N" ? "Não avaliado" : "Aprovado") + " (infrações oficiais não detalhadas)"} />
            <MarkerTrack label="ValBot" sub="IA Gemini" led="var(--accent)" ledLogo marks={marks.vb} pps={pps} dur={dur} selCode={selCode} onMarker={onMarker} accept onAccept={onAccept} verdict={q.vb ? { result: q.vb.result, pts: q.vb.pts } : null} emptyHint="IA não detectou infrações" />
            <MarkerTrack label="Auditor" sub="Seu laudo" led="#B45309" marks={laudo} pps={pps} dur={dur} selCode={selCode} onMarker={onMarker} onResize={onLaudoResize} verdict={laudoVerd} emptyHint="Lance infrações para gravar aqui o seu laudo" />
            <div className="tl-playhead" style={{ left: GUTTER + pos * pps }}><span className="tl-playhead-tc mono">{fmtDur(Math.round(pos))}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Inspector ---------- */
function Comparison({ q }: { q: QueueItem }) {
  const tpS = ptsOf(q.tp.faults), vbS = q.vb ? ptsOf(q.vb.faults) : null;
  const rows = [
    { k: "Resultado", tp: q.tp.result === "aprovado" ? "Aprovado" : "Reprovado", vb: q.vb ? (q.vb.result === "aprovado" ? "Aprovado" : "Reprovado") : "—", div: !!q.vb && q.tp.result !== q.vb.result, tone: true },
    { k: "Pontuação", tp: q.resultadoExame ? "—" : tpS.label, vb: q.vb ? (q.vb.pts + " pts") : "—", div: false, tone: false },
    { k: "Infrações", tp: "—", vb: q.vb ? String(q.vb.faults.length) : "—", div: false, tone: false },
  ];
  const tone = (t: string) => t === "Aprovado" ? "var(--ok)" : t === "Reprovado" ? "var(--bad)" : "var(--text-2)";
  return (
    <div className="cmp">
      <div className="cmp-head"><span className="cmp-pillar">Comparação</span><span className="cmp-c"><span className="cmp-who tp">TechPrático</span></span><span className="cmp-c"><span className="cmp-who vb">ValBot</span></span></div>
      {rows.map((r) => (
        <div key={r.k} className={"cmp-row" + (r.div ? " div" : "")}>
          <span className="cmp-dim">{r.k}{r.div && <span className="cmp-flag">≠</span>}</span>
          <span className="cmp-c mono" style={{ color: r.tone ? tone(r.tp) : "var(--text)" }}>{r.tp}</span>
          <span className="cmp-c mono" style={{ color: r.tone ? tone(r.vb) : "var(--text)" }}>{r.vb}</span>
        </div>
      ))}
    </div>
  );
}
function FaultRow({ m, onClick, onRemove, onSetStart, onSetEnd, onNudge }: { m: Mark; onClick: (m: Mark) => void; onRemove: (m: Mark) => void; onSetStart: (m: Mark) => void; onSetEnd: (m: Mark) => void; onNudge: (m: Mark, which: "start" | "end", delta: number) => void; }) {
  const r = ruleByCode(m.code), t = tk(m.grav), ptsLbl = r.pontos + (r.pontos === 1 ? " pt" : " pts");
  return (
    <div className="fault-row">
      <button className="fr-main" onClick={() => onClick(m)} title={r.desc}>
        <span className="fc-code mono" style={{ color: t.color, background: t.bg }}>{r.enquad.ctb}</span>
        <span className="fr-name">{r.nome}</span><span className="fr-pts mono" style={{ color: t.color }}>{ptsLbl}</span>
        <span className="fr-x" onClick={(e) => { e.stopPropagation(); onRemove(m); }}>{I.close({ width: 13, height: 13 })}</span>
      </button>
      <div className="fr-meta">
        <span className="fr-occ">Início</span>
        <span className="fr-stepper">
          <button className="fr-step" onClick={() => onNudge(m, "start", -1)} title="Recuar o início 1s">−</button>
          <button className="fr-ev mono" onClick={() => onClick(m)} title="Ir para o início da infração">{I.video({ width: 11, height: 11 })}{fmtDur(m.t)}</button>
          <button className="fr-step" onClick={() => onNudge(m, "start", 1)} title="Avançar o início 1s">+</button>
        </span>
        <button className="fr-settime" onClick={() => onSetStart(m)} title="Definir início no tempo atual do vídeo">marcar</button>
        <span className="fr-occ" style={{ marginLeft: 4 }}>Fim</span>
        <span className="fr-stepper">
          <button className="fr-step" onClick={() => onNudge(m, "end", -1)} title="Recuar o fim 1s">−</button>
          <button className="fr-ev mono" onClick={() => onClick({ ...m, t: m.t + m.len })} title="Ir para o fim da infração">{fmtDur(m.t + m.len)}</button>
          <button className="fr-step" onClick={() => onNudge(m, "end", 1)} title="Avançar o fim 1s">+</button>
        </span>
        <button className="fr-settime" onClick={() => onSetEnd(m)} title="Finalizar a infração no tempo atual">marcar</button>
      </div>
    </div>
  );
}
const PK_FILTERS: [string, string][] = [["todas", "Todas"], ["gravissima", "Gravíssimas"], ["grave", "Graves"], ["media", "Médias"], ["leve", "Leves"]];
function RuleFicha({ r, added, onAdd, onBack }: { r: Rule; added: boolean; onAdd: (c: string) => void; onBack: () => void }) {
  const t = tk(r.grav);
  return (
    <div className="pkf">
      <div className="pkf-bar"><button className="pkf-back" onClick={onBack}>{I.arrow({ width: 15, height: 15, style: { transform: "rotate(180deg)" } })}Voltar</button><span className="pkf-tag">Ficha do procedimento</span></div>
      <div className="pkf-body">
        <div className="pkf-top"><span className="pk-code mono" style={{ color: t.color, background: t.bg }}>{r.enquad.ctb}</span><span className="pkf-grav" style={{ color: t.color, background: t.bg }}>{meta.grav[r.grav].label} · {r.pontos} pts</span></div>
        <h3 className="pkf-name">{r.nome}</h3>
        <div className="pkf-sec">Definição</div><p className="pkf-text">{r.desc || "—"}</p>
        {r.checks && <><div className="pkf-sec">{I.target({ width: 13, height: 13 })}Como o ValBot detecta</div><p className="pkf-text">{r.checks}</p></>}
        <div className="pkf-sec">Enquadramento</div><div className="pkf-norm mono">{r.enquad.ctb}{r.enquad.mbedv ? " · " + r.enquad.mbedv : ""}</div>
      </div>
      <div className="pkf-foot"><button className="lbtn" onClick={onBack}>Voltar</button><button className="lbtn warn" disabled={added} onClick={() => onAdd(r.code)}>{added ? "Já no laudo" : "Lançar esta infração"}</button></div>
    </div>
  );
}
function FaultPickerInline({ has, onAdd, onClose, pos, marks }: { has: Set<string>; onAdd: (c: string) => void; onClose: () => void; pos: number; marks: ClipMarks }) {
  const [query, setQuery] = useState(""); const [g, setG] = useState("todas"); const [view, setView] = useState<Rule | null>(null);
  const all = rulesList();
  const avail = all.filter((r) => !has.has(r.code));
  const list = avail.filter((r) => (g === "todas" || r.grav === g) && (!query || (r.nome + " " + r.code + " " + r.enquad.ctb + " " + r.desc).toLowerCase().includes(query.toLowerCase())));
  const near: Mark[] = []; const seen = new Set<string>();
  [...marks.vb].sort((a, b) => Math.abs(a.t - pos) - Math.abs(b.t - pos)).forEach((m) => { if (!has.has(m.code) && !seen.has(m.code) && Math.abs(m.t - pos) <= 12) { seen.add(m.code); near.push(m); } });
  return (
    <div className="pk-scrim" onClick={onClose}>
      <div className="pk" onClick={(e) => e.stopPropagation()}>
        {view ? <RuleFicha r={view} added={has.has(view.code)} onAdd={onAdd} onBack={() => setView(null)} /> : (
          <>
            <div className="pk-start"><span className="pk-start-ic">{I.target({ width: 20, height: 20 })}</span><div className="pk-start-body"><div className="pk-start-lbl">Início da infração</div><div className="pk-start-help">O fim você ajusta depois no laudo.</div></div><div className="pk-start-tc mono">{fmtDur(Math.round(pos))}</div></div>
            <div className="pk-search-row"><div className="pk-search">{I.search({})}<input autoFocus placeholder="Buscar infração, artigo, palavra-chave…" value={query} onChange={(e) => setQuery(e.target.value)} /></div><button className="pk-x" onClick={onClose}>{I.close({})}</button></div>
            {near.length > 0 && !query && <div className="pk-sug"><div className="pk-sug-lbl">Detectadas pela IA neste trecho</div><div className="pk-sug-row">{near.map((m) => { const r = ruleByCode(m.code), t = tk(m.grav); return <button key={m.code} className="pk-sug-chip" style={{ color: t.color, background: t.bg }} onClick={() => onAdd(m.code)} title={r.nome}><span className="mono">{r.enquad.ctb}</span><span className="pk-sug-t mono">{fmtDur(m.t)}</span>+</button>; })}</div></div>}
            <div className="pk-filters">{PK_FILTERS.map(([k, l]) => <button key={k} className={"pk-chip" + (g === k ? " on" : "")} onClick={() => setG(k)}>{k !== "todas" && <span className="pk-chip-dot" style={{ background: gravColor(k as Grav) }} />}{l}</button>)}</div>
            <div className="pk-list">
              {list.map((r) => { const t = tk(r.grav); return (
                <div key={r.code} className="pk-item2" style={{ ["--gc" as string]: t.color } as React.CSSProperties}>
                  <button className="pk-item2-main" onClick={() => onAdd(r.code)}><span className="pk-code mono" style={{ color: t.color, background: t.bg }}>{r.enquad.ctb}</span><div className="pk-item2-txt"><div className="pk-name">{r.nome}</div><div className="pk-norm mono">{r.enquad.ctb}</div></div><span className="pk-pts mono" style={{ color: t.color }}>{r.pontos} pts</span></button>
                  <button className="pk-ficha" onClick={() => setView(r)} title="Ficha">{I.arrow({})}</button>
                </div>
              ); })}
              {!list.length && <div className="pk-empty">Nenhuma infração{query ? " para “" + query + "”" : ""}.</div>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
function Inspector({ q, marks, laudo, setLaudo, pos, dur, selCode, onSelectMark, onResolve, onAfterResolve, onPause, recomendacao }: { q: QueueItem; marks: ClipMarks; laudo: Mark[]; setLaudo: (f: (l: Mark[]) => Mark[]) => void; pos: number; dur: number; selCode: string | null; onSelectMark: (m: Mark) => void; onResolve: (r: "aprovado" | "reprovado", f: Mark[], n: string) => void | Promise<void>; onAfterResolve: () => void; onPause: () => void; recomendacao: string; }) {
  const [note, setNote] = useState(""); const [pickerOpen, setPickerOpen] = useState(false); const [confirm, setConfirm] = useState<"aprovado" | "reprovado" | null>(null);
  useEffect(() => setNote(""), [q.id]);
  void onAfterResolve; // resolve() avança internamente após persistir/fallback
  const has = new Set(laudo.map((l) => l.code));
  void selCode;
  const addLaudo = (code: string) => { if (has.has(code)) return; const ref = marks.vb.find((x) => x.code === code); setLaudo((l) => [...l, { code, t: ref ? ref.t : Math.round(pos), len: ref ? ref.len : 4, grav: ruleByCode(code).grav }].sort((a, b) => a.t - b.t)); setPickerOpen(false); };
  const removeLaudo = (m: Mark) => setLaudo((l) => l.filter((x) => x.code !== m.code));
  const setStartLaudo = (m: Mark) => setLaudo((l) => l.map((x) => x.code === m.code ? { ...x, len: Math.max(1, x.t + x.len - Math.round(pos)), t: Math.round(pos) } : x).sort((a, b) => a.t - b.t));
  const setEndLaudo = (m: Mark) => setLaudo((l) => l.map((x) => x.code === m.code ? { ...x, len: Math.max(1, Math.round(pos) - x.t) } : x));
  // move um extremo do Mark em ±delta segundos, mantendo o outro fixo, mín. 1s de duração e limitado pela duração do exame.
  const nudgeMark = (m: Mark, which: "start" | "end", delta: number) => setLaudo((l) => l.map((x) => {
    if (x.code !== m.code) return x;
    if (which === "start") { const end = x.t + x.len; const nt = Math.max(0, Math.min(end - 1, x.t + delta)); return { ...x, t: nt, len: end - nt }; }
    const maxLen = Math.max(1, Math.round(dur || x.t + x.len) - x.t);
    return { ...x, len: Math.max(1, Math.min(maxLen, x.len + delta)) };
  }).sort((a, b) => a.t - b.t));
  const ls = ptsOf(laudo.map((l) => l.code));
  // verdito do laudo pela mesma regra do scoring (verdictOf de painel.ts): gravíssima
  // ou > 10 pts ⇒ reprovação. Base da checagem de coerência decisão × laudo.
  const laudoResult: "aprovado" | "reprovado" = verdictOf(laudo.map((l) => l.code));
  // Parecer do ValBot: confiança (%) da IA, se disponível.
  const confPct = q.vb && q.vb.conf != null ? Math.round(q.vb.conf * 100) : null;
  // Comitê de IA (read-only): recomendação do comitê + status de divergência pós-comitê.
  const comiteRec = recomendacao || (marks.vb.length ? "Comitê avaliou as infrações detectadas." : "Sem recomendação do comitê para este exame.");
  // tipo_divergencia_pos_comite chega no item quando disponível; senão deriva do status.
  const posComite = (q as unknown as { tipo_divergencia_pos_comite?: string | null }).tipo_divergencia_pos_comite;
  const comiteStatus: { label: string; tone: string } | null =
    posComite === "sem_divergencia" ? { label: "Divergência resolvida", tone: "var(--ok)" }
    : posComite ? { label: "Divergência mantida", tone: "var(--bad)" }
    : q.status === "divergencia" ? { label: "Em divergência", tone: "var(--warn)" }
    : q.status === "finalizado" ? { label: "Concordante", tone: "var(--ok)" }
    : null;
  return (
    <div className="ppane insp">
      <div className="pane-head"><I.target width={14} height={14} /><span className="ph-title">Auditoria do laudo</span><span className="ph-formal">IA consultiva · decisão humana</span></div>
      <div className="insp-body">
        <Comparison q={q} />
        {recomendacao && (
          <div className="insp-rec">
            <div className="insp-rec-h">
              <img src="/logo.png" alt="ValBot" width="13" height="13" style={{ borderRadius: 3 }} />
              <span>Parecer do ValBot</span>
              {confPct != null && <span className="insp-rec-conf mono">{confPct}% confiança</span>}
            </div>
            <p className="insp-rec-t" title={recomendacao}>{recomendacao}</p>
          </div>
        )}
        <div className="insp-rec comite">
          <div className="insp-rec-h" style={{ color: "var(--text-2)" }}>{I.target({ width: 13, height: 13 })}<span>Comitê de IA</span>{comiteStatus && <span className="insp-rec-conf mono" style={{ color: comiteStatus.tone, background: "color-mix(in oklab," + comiteStatus.tone + ", transparent 86%)" }}>{comiteStatus.label}</span>}</div>
          <p className="insp-rec-t" title={comiteRec}>{comiteRec}</p>
          <div className="comite-note">IA consultiva · decisão humana.</div>
        </div>
        <div className="insp-actions"><div className="ia-row">
          <button className="lbtn bad" onClick={() => setConfirm("reprovado")}>{I.close({ width: 15, height: 15 })}Reprovar</button>
          <button className="lbtn ok" onClick={() => setConfirm("aprovado")}>{I.check({ width: 15, height: 15 })}Aprovar</button>
          <button className="lbtn warn" onClick={() => { onPause(); setPickerOpen(true); }}>+ Lançar infração</button>
        </div></div>
        <div className="laudo">
          <div className="laudo-head"><span className="src-avatar rev">{I.user({})}</span><div style={{ minWidth: 0, flex: 1 }}><div className="src-title">Infrações do laudo</div><div className="src-sub">Sua análise</div></div>
            <span className="lv-tag mono" style={{ background: laudoResult === "aprovado" ? "color-mix(in oklab,var(--ok),transparent 84%)" : "color-mix(in oklab,var(--bad),transparent 84%)", color: laudoResult === "aprovado" ? "var(--ok)" : "var(--bad)" }}>{ls.label} → {laudoResult === "aprovado" ? "Aprovado" : "Reprovado"}</span>
          </div>
          <div className="laudo-faults">{laudo.length ? laudo.map((m) => <FaultRow key={m.code} m={m} onClick={onSelectMark} onRemove={removeLaudo} onSetStart={setStartLaudo} onSetEnd={setEndLaudo} onNudge={nudgeMark} />) : <div className="laudo-hint">Use <b>Lançar infração</b> ou aceite os marcadores das trilhas (+).</div>}</div>
          <textarea className="laudo-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Fundamentação técnica do auditor…" />
        </div>
      </div>
      {pickerOpen && <FaultPickerNew rules={pickerRules()} startTime={pos} suggestions={toSuggestions(marks)} inLaudo={[...has]} onPick={addLaudo} onClose={() => setPickerOpen(false)} />}
      {confirm && (
        <div className="conf-scrim" onClick={() => setConfirm(null)}><div className="conf" onClick={(e) => e.stopPropagation()}>
          <div className="conf-head"><span className="conf-dot" style={{ background: confirm === "aprovado" ? "var(--ok)" : "var(--bad)" }} />Confirmar {confirm === "aprovado" ? "aprovação" : "reprovação"}</div>
          <div className="conf-body">
            <div className="conf-line">Exame <b className="mono">{q.renach}</b></div>
            <div className="conf-line">Pontuação <b className="mono">{ls.label}</b> · laudo configura <b style={{ color: laudoResult === "aprovado" ? "var(--ok)" : "var(--bad)" }}>{laudoResult === "aprovado" ? "Apto" : "Inapto"}</b></div>
            {confirm === laudoResult ? <div className="conf-valid ok">{I.check({ width: 15, height: 15 })}Decisão coerente com o laudo.</div> : <div className="conf-valid bad">⚠ {confirm === "aprovado" ? "O laudo soma " + ls.label + (ls.grav ? " (infração gravíssima)" : "") + " e configura reprovação — revise antes de aprovar." : (laudo.length ? "O laudo soma " + ls.label + ", insuficiente para reprovação — falta infração que a justifique." : "Não há infração lançada que justifique a reprovação.")}</div>}
          </div>
          <div className="conf-foot"><button className="lbtn" onClick={() => setConfirm(null)}>Cancelar</button><button className={"lbtn " + (confirm === "aprovado" ? "ok" : "bad")} disabled={confirm !== laudoResult} onClick={() => { void onResolve(confirm, laudo, note); setConfirm(null); }}>{confirm === "aprovado" ? "Aprovar e avançar" : "Reprovar e avançar"}</button></div>
        </div></div>
      )}
    </div>
  );
}

/* ---------- DetailModal (ficha — abre sempre) ---------- */
function DetailModalInline({ m, onClose }: { m: Mark; onClose: () => void }) {
  const r = ruleByCode(m.code), grav = meta.grav[m.grav];
  return (
    <div className="dm-scrim" onClick={onClose}>
      <div className="dm" onClick={(e) => e.stopPropagation()} style={{ ["--gc" as string]: gravColor(m.grav) } as React.CSSProperties}>
        <div className="dm-head"><span className="dm-code mono">{r.enquad.ctb}</span><span className="dm-grav" style={{ color: grav.color }}>{grav.label} · {r.pontos} pts</span><button className="dm-x" onClick={onClose}>{I.close({})}</button></div>
        <div className="dm-body">
          <div className="dm-title">{r.enquad.ctb} — {r.nome}</div>
          <div className="cmt"><div className="cmt-h"><span className="cmt-av vb">IA</span>ValBot · Gemini<span className="cmt-meta mono">{fmtDur(m.t)}</span></div><p className="dm-text">{r.desc || r.nome}</p></div>
          {r.checks && <><div className="dm-sec">Evidência / como detecta</div><p className="dm-text">{r.checks}</p></>}
          <div className="dm-sec">Enquadramento</div><p className="dm-text mono">{r.enquad.ctb}{r.enquad.mbedv ? " · " + r.enquad.mbedv : ""}</p>
        </div>
      </div>
    </div>
  );
}

/* ---------- raiz ---------- */
const DIRS: [string, string][] = [["grafite", "Grafite"], ["cobalto", "Cobalto"], ["claro", "Claro"]];
export default function FilaAuditor() {
  const [dir, setDir] = useState<string>((loadState().dir as string) || document.documentElement.getAttribute("data-dir") || "claro");
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [selId, setSelId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExamDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailErr, setDetailErr] = useState<string | null>(null);
  // Token da requisição corrente: cada selectClip incrementa; resoluções de fetch
  // antigas são descartadas (evita race no seek/playhead ao trocar de exame).
  const selReqRef = useRef(0);
  const [pos, setPos] = useState(0);
  // duração REAL do <video> (onLoadedMetadata). O backend (detail.dur) costuma vir
  // truncado/estimado; a fonte da verdade do "vídeo inteiro" é o elemento <video>.
  const [videoDur, setVideoDur] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selCode, setSelCode] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [det, setDet] = useState<Mark | null>(null);
  const [supOpen, setSupOpen] = useState(false);
  const [examOpen, setExamOpen] = useState(false);
  const [laudoMap, setLaudoMap] = useState<Record<string, Mark[]>>({});
  const [toast, setToast] = useState<string | null>(null);
  const [tourOpen, setTourOpen] = useState(false);
  // cache de filmstrip/waveform por hash do exame (busca 1x por exame).
  const [thumbsMap, setThumbsMap] = useState<Record<string, string[]>>({});
  const [peaksMap, setPeaksMap] = useState<Record<string, number[]>>({});
  // Trava de 1ª revisão: máximo já assistido por exame (segundos). Atualizado pelo
  // onTimeUpdate do vídeo; libera o seek para frente conforme o auditor assiste.
  const [watchedMaxMap, setWatchedMaxMap] = useState<Record<string, number>>({});

  useEffect(() => { document.documentElement.setAttribute("data-dir", dir); saveState({ dir }); }, [dir]);
  useEffect(() => { try { if (!localStorage.getItem("vb-guide")) setTourOpen(true); } catch { /* noop */ } }, []);
  useEffect(() => { (async () => {
    try { await fetchRubrica(); const vids = await fetchVideos(); const q = vids.map(videoToQueueItem); setQueue(q); setReady(true); if (q.length) selectClip(q[0]); else setErr("Nenhum exame processado disponível."); }
    catch (e) { setErr("Falha ao carregar exames: " + (e as Error).message); setReady(true); }
  })(); }, []);

  // ao abrir um exame, busca filmstrip + waveform uma vez (cache por hash; tolera vazio).
  useEffect(() => {
    const hash = detail?.q.hash;
    if (!hash) return;
    let alive = true;
    if (thumbsMap[hash] === undefined) {
      fetchThumbnails(hash, 48).then((frames) => { if (alive) setThumbsMap((m) => ({ ...m, [hash]: frames })); });
    }
    if (peaksMap[hash] === undefined) {
      fetchWaveform(hash, 400).then((p) => { if (alive) setPeaksMap((m) => ({ ...m, [hash]: p })); });
    }
    return () => { alive = false; };
  }, [detail?.q.hash]);

  const q = detail?.q || null;
  const marks: ClipMarks = detail?.marks || { tp: [], vb: [], onlyTp: [], onlyVb: [], divRegions: [], processing: false, interrupt: null };
  // Duração efetiva da timeline: máximo entre o backend e a duração real do vídeo.
  // Sem isto a timeline trunca (ex.: vídeo de 7min mostrando só 3min) e o playhead
  // estoura o quadro quando pos > dur (pos/dur*100 > 100%).
  const dur = Math.max(detail?.dur || 0, videoDur);
  const videoUrl = detail?.videoUrl || "";
  const laudo = (selId && laudoMap[selId]) || [];
  const setLaudo = (u: (l: Mark[]) => Mark[]) => { if (selId) setLaudoMap((m) => ({ ...m, [selId]: u(m[selId] || []) })); };
  const divCount = marks.onlyVb.length;
  const flash = (msg: string) => { setToast(msg); window.setTimeout(() => setToast(null), 1900); };

  // máximo já assistido do exame corrente (1ª revisão).
  const watchedMax = (selId && watchedMaxMap[selId]) || 0;
  // exame liberado para navegação livre quando já foi assistido (quase) até o fim.
  const watchedFull = dur > 0 && watchedMax >= dur - 1.5;
  // onWatch: relatório real de reprodução do vídeo (onTimeUpdate). Atualiza o playhead
  // e empurra watchedMax — nunca é bloqueado (é o que LIBERA o avanço).
  const onWatch = (t: number) => {
    setPos(t);
    if (selId) setWatchedMaxMap((m) => (t <= (m[selId] || 0) ? m : { ...m, [selId]: t }));
  };
  // guardedSeek: seek iniciado pelo usuário (scrub/marcador/transport). Na 1ª revisão
  // limita o avanço ao máximo já assistido + toast explicativo; voltar é sempre livre.
  const guardedSeek = (t: number) => {
    if (!watchedFull && t > watchedMax + 2) {
      flash("1ª revisão — o avanço libera conforme você assiste ao vídeo");
      setPos(Math.min(t, watchedMax));
      return;
    }
    setPos(t);
  };
  // espelho da trava p/ o handler de teclado (deps estáveis, sem stale closure).
  const guardRef = useRef({ watchedMax: 0, watchedFull: false });
  guardRef.current = { watchedMax, watchedFull };

  const loadDetail = async (item: QueueItem, token: number) => {
    setLoadingDetail(true); setDetailErr(null);
    try {
      const d = await fetchExamDetail(item);
      if (token !== selReqRef.current) return; // seleção mudou: descarta resultado antigo
      setDetail(d); const first = d.marks.vb[0]; if (first) setSelCode(first.code);
    } catch (e) {
      if (token !== selReqRef.current) return;
      setDetailErr("Não foi possível carregar o exame/vídeo. " + (e as Error).message);
    } finally {
      if (token === selReqRef.current) setLoadingDetail(false);
    }
  };
  const selectClip = (item: QueueItem) => {
    const token = ++selReqRef.current; // invalida fetches/estado do exame anterior
    setSelId(item.id); setPlaying(false); setPos(0); setVideoDur(0); setSelCode(null); setExamOpen(false);
    setDetail(null); setDetailErr(null);
    void loadDetail(item, token);
  };
  // Reabre o exame atualmente selecionado (botão "tentar de novo" do viewer).
  const retryDetail = () => { const it = queue.find((x) => x.id === selId); if (it) { const token = ++selReqRef.current; void loadDetail(it, token); } };
  // Falha de carregamento do VÍDEO (404/timeout no <video>): feedback no viewer
  // sem travar (a análise já carregou; só o vídeo falhou). "Tentar de novo" recarrega tudo.
  const onVideoError = () => {
    if (!videoUrl || detailErr) return;
    setPlaying(false);
    setDetailErr("Não foi possível carregar o vídeo deste exame (arquivo indisponível ou expirado).");
  };

  // vídeo real controla a timeline
  useEffect(() => { const v = videoRef.current; if (!v || !videoUrl) return; if (playing) v.play().catch(() => {}); else v.pause(); }, [playing, videoUrl, selId]);
  useEffect(() => { const v = videoRef.current; if (!v || !videoUrl) return; if (Math.abs(v.currentTime - pos) > 0.5) v.currentTime = pos; }, [pos, videoUrl]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName; if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.code === "Space") { e.preventDefault(); setPlaying((p) => !p); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); setPos((p) => Math.max(0, p - 1)); }
      else if (e.key === "ArrowRight") { e.preventDefault(); setPos((p) => { const next = Math.min(dur, p + 1); const g = guardRef.current; if (!g.watchedFull && next > g.watchedMax + 2) { flash("1ª revisão — o avanço libera conforme você assiste ao vídeo"); return Math.min(next, g.watchedMax); } return next; }); }
      else if (e.key === "[" || e.key === "]") { const i = queue.findIndex((x) => x.id === selId); const n = queue[i + (e.key === "]" ? 1 : -1)]; if (n) selectClip(n); }
    };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  }, [selId, dur, queue]);

  const seekToMark = (m: Mark) => {
    const blocked = !watchedFull && m.t > watchedMax + 2;
    if (!blocked) { setPos(m.t); const v = videoRef.current; if (v && videoUrl) { try { v.currentTime = m.t; } catch { /* */ } } }
    else flash("1ª revisão — assista até o ponto antes de pular para a infração");
    setSelCode(m.code); setDet(m);
  };
  const acceptMark = (m: Mark) => { setLaudo((l) => l.some((x) => x.code === m.code) ? l : [...l, { code: m.code, t: m.t, len: m.len, grav: m.grav }].sort((a, b) => a.t - b.t)); setSelCode(m.code); flash("Infração adicionada ao laudo"); };
  const resizeLaudo = (code: string, t: number, len: number) => setLaudo((l) => l.map((x) => x.code === code ? { ...x, t: Math.round(t), len: Math.max(1, Math.round(len)) } : x));
  const advanceNext = () => { const i = queue.findIndex((x) => x.id === selId); const n = queue[i + 1]; if (n) selectClip(n); else flash("Fila concluída"); };
  // Persiste o parecer no backend (resolve hash→os_id). Em falha de rede, NÃO perde
  // o parecer: grava no localStorage + toast e segue. Só avança após sucesso ou
  // fallback explícito.
  const resolve = async (result: "aprovado" | "reprovado", faults: Mark[], note: string) => {
    const hash = q?.hash;
    if (!hash) { flash("Sem exame selecionado"); return; }
    // decisao = concorda/discorda com o ValBot (IA). Se o resultado do auditor
    // bate com o veredito da IA, é concordância; senão, discordância.
    const vbResult = q?.vb?.result ?? null;
    const decisao: "concorda" | "discorda" = vbResult == null || vbResult === result ? "concorda" : "discorda";
    const payload = {
      decisao,
      resultado_final: result,
      infracoes: faults.map((m) => ({ code: m.code, t: m.t, len: m.len, grav: m.grav })),
      justificativa: note || "",
      referencia_mbedv: null as string | null,
    };
    try {
      const res = await postParecerAuditor(hash, payload);
      if (res.persisted) flash("Laudo " + (result === "aprovado" ? "aprovado" : "reprovado") + " e registrado");
      else { savePendingParecer(hash, payload); flash("Salvo localmente — sincroniza depois"); }
      advanceNext();
    } catch {
      // Erro de rede: não perde o parecer.
      savePendingParecer(hash, payload);
      flash("Sem conexão — salvo localmente, sincroniza depois");
      advanceNext();
    }
  };

  const statusLabel: Record<string, string> = { divergencia: "Em análise", finalizado: "Finalizado", processando: "Processando", interrompido: "Interrompido" };

  return (
    <div className="painel">
      <div className="pchrome">
        <div className="pbrand"><div className="pbrand-mark"><img src="/logo.png" alt="ValBot" width="32" height="32" /></div><div className="pbrand-name">Val<b>Bot</b></div></div>
        <span className="pchrome-sub">Painel do Auditor</span>
        {q && (
          <div className="exam-picker" style={{ marginLeft: 16, position: "relative" }}>
            <button className="exam-trigger" onClick={() => setExamOpen((o) => !o)} style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "var(--panel-2)", border: "1px solid var(--line)", color: "var(--text)", borderRadius: 8, padding: "6px 12px", cursor: "pointer", fontSize: 13 }}>
              <span className="mono">{q.renach}</span><span style={{ fontSize: 11, color: "var(--muted)" }}>{statusLabel[q.status]}</span><span>▾</span>
            </button>
            {examOpen && (
              <div style={{ position: "absolute", top: "115%", left: 0, zIndex: 60, minWidth: 340, maxHeight: 420, overflow: "auto", background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 10, boxShadow: "0 18px 48px rgba(0,0,0,.45)", padding: 6 }}>
                {queue.map((it) => (
                  <button key={it.id} onClick={() => selectClip(it)} style={{ display: "flex", width: "100%", alignItems: "center", gap: 10, padding: "9px 10px", borderRadius: 7, border: "none", background: it.id === selId ? "var(--hover)" : "transparent", color: "var(--text)", cursor: "pointer", textAlign: "left" }}>
                    <span className="mono" style={{ fontSize: 12 }}>{it.renach}</span>
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>Cat {it.cat}</span>
                    <span style={{ marginLeft: "auto", fontSize: 11, color: it.vb && it.vb.result === "reprovado" ? "var(--bad)" : "var(--ok)" }}>{it.vb ? (it.vb.result === "reprovado" ? "Reprovado" : "Aprovado") : "—"}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <span style={{ marginLeft: "auto" }} />
        <div className="pchrome-right">
          <div className="dirseg">{DIRS.map(([k, l]) => <button key={k} className={dir === k ? "on" : ""} onClick={() => setDir(k)}>{l}</button>)}</div>
          <button className="pchrome-btn" onClick={() => setSupOpen(true)}>{I.user({ width: 15, height: 15 })}Supervisor</button>
          <a href="/dashboard" className="pchrome-btn">{I.dash({ width: 15, height: 15 })}Dashboard</a>
        </div>
      </div>

      {!ready && <div style={{ padding: 60, textAlign: "center", color: "var(--muted)" }}>Carregando exames…</div>}
      {ready && err && <div style={{ padding: 60, textAlign: "center", color: "var(--bad)" }}>{err}</div>}
      {ready && !err && q && (
        <>
          <div className="pwork">
            <div className="pcenter">
              {detailErr ? (
                <div className="viewer-wrap"><div className="viewer" style={{ display: "grid", placeItems: "center", gap: 14, padding: 24, textAlign: "center" }}>
                  <div style={{ color: "var(--bad)", fontSize: 14, fontWeight: 600, maxWidth: 420 }}>{detailErr}</div>
                  <button className="lbtn warn" onClick={retryDetail} disabled={loadingDetail}>{loadingDetail ? "Tentando…" : "Tentar de novo"}</button>
                </div></div>
              ) : loadingDetail && !detail ? <div className="viewer-wrap"><div className="viewer" style={{ display: "grid", placeItems: "center", color: "var(--muted)" }}>Carregando vídeo e análise…</div></div>
                : <Viewer q={q} marks={marks} laudo={laudo} pos={pos} dur={dur} playing={playing} setPlaying={setPlaying} onSeek={guardedSeek} onWatch={onWatch} videoUrl={videoUrl} videoRef={videoRef} onVideoError={onVideoError} onLoadedMeta={(d) => { if (Number.isFinite(d) && d > 0) setVideoDur(d); }} />}
              <Transport queue={queue} selId={selId} setSel={selectClip} pos={pos} dur={dur} playing={playing} setPlaying={setPlaying} onSeek={guardedSeek} />
            </div>
            <Inspector q={q} marks={marks} laudo={laudo} setLaudo={setLaudo} pos={pos} dur={dur} selCode={selCode} onSelectMark={seekToMark} onResolve={resolve} onAfterResolve={advanceNext} onPause={() => setPlaying(false)} recomendacao={detail?.recomendacao || ""} />
          </div>
          <HowItWorks />
          <Timeline q={q} marks={marks} laudo={laudo} pos={pos} dur={dur} onSeek={guardedSeek} selCode={selCode} onMarker={seekToMark} onAccept={acceptMark} onLaudoResize={resizeLaudo} divCount={divCount} thumbs={(q && thumbsMap[q.hash]) || []} peaks={(q && peaksMap[q.hash]) || []} />
        </>
      )}

      {det && <DetailModalNew rule={toDetailRule(det, q)} onClose={() => setDet(null)} />}
      {supOpen && (
        <div className="dm-scrim" onClick={() => setSupOpen(false)}><div className="sup" onClick={(e) => e.stopPropagation()}>
          <div className="dm-head"><span style={{ fontWeight: 700, fontSize: 15 }}>Painel do Supervisor</span><button className="dm-x" style={{ marginLeft: "auto" }} onClick={() => setSupOpen(false)}>{I.close({})}</button></div>
          <div className="sup-body" style={{ padding: 16, color: "var(--muted)" }}>Decisão final do Supervisor — em breve.</div>
        </div></div>
      )}
      {tourOpen && <TourOverlay onClose={() => { try { localStorage.setItem("vb-guide", "1"); } catch { /* noop */ } setTourOpen(false); }} />}
      {toast && <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 80, background: "var(--elev)", color: "var(--text)", border: "1px solid var(--line)", padding: "10px 18px", borderRadius: 9, fontSize: 13, fontWeight: 600 }}>{toast}</div>}
    </div>
  );
}
