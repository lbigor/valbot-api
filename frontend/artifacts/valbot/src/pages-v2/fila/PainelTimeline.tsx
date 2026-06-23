/* ============================================================================
   Painel — Timeline (trilhas, régua, playhead) · porte de painel-timeline.jsx
   ============================================================================ */
import { useState, useEffect, useRef, Fragment } from "react";
import type { CSSProperties, ReactNode } from "react";
import { VB, gravColor, fmtDur } from "@/system/painel-data";
import type { MarkRef, ExamItem, AudioCue, Grav } from "@/system/painel-data";
import { I } from "./painelIcons";
import { VBP } from "./PainelModel";
import type { ClipMarks } from "./PainelModel";
import { loadState, saveState, guideSeen, markGuide } from "./painelState";

const GUTTER = 132;

/* Botão com guia didático reutilizável */
interface GuidedButtonProps {
  gkey: string;
  className: string;
  title: string;
  desc: string;
  actionLabel: string;
  onAct: () => void;
  children: ReactNode;
}
export function GuidedButton({ gkey, className, title, desc, actionLabel, onAct, children }: GuidedButtonProps) {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [dontShow, setDontShow] = useState(true);
  const btnRef = useRef<HTMLButtonElement>(null);
  const handle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (guideSeen().includes(gkey)) { onAct(); }
    else { setRect(btnRef.current!.getBoundingClientRect()); setOpen(true); }
  };
  const confirm = (e: React.MouseEvent) => { e.stopPropagation(); if (dontShow) markGuide(gkey); setOpen(false); onAct(); };
  return (
    <span className="guide-wrap">
      <button ref={btnRef} className={className} onClick={handle} title={title}>{children}</button>
      {open && rect && (
        <Fragment>
          <span className="guide-back" onClick={(e) => { e.stopPropagation(); setOpen(false); }} />
          <span className="guide-pop" style={{ left: rect.right, top: rect.top - 8, transform: "translate(-100%, -100%)" }} onClick={(e) => e.stopPropagation()}>
            <span className="guide-title"><span className="guide-badge">guia</span>{title}</span>
            <span className="guide-desc">{desc}</span>
            <span className="guide-actions">
              <button className="guide-skip" onClick={(e) => { e.stopPropagation(); setOpen(false); }}>Cancelar</button>
              <button className="guide-go" onClick={confirm}>{actionLabel}</button>
            </span>
            <label className="guide-check" onClick={(e) => e.stopPropagation()}>
              <input type="checkbox" checked={dontShow} onChange={(e) => setDontShow(e.target.checked)} />não mostrar mais este guia
            </label>
          </span>
        </Fragment>
      )}
    </span>
  );
}

function niceStep(pps: number): number {
  const target = 72 / pps;
  const steps = [1, 2, 5, 10, 15, 20, 30, 60];
  return steps.find((s) => s >= target) || 60;
}

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

function gravTok(g: Grav): string { return gravColor(g); }

interface MarkerProps {
  m: MarkRef; pps: number; sel: boolean; onClick: (m: MarkRef) => void;
  accept?: boolean; onAccept?: (m: MarkRef) => void; ghost?: boolean;
  onResize?: (code: string, t: number, len: number) => void;
}
function Marker({ m, pps, sel, onClick, accept, onAccept, ghost, onResize }: MarkerProps) {
  const isNota = m.kind === "nota";
  const r = VB.ruleByCode[m.code];
  // marcador de "nota" (observação do examinador sem Art.): rótulo/tooltip do texto,
  // estilo neutro, sem botão de aceitar (não enquadra infração) e sem ficha.
  if (isNota || !r) {
    const cap = isNota ? "Nota" : (m.code || "Nota");
    const txt = m.note || m.code || "Anotação do examinador";
    // cor neutra (cinza) para distinguir de infração; usa --gc como o marcador padrão.
    const style = { left: m.t * pps, width: Math.max(30, m.len * pps), "--gc": "#6b7689", borderStyle: "dashed" } as CSSProperties;
    return (
      <div className={"marker marker-nota" + (sel ? " sel" : "")} style={style}
        onClick={(e) => { e.stopPropagation(); onClick(m); }}
        title={"Anotação do examinador · " + fmtDur(m.t) + " — " + txt}>
        <span className="m-frame" />
        <span className="m-cap mono">
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 3, verticalAlign: "-1px" }}><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>
          {cap}
        </span>
      </div>
    );
  }
  const drag = (side: "l" | "r") => (e: React.MouseEvent) => {
    e.stopPropagation(); e.preventDefault();
    const sx = e.clientX, st = m.t, sl = m.len;
    const move = (ev: MouseEvent) => {
      const d = (ev.clientX - sx) / pps;
      if (side === "l") { const nt = Math.max(0, Math.min(st + sl - 1, st + d)); onResize!(m.code, nt, sl - (nt - st)); }
      else { onResize!(m.code, st, Math.max(1, sl + d)); }
    };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
  };
  const style = { left: m.t * pps, width: Math.max(30, m.len * pps), "--gc": gravTok(m.grav) } as CSSProperties;
  return (
    <div className={"marker" + (sel ? " sel" : "") + (ghost ? " ghost" : "")} style={style}
      onClick={(e) => { e.stopPropagation(); onClick(m); }} title={r.enquad.ctb + " · " + r.nome + " · " + fmtDur(m.t)}>
      <span className="m-frame" />
      <span className="m-cap mono">{r.enquad.ctb}</span>
      {onResize && <span className="m-h m-h-l" onMouseDown={drag("l")} title="Arrastar início" />}
      {onResize && <span className="m-h m-h-r" onMouseDown={drag("r")} title="Arrastar fim" />}
      {accept && (
        <GuidedButton gkey="accept-vb" className="m-accept-big" title="Adicionar ao laudo do Auditor"
          desc={"A infração " + r.enquad.ctb + " detectada pelo ValBot será lançada no SEU laudo (trilha do Auditor) no mesmo timestamp. Depois você pode ajustar início/fim e remover."}
          actionLabel="Adicionar ao laudo" onAct={() => onAccept!(m)}>+</GuidedButton>
      )}
    </div>
  );
}

interface MarkerTrackProps {
  label: string; sub?: string | null; led?: string; ledLogo?: boolean;
  marks: MarkRef[]; pps: number; dur: number; selCode: string | null;
  onMarker: (m: MarkRef) => void; accept?: boolean; onAccept?: (m: MarkRef) => void;
  ghostSet?: Set<string>; emptyHint?: string; region?: { from: number; to: number }[];
  verdict?: { result: string; pts?: number } | null; onResize?: (code: string, t: number, len: number) => void;
}
function MarkerTrack({ label, sub, led, ledLogo, marks, pps, dur, selCode, onMarker, accept, onAccept, ghostSet, emptyHint, region, verdict, onResize }: MarkerTrackProps) {
  return (
    <div className="tl-track tl-markers">
      <div className="tl-label">
        {ledLogo
          ? <span className="tl-led-logo"><img src="/logo.png" alt="ValBot" width="18" height="18" /></span>
          : <span className="tl-led" style={{ background: led }} />}
        <div style={{ minWidth: 0 }}>
          <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
          {sub && <div className="tl-sub">{sub}</div>}
          {verdict && <div className={"tl-verdict " + (verdict.result === "aprovado" ? "ok" : "bad")}>{verdict.result === "aprovado" ? "Aprovado" : "Reprovado"}{verdict.result !== "aprovado" && verdict.pts ? " · " + verdict.pts + " pts" : ""}</div>}
        </div>
      </div>
      <div className="tl-lane" style={{ width: dur * pps }}>
        {region && region.map((rg, i) => (
          <div key={"r" + i} className="div-region" style={{ left: rg.from * pps, width: (rg.to - rg.from) * pps }} />
        ))}
        {marks.map((m, i) => (
          <Marker key={m.code + i} m={m} pps={pps} sel={selCode === m.code}
            onClick={onMarker} accept={accept} onAccept={onAccept}
            ghost={ghostSet ? ghostSet.has(m.code) : false} onResize={onResize} />
        ))}
        {!marks.length && emptyHint && <div className="lane-empty">{emptyHint}</div>}
      </div>
    </div>
  );
}

// wrapper que torna a lane clicável para seek sem capturar cliques em marcadores
function SeekTrack({ children, dur, pps, onSeek }: { children: ReactNode; dur: number; pps: number; onSeek: (t: number) => void }) {
  const handle = (e: React.MouseEvent) => {
    const tgt = e.target as HTMLElement;
    if (tgt.closest(".marker") || tgt.closest(".m-accept")) return;
    const lane = (e.currentTarget as HTMLElement).querySelector(".tl-lane");
    if (!lane) return;
    const rect = lane.getBoundingClientRect();
    onSeek(Math.max(0, Math.min(dur, (e.clientX - rect.left) / pps)));
  };
  return <div style={{ display: "contents" }} onMouseDown={handle}>{children}</div>;
}

interface TimelineProps {
  q: ExamItem; marks: ClipMarks; laudo: MarkRef[]; pos: number; dur: number;
  onSeek: (t: number) => void; selCode: string | null; onMarker: (m: MarkRef) => void;
  onAccept: (m: MarkRef) => void; onLaudoResize: (code: string, t: number, len: number) => void; divCount: number;
}
export function Timeline({ q, marks, laudo, pos, dur, onSeek, selCode, onMarker, onAccept, onLaudoResize, divCount }: TimelineProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [laneW, setLaneW] = useState(900);
  const [open, setOpen] = useState(() => loadState().tlOpen !== false);
  const toggleOpen = () => setOpen((o) => { saveState({ tlOpen: !o }); return !o; });
  useEffect(() => {
    const el = scrollRef.current; if (!el) return;
    const upd = () => setLaneW(el.clientWidth);
    upd();
    const ro = new ResizeObserver(upd); ro.observe(el);
    return () => ro.disconnect();
  }, [open]);
  const pps = Math.max(0.4, (laneW - GUTTER) / dur);
  const laudoPts = laudo.reduce((s, m) => s + (VB.ruleByCode[m.code].pontos || 0), 0);
  const laudoGrav = laudo.some((m) => m.grav === "gravissima");
  const laudoVerd = laudo.length === 0 ? null : { result: (laudoGrav || laudoPts > 4) ? "reprovado" : "aprovado", pts: laudoPts };

  return (
    <div className={"timeline" + (open ? "" : " timeline-collapsed")}>
      <div className="tl-bar">
        <button className="tl-toggle" onClick={toggleOpen} aria-expanded={open}>
          <svg className="tl-chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
          <span className="tl-title">Linha do tempo</span>
        </button>
        {divCount > 0
          ? <span className="tl-divcount"><span className="dot" />{divCount} {divCount === 1 ? "divergência" : "divergências"} de alinhamento</span>
          : q.vb ? <span style={{ fontSize: 11.5, color: "var(--ok)", fontWeight: 600 }}>Trilhas alinhadas</span> : null}
        <span className="tl-fit mono">vídeo inteiro · {fmtDur(dur)}</span>
        <button className="tl-hide" onClick={toggleOpen}>{open ? "Ocultar" : "Mostrar"}</button>
      </div>

      {open && (
        <div className="tl-scroll" ref={scrollRef}>
          <div className="tl-inner" style={{ width: GUTTER + dur * pps }}
            onMouseDown={(e) => {
              const tgt = e.target as HTMLElement;
              if (tgt.closest(".marker") || tgt.closest(".m-accept") || tgt.closest(".afind")) return;
              const lane = (e.currentTarget as HTMLElement).querySelector(".tl-lane");
              if (!lane) return;
              const rect = lane.getBoundingClientRect();
              onSeek(Math.max(0, Math.min(dur, (e.clientX - rect.left) / pps)));
            }}>
            <Ruler dur={dur} pps={pps} />

            <SeekTrack dur={dur} pps={pps} onSeek={onSeek}>
              <MarkerTrack label="TechPrático"
                sub={(() => { const n = (q.tpAnnotations || []).length; return n ? n + (n === 1 ? " anotação" : " anotações") + " do examinador" : null; })()}
                led="#6b7689" marks={marks.tp} pps={pps} dur={dur}
                selCode={selCode} onMarker={onMarker} accept onAccept={onAccept}
                verdict={{ result: q.tp.result, pts: q.tp.pts }}
                emptyHint={(q.tpAnnotations || []).length
                  ? "Anotações do examinador sem artigo do CTB (veja abaixo)"
                  : "Sem infrações marcadas pelo examinador"} />
            </SeekTrack>

            <SeekTrack dur={dur} pps={pps} onSeek={onSeek}>
              <MarkerTrack label="ValBot" sub={null} led="var(--accent)" ledLogo marks={marks.vb} pps={pps} dur={dur}
                selCode={selCode} onMarker={onMarker} accept onAccept={onAccept}
                verdict={q.vb ? { result: q.vb.result, pts: q.vb.pts } : null}
                emptyHint={q.vb ? "IA não detectou infrações" : "Processando vídeo…"} />
            </SeekTrack>

            <SeekTrack dur={dur} pps={pps} onSeek={onSeek}>
              <MarkerTrack label="Auditor" sub="Renata Moura" led="#B45309" marks={laudo} pps={pps} dur={dur}
                selCode={selCode} onMarker={onMarker} onResize={onLaudoResize}
                verdict={laudoVerd}
                emptyHint="Lance infrações para gravar aqui o seu laudo" />
            </SeekTrack>

            {marks.interrupt && (
              <Fragment>
                <div className="interrupt-region" style={{ left: GUTTER + marks.interrupt.at * pps, width: (dur - marks.interrupt.at) * pps }}>
                  <span className="ir-l">Exame interrompido</span>
                </div>
                <div className="tl-interrupt" style={{ left: GUTTER + marks.interrupt.at * pps }} />
              </Fragment>
            )}

            <div className="tl-playhead" style={{ left: GUTTER + pos * pps }}>
              <span className="tl-playhead-tc mono">{fmtDur(Math.round(pos))}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Timeline;
