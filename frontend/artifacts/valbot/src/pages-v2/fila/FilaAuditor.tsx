/* ============================================================================
   Painel do Auditor — core / shell (porte de painel-core.jsx)
   Tela IMERSIVA da Fila do Auditor: viewer + timeline + inspetor + tour.
   Componente raiz exportado: FilaAuditor.
   ============================================================================ */
import { useState, useEffect, useRef, Fragment } from "react";
import type { CSSProperties, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { VB, gravColor, fmtDur } from "@/system/painel-data";
import type { ExamItem, MarkRef, Grav } from "@/system/painel-data";
import { I } from "./painelIcons";
import { VBP } from "./PainelModel";
import type { ClipMarks } from "./PainelModel";
import { Timeline } from "./PainelTimeline";
import { Inspector } from "./PainelInspector";
import { loadState, saveState } from "./painelState";
import {
  fetchQueue, loadRubrica, fetchExamDetail, postParecerAuditor, savePendingParecer,
  type ExamDetail,
} from "@/system/painel-api";
import "@/system/painel.css";

const EMPTY_MARKS: ClipMarks = { tp: [], vb: [], onlyTp: [], onlyVb: [], divRegions: [], processing: false, audio: [], interrupt: null };

const DIRS = [
  { k: "grafite", label: "Grafite" },
  { k: "cobalto", label: "Cobalto" },
  { k: "claro", label: "Claro" },
];

interface Tele { views: number; secs: number; watchedTo: number; full: boolean }
type TeleMap = Record<string, Tele>;
const emptyTele = (): Tele => ({ views: 0, secs: 0, watchedTo: 0, full: false });

function frameScene(seed: string, t: number): string {
  const h = VBP.hashCode(String(seed));
  const ph = (h % 100) / 100 * 6.283;
  const hue = Math.round(206 + 26 * Math.sin(t / 13 + ph));
  const skyL = Math.round(46 + 8 * Math.sin(t / 8 + ph * 1.6));
  const horizon = Math.round(52 + 7 * Math.sin(t / 19 + ph));
  return `linear-gradient(180deg, hsl(${hue} 32% ${skyL}%) 0%, hsl(${hue} 26% ${skyL - 12}%) ${horizon - 10}%, hsl(28 12% 30%) ${horizon}%, hsl(28 9% 15%) 100%)`;
}

interface AnnoMark extends MarkRef { src: "tp" | "vb" | "laudo" }
function FrameAnno({ marks, pos, dur }: { marks: { tp: MarkRef[]; vb: MarkRef[]; laudo: MarkRef[] }; pos: number; dur: number }) {
  const srcLabel: Record<string, string> = { tp: "TechPrático", vb: "ValBot", laudo: "Auditor" };
  const ppsApprox = Math.max(0.4, (window.innerWidth - 132) / (dur || 1));
  const minSec = 30 / ppsApprox;
  const all: AnnoMark[] = [
    ...(marks.tp || []).map((m) => ({ ...m, src: "tp" as const })),
    ...(marks.vb || []).map((m) => ({ ...m, src: "vb" as const })),
    ...(marks.laudo || []).map((m) => ({ ...m, src: "laudo" as const })),
  ];
  const seen = new Set<string>();
  const active = all.filter((m) => {
    // notas (observações do examinador sem Art.) não viram overlay no vídeo.
    if (m.kind === "nota" || !VB.ruleByCode[m.code]) return false;
    const end = m.t + Math.max(m.len, minSec);
    if (pos < m.t - 0.3 || pos > end) return false;
    const k = m.src + m.code; if (seen.has(k)) return false; seen.add(k); return true;
  });
  if (!active.length) return null;
  return (
    <Fragment>
      {active.map((m, i) => (
        <div key={m.src + m.code} className="frame-anno" style={{ "--gc": gravColor(m.grav), inset: (12 + i * 9) + "px", zIndex: 3 + i } as CSSProperties} />
      ))}
      <div className="fa-legend">
        {active.map((m) => (
          <span key={"lg" + m.src + m.code} className="fa-badge" style={{ background: gravColor(m.grav) }}>{srcLabel[m.src]}</span>
        ))}
      </div>
      {active.map((m, i) => {
        const r = VB.ruleByCode[m.code];
        const run = r.nome + " — " + (r.desc || r.nome) + " · " + srcLabel[m.src] + (m.conf != null ? " " + Math.round(m.conf * 100) + "%" : "") + " · " + fmtDur(m.t);
        return (
          <div key={"tk" + m.src + m.code} className="anno-ticker" style={{ "--gc": gravColor(m.grav), bottom: (16 + i * 38) + "px" } as CSSProperties}>
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
    </Fragment>
  );
}

interface ViewerProps {
  q: ExamItem; marks: ClipMarks; laudo: MarkRef[]; pos: number; dur: number;
  playing: boolean; setPlaying: React.Dispatch<React.SetStateAction<boolean>>;
  overlay: string; onSeek: (t: number) => void; selCode: string | null;
  videoUrl: string | null; videoRef: React.RefObject<HTMLVideoElement | null>;
  onVideoError?: () => void;
}
function Viewer({ q, marks, laudo, pos, dur, playing, setPlaying, overlay, onSeek, selCode, videoUrl, videoRef, onVideoError }: ViewerProps) {
  const annoMarks = overlay === "tp" ? marks.tp : overlay === "laudo" ? laudo : marks.vb;
  const scrubRef = useRef<HTMLDivElement>(null);
  const scrub = (e: React.MouseEvent) => {
    const rect = scrubRef.current!.getBoundingClientRect();
    onSeek(Math.max(0, Math.min(dur, (e.clientX - rect.left) / rect.width * dur)));
  };
  const hasExam = q.examinador && q.examinador !== "—";
  const initials = hasExam ? q.examinador.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase() : "VB";
  return (
    <div className="viewer-wrap">
      <div className="viewer-bar">
        <span className="vb-renach mono">{q.renach}</span>
        <span className="vb-exam"><span className="vb-exam-av">{initials}</span>Cat {q.cat} · {hasExam ? "Exam. " + q.examinador : "exame"}</span>
      </div>

      <StatStrip divCount={(marks.onlyTp ? marks.onlyTp.length : 0) + (marks.onlyVb ? marks.onlyVb.length : 0)} laudo={laudo} q={q} />

      <div className={"viewer" + (playing ? " playing" : "")} onClick={() => setPlaying((p) => !p)}>
        {videoUrl
          ? <video ref={videoRef} src={videoUrl} className="viewer-video" playsInline preload="metadata" onTimeUpdate={(e) => onSeek((e.target as HTMLVideoElement).currentTime)} onEnded={() => setPlaying(false)} onError={onVideoError} />
          : <div className="viewer-frame" style={{ background: frameScene(q.id, pos) }} />}
        <div className="viewer-grid" />
        <div className="viewer-safe" />
        <div className="viewer-play"><svg width="24" height="24" viewBox="0 0 24 24" fill="#fff"><path d="M8 5v14l11-7z" /></svg></div>
        <FrameAnno marks={{ tp: marks.tp, vb: marks.vb, laudo }} pos={pos} dur={dur} />
        <div className="viewer-vign" />
      </div>

      <div ref={scrubRef} onMouseDown={scrub} style={{ height: 18, marginTop: 8, position: "relative", cursor: "text", display: "flex", alignItems: "center" }}>
        <div style={{ height: 4, borderRadius: 3, background: "var(--inset)", width: "100%", position: "relative" }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: (pos / dur * 100) + "%", background: "var(--accent)", borderRadius: 3 }} />
          {annoMarks.map((m, i) => <span key={i} style={{ position: "absolute", left: (m.t / dur * 100) + "%", top: -2, width: 2, height: 8, background: gravColor(m.grav) }} />)}
          <span style={{ position: "absolute", left: "calc(" + (pos / dur * 100) + "% - 6px)", top: -4, width: 12, height: 12, borderRadius: "50%", background: "#fff", boxShadow: "0 1px 4px rgba(0,0,0,.4)" }} />
        </div>
      </div>
    </div>
  );
}

interface TransportProps {
  queue: ExamItem[]; selId: string; setSel: (clip: ExamItem) => void;
  pos: number; dur: number; playing: boolean; setPlaying: React.Dispatch<React.SetStateAction<boolean>>; onSeek: (t: number) => void;
}
function Transport({ queue, selId, setSel, pos, dur, playing, setPlaying, onSeek }: TransportProps) {
  const idx = queue.findIndex((x) => x.id === selId);
  const go = (d: number) => { const n = queue[idx + d]; if (n) setSel(n); };
  return (
    <div className="transport">
      <span className="tc-read mono">{fmtDur(Math.round(pos))}<span className="sep">/</span><span className="tot">{fmtDur(dur)}</span></span>
      <div className="tp-btns">
        <button className="tp-btn" title="Clipe anterior ( [ )" onClick={() => go(-1)} disabled={idx <= 0}><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M7 5h2v14H7zM20 5v14l-9-7z" /></svg></button>
        <button className="tp-btn" title="-5s (←)" onClick={() => onSeek(Math.max(0, pos - 5))}><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M11 18V6l-8.5 6zM20 18V6l-8.5 6z" /></svg></button>
        <button className="tp-btn play" title="Reproduzir (espaço)" onClick={() => setPlaying((p) => !p)}>
          {playing ? <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
            : <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>}
        </button>
        <button className="tp-btn" title="+5s (→)" onClick={() => onSeek(Math.min(dur, pos + 5))}><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M4 6v12l8.5-6zM13 6v12l8.5-6z" /></svg></button>
        <button className="tp-btn" title="Próximo clipe ( ] )" onClick={() => go(1)} disabled={idx >= queue.length - 1}><svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M17 5h-2v14h2zM4 5v14l9-7z" /></svg></button>
      </div>
      <div className="tp-right">
        <button className="tp-nav" onClick={() => go(-1)} disabled={idx <= 0}>← Anterior</button>
        <span className="tp-meta mono">Exame {idx + 1}/{queue.length}</span>
        <button className="tp-nav" onClick={() => go(1)} disabled={idx >= queue.length - 1}>Próximo exame →</button>
      </div>
    </div>
  );
}

interface TourStep { sel?: string; act?: string; t: string; d: string; hold: number }
const TOUR: TourStep[] = [
  { t: "Tour do fluxo", d: "Vou destacar cada etapa do Painel do Auditor e os pontos de conhecimento. Avance no seu ritmo — a barra acima apenas marca o tempo de cada passo.", hold: 4200 },
  { sel: ".exam-picker", t: "Exame em auditoria", d: "Aqui você seleciona o exame da fila — o cabeçalho traz o RENACH e o resultado em análise.", hold: 4200 },
  { sel: ".viewer", act: "seekInfra", t: "Vídeo do exame", d: "Levo o playhead até uma infração: a moldura acende na cor da gravidade e a tarja corre com o enquadramento. Na 1ª revisão, o avanço libera conforme você assiste.", hold: 5400 },
  { sel: ".timeline", t: "Linha do tempo", d: "Quatro trilhas — VÍDEO, TECHPRÁTICO (examinador), VALBOT (IA) e AUDITOR (seu laudo). Onde TechPrático e ValBot não coincidem, há uma divergência a revisar.", hold: 6200 },
  { sel: ".m-accept-big", t: "Trazer a detecção da IA", d: "Este “+” lança a infração detectada pelo ValBot direto no seu laudo, no mesmo início/fim.", hold: 4800 },
  { sel: ".dm", act: "openFicha", t: "Ficha do Procedimento", d: "Ponto de conhecimento: cada infração abre sua ficha oficial do MBEDV — descrição, gravidade e peso, e as abas Condutas que pontuam, que não pontuam e Definições.", hold: 7200 },
  { sel: ".lbtn.warn", t: "Lançar infração", d: "Enquadre manualmente pela Matriz Nacional — cada lançamento tem início, fim e o artigo do CTB.", hold: 5000 },
  { sel: ".laudo", t: "Seu laudo", d: "As infrações confirmadas somam pontos e definem o veredito sugerido. A sua análise é o laudo final.", hold: 5400 },
  { sel: ".ia-row", t: "Decisão", d: "Aprovar ou Reprovar pede confirmação e valida a coerência com o laudo antes de registrar e avançar.", hold: 5000 },
  { sel: ".pchrome-right", t: "Supervisão", d: "No topo, o Painel do Supervisor acompanha acessos, tempo de vídeo e a qualidade de cada auditoria.", hold: 5000 },
];

interface TourApi { seekInfra: () => void; openFicha: () => void; closeFicha: () => void }
function TourOverlay({ onClose, api }: { onClose: () => void; api: TourApi }) {
  const [i, setI] = useState(0);
  const [box, setBox] = useState<DOMRect | null>(null);
  const s = TOUR[i];
  const last = i === TOUR.length - 1;
  useEffect(() => {
    if (api) {
      if (s.act === "seekInfra") api.seekInfra();
      if (s.act === "openFicha") api.openFicha(); else api.closeFicha();
    }
    let raf = 0, n = 0;
    const upd = () => { const el = s.sel ? document.querySelector(s.sel) : null; setBox(el ? el.getBoundingClientRect() : null); if (n++ < 24) raf = requestAnimationFrame(upd); };
    const t = setTimeout(upd, 90);
    return () => { clearTimeout(t); cancelAnimationFrame(raf); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i]);
  useEffect(() => () => { if (api) api.closeFicha(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  let cardStyle: CSSProperties = { left: "50%", top: "50%", transform: "translate(-50%,-50%)" };
  let cur: { x: number; y: number } | null = null;
  if (box) {
    const cw = 348, ch = 268, gap = 20, W = window.innerWidth, H = window.innerHeight;
    const cl = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
    if (H - box.bottom > ch + gap) cardStyle = { top: box.bottom + gap, left: cl(box.left, 16, W - cw - 16) };
    else if (box.top > ch + gap) cardStyle = { top: box.top - ch - gap, left: cl(box.left, 16, W - cw - 16) };
    else if (W - box.right > cw + gap) cardStyle = { left: box.right + gap, top: cl(box.top, 16, H - ch - 16) };
    else if (box.left > cw + gap) cardStyle = { left: box.left - cw - gap, top: cl(box.top, 16, H - ch - 16) };
    else cardStyle = { left: cl(box.left, 16, W - cw - 16), top: 16 };
    cur = { x: cl(box.left + box.width / 2, 12, W - 12), y: cl(box.top + box.height / 2, 12, H - 12) };
  }
  return (
    <div className="tour-scrim2">
      {box && <div className="tour-spot" style={{ left: box.left - 6, top: box.top - 6, width: box.width + 12, height: box.height + 12 }} />}
      {cur && <div className={"tour-cursor" + (s.act ? " act" : "")} style={{ left: cur.x, top: cur.y }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="#fff" stroke="rgba(0,0,0,.5)" strokeWidth="1.2"><path d="M5 3l15 9-6.5 1.5L10 20z" /></svg>
      </div>}
      <div className="tour-card" style={cardStyle}>
        <div className="tour-progress"><span key={i} style={{ animationDuration: (s.hold || 4800) + "ms" }} /></div>
        <div className="tour-step">Etapa {i + 1} / {TOUR.length}</div>
        <div className="tour-title">{s.t}</div>
        <div className="tour-desc">{s.d}</div>
        <div className="tour-dots">{TOUR.map((_, k) => <span key={k} className={"tour-dot" + (k === i ? " on" : "") + (k < i ? " done" : "")} />)}</div>
        <div className="tour-actions">
          <button className="tour-skip" onClick={onClose}>Pular</button>
          {i > 0 && <button className="tour-skip" onClick={() => setI(i - 1)}>Voltar</button>}
          <button className="tour-go" onClick={() => last ? onClose() : setI(i + 1)}>{last ? "Concluir" : "Avançar"}</button>
        </div>
      </div>
    </div>
  );
}

function SupervisorModal({ tele, queue, onClose }: { tele: TeleMap; queue: ExamItem[]; onClose: () => void }) {
  return (
    <div className="dm-scrim" onClick={onClose}>
      <div className="sup" onClick={(e) => e.stopPropagation()}>
        <div className="dm-head"><span style={{ fontWeight: 700, fontSize: 15 }}>Painel do Supervisor</span><span style={{ fontSize: 11, color: "var(--faint)", marginLeft: 6 }}>controle de qualidade da auditoria</span><button className="dm-x" style={{ marginLeft: "auto" }} onClick={onClose}><I.close /></button></div>
        <div className="sup-body">
          <table className="sup-table">
            <thead><tr><th>Exame (RENACH)</th><th>Acessos</th><th>Tempo no vídeo</th><th>Assistido</th><th>Veredito</th></tr></thead>
            <tbody>
              {queue.map((q) => {
                const c = tele[q.id] || emptyTele();
                const ver = q.final ? q.final.result : (q.status === "interrompido" ? "interrompido" : q.vb ? q.vb.result : null);
                return (
                  <tr key={q.id}>
                    <td className="mono">{q.renach}</td>
                    <td className="mono">{c.views}</td>
                    <td className="mono">{fmtDur(c.secs)}</td>
                    <td>{c.full ? <span className="sup-ok">Integral</span> : <span className="sup-part">{fmtDur(Math.round(c.watchedTo))} / {fmtDur(q.dur)}</span>}</td>
                    <td style={{ color: ver === "aprovado" ? "var(--ok)" : ver === "reprovado" ? "var(--bad)" : ver === "interrompido" ? "var(--warn)" : "var(--faint)" }}>{ver === "aprovado" ? "Aprovado" : ver === "reprovado" ? "Reprovado" : ver === "interrompido" ? "Interrompido" : "Pendente"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="sup-note">O avanço do vídeo só é liberado após o auditor assistir integralmente na 1ª revisão. Acessos e tempo no vídeo são registrados por exame.</div>
        </div>
      </div>
    </div>
  );
}

function DetailModal({ m, q, onClose }: { m: MarkRef; q: ExamItem; onClose: () => void }) {
  const [view, setView] = useState(0);
  const [tab, setTab] = useState(0);
  const r = VB.ruleByCode[m.code] || { code: m.code, nome: "Infração " + m.code, desc: "Detalhe não disponível para este código.", grav: m.grav, pontos: VB.meta.grav[m.grav] ? VB.meta.grav[m.grav].pontos : 0, enquad: { ctb: m.code, mbedv: "—", art: "" } };
  const grav = VB.meta.grav[m.grav] || VB.meta.grav[r.grav] || { label: "—", color: "var(--faint)", bg: "transparent", ring: "transparent", pontos: 0 };
  const fromVb = !!(q.vb && q.vb.faults.includes(m.code));
  const fromTp = q.tp.faults.includes(m.code);
  const fontes = [fromTp && "TechPrático", fromVb && ("ValBot · " + Math.round(q.vb!.conf! * 100) + "% confiança")].filter(Boolean);
  // anotação específica do examinador para este código (training_annotations)
  const tpAnno = (q.tpAnnotations || []).find((a) => a.code === m.code);
  const tpText = tpAnno ? tpAnno.text : (q.tpComment || "Examinador registrou esta infração na avaliação presencial.");
  return (
    <div className="dm-scrim" onClick={onClose}>
      <div className="dm" onClick={(e) => e.stopPropagation()} style={{ "--gc": gravColor(m.grav) } as CSSProperties}>
        <div className="dm-head">
          <span className="dm-code mono">{r.enquad.ctb}</span>
          <span className="dm-grav" style={{ color: grav.color, background: grav.bg }}>{grav.label} · peso {r.pontos}</span>
          <button className="dm-x" onClick={onClose}><I.close /></button>
        </div>
        <div className="dm-toptabs">
          <button className={"dm-toptab" + (view === 0 ? " on" : "")} onClick={() => setView(0)}>Comentários</button>
          <button className={"dm-toptab" + (view === 1 ? " on" : "")} onClick={() => setView(1)}>Ficha do procedimento</button>
        </div>
        <div className="dm-body">
          {view === 0 ? (
            <Fragment>
              <div className="dm-title">{r.enquad.ctb} — {r.nome}</div>
              {fromTp && (
                <div className="cmt">
                  <div className="cmt-h"><span className="cmt-av tp">TP</span>TechPrático · examinador<span className="cmt-meta mono">{fmtDur(tpAnno ? tpAnno.t : m.t)}</span></div>
                  <p className="dm-text" style={{ whiteSpace: "pre-wrap" }}>{tpText}</p>
                </div>
              )}
              {fromVb && (
                <div className="cmt">
                  <div className="cmt-h"><span className="cmt-av vb">IA</span>ValBot · análise Gemini<span className="cmt-meta mono">{Math.round(q.vb!.conf! * 100)}% · {fmtDur(m.t)}</span></div>
                  <p className="dm-text">{r.constatacao || r.desc}</p>
                </div>
              )}
              {!fromTp && !fromVb && <p className="dm-text" style={{ color: "var(--faint)" }}>Infração enquadrada manualmente pelo auditor neste laudo · {fmtDur(m.t)}.</p>}
              {fromTp && fromVb && <div className="cmt-flag ok"><I.check width="13" height="13" />TechPrático e ValBot convergem nesta infração.</div>}
              {q.vb && (fromTp !== fromVb) && <div className="cmt-flag div"><span className="db-dot" />Divergência — apontada apenas por {fromTp ? "TechPrático" : "ValBot"}.</div>}
            </Fragment>
          ) : (
            <Fragment>
              <div className="fic-row"><span className="fic-k">Infração</span><div className="fic-v"><b className="mono">{r.enquad.ctb}</b> — {r.nome}</div></div>
              {r.categorias && <div className="fic-row"><span className="fic-k">Categorias</span><div className="fic-v">{r.categorias}</div></div>}
              <div className="fic-row"><span className="fic-k">Descrição</span><div className="fic-v">{r.desc}</div></div>
              <div className="fic-row"><span className="fic-k">Gravidade · Peso</span><div className="fic-v">{grav.label} · {r.pontos} ponto{(r.pontos || 0) > 1 ? "s" : ""}</div></div>
              {r.constatacao && <Fragment><div className="dm-sec">Constatação da infração</div><p className="dm-text">{r.constatacao}</p></Fragment>}
              <div className="dm-tabs">
                {["Condutas que pontuam", "Condutas que não pontuam", "Definições e procedimentos"].map((t, k) => (
                  <button key={k} className={"dm-tab" + (tab === k ? " on" : "")} onClick={() => setTab(k)}>{t}</button>
                ))}
              </div>
              <p className="dm-text dm-tabbody">{[r.pontua, r.naoPontua, r.definicoes][tab] || r.checks || "—"}</p>
              {r.compl && <Fragment><div className="dm-sec">Informações complementares</div><p className="dm-text">{r.compl}</p></Fragment>}
              <div className="dm-sec">Auditoria deste exame</div>
              <div className="dm-grid">
                <div className="dm-cell"><span>Detectado por</span><b>{fontes.length ? fontes.join(" · ") : "Laudo do auditor"}</b></div>
                <div className="dm-cell"><span>Ocorrência</span><b className="mono">{fmtDur(m.t)} – {fmtDur(m.t + m.len)}</b></div>
              </div>
            </Fragment>
          )}
        </div>
      </div>
    </div>
  );
}

interface HowtoStep { n: number; c: string; t: string; d: string; ic: ReactNode }
const HOWTO: HowtoStep[] = [
  { n: 1, c: "#5B8DEF", t: "Aponte o momento", d: "Clique na linha do tempo no instante exato da falha ou use os marcadores do ValBot.", ic: <path d="M12 2v4M12 18v4M2 12h4M18 12h4M12 8a4 4 0 100 8 4 4 0 000-8z" /> },
  { n: 2, c: "#F08A2C", t: "Lance a infração", d: "Marque o início e o fim da ocorrência, escolha o enquadramento e confirme a gravidade.", ic: <path d="M12 5v14M5 12h14" /> },
  { n: 3, c: "#1FA968", t: "Finalize o laudo", d: "Revise as infrações e aprove ou reprove para concluir o exame.", ic: <path d="M20 6L9 17l-5-5" /> },
];
function HowItWorks() {
  const [open, setOpen] = useState(() => loadState().howtoOpen !== false);
  const toggle = () => { setOpen((o) => { saveState({ howtoOpen: !o }); return !o; }); };
  return (
    <div className={"howto" + (open ? "" : " howto-collapsed")}>
      <button className="howto-head" onClick={toggle} aria-expanded={open}>
        <svg className="howto-chev" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
        Como lançar uma infração
        <span className="howto-hide">{open ? "Ocultar" : "Mostrar"}</span>
      </button>
      {open && (
        <div className="howto-grid">
          {HOWTO.map((s) => (
            <div className="howto-card" key={s.n}>
              <span className="howto-ic" style={{ background: s.c }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{s.ic}</svg>
              </span>
              <div className="howto-body">
                <div className="howto-t"><span className="howto-n mono">{s.n}</span>{s.t}</div>
                <div className="howto-d">{s.d}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatStrip({ divCount, laudo, q }: { divCount: number; laudo: MarkRef[]; q: ExamItem }) {
  const statusMap: Record<string, { t: string; c: string }> = {
    divergencia: { t: "Em análise", c: "var(--proc)" },
    processando: { t: "Processando", c: "var(--warn)" },
    interrompido: { t: "Interrompido", c: "var(--bad)" },
    finalizado: { t: "Finalizado", c: "var(--ok)" },
  };
  const st = statusMap[q.status] || { t: "Em análise", c: "var(--proc)" };
  const conf = q.vb ? Math.round(q.vb.conf! * 100) : null;
  const confLbl = conf == null ? "—" : conf >= 85 ? "Alta" : conf >= 65 ? "Média" : "Baixa";
  const confColor = conf == null ? "var(--muted)" : conf >= 85 ? "var(--ok)" : conf >= 65 ? "var(--warn)" : "var(--bad)";
  const items = [
    { label: "Divergências", value: divCount, unit: "encontradas", color: divCount > 0 ? "var(--bad)" : "var(--ok)", info: false, ic: <Fragment><rect x="4" y="3" width="14" height="18" rx="2" /><path d="M11 8v5M11 16h.01" /></Fragment> },
    { label: "Infrações", value: laudo.length, unit: "registradas", color: laudo.length > 0 ? "var(--warn)" : "var(--muted)", info: false, ic: <Fragment><rect x="4" y="3" width="14" height="18" rx="2" /><path d="M8 9h6M8 13h4" /></Fragment> },
    { label: "Status", value: st.t, unit: null, color: st.c, info: false, ic: <Fragment><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Fragment> },
    { label: "Confiança ValBot", value: conf == null ? "—" : confLbl + " " + conf + "%", unit: null, color: confColor, info: true, ic: <Fragment><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 014.7 1.2c0 1.7-2.2 1.9-2.2 3.3M12 17h.01" /></Fragment> },
  ];
  return (
    <div className="statstrip">
      {items.map((it, i) => (
        <div className="ss-cell" key={i}>
          <span className="ss-ic"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{it.ic}</svg></span>
          <div className="ss-body">
            <div className="ss-label">{it.label}</div>
            <div className="ss-value"><b style={{ color: it.color }}>{it.value}</b>{it.unit ? <span className="ss-unit"> {it.unit}</span> : null}</div>
          </div>
          {it.info ? <span className="ss-info" title="Grau de certeza da análise de visão computacional do ValBot."><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" strokeLinecap="round" /></svg></span> : null}
        </div>
      ))}
    </div>
  );
}

export default function FilaAuditor() {
  const init = loadState();
  const [dir, setDir] = useState(init.dir && DIRS.some((d) => d.k === init.dir) ? init.dir! : "grafite");

  // ---- FILA REAL: GET /api/videos?only_unresolved=true (carrega a rubrica antes) ----
  const { data: queue = [], isLoading: queueLoading, isError: queueError, refetch: refetchQueue } =
    useQuery<ExamItem[]>({
      queryKey: ["fila-auditor", "queue"],
      queryFn: async () => { await loadRubrica(); return fetchQueue(); },
      staleTime: 60_000,
    });

  const [selId, setSelId] = useState<string | null>(null);
  const [pos, setPos] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [overlay, setOverlay] = useState("vb");
  const [selCode, setSelCode] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [detail, setDetail] = useState<MarkRef | null>(null);
  const [tele, setTele] = useState<TeleMap>(() => loadState().tele || {});
  const [supOpen, setSupOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(true);
  const bumpTele = (id: string, fn: (c: Tele) => Tele) => setTele((t) => { const c = t[id] || emptyTele(); return { ...t, [id]: fn(c) }; });
  const [laudoMap, setLaudoMap] = useState<Record<string, MarkRef[]>>({});
  const [toast, setToast] = useState<string | null>(null);

  // ---- DETALHE LAZY do exame selecionado: vídeo + infrações da IA (timeline) ----
  // Token por requisição: descarta resolução de fetch antiga ao trocar de exame (race).
  const selReqRef = useRef(0);
  const [detailMap, setDetailMap] = useState<Record<string, ExamDetail>>({});
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailErr, setDetailErr] = useState<string | null>(null);

  // seleção default quando a fila chega (1º divergente, senão 1º).
  useEffect(() => {
    if (selId || !queue.length) return;
    const div = queue.find((x) => x.status === "divergencia");
    const first = (init.selId && queue.some((x) => x.id === init.selId) ? init.selId : (div ? div.id : queue[0].id)) as string;
    setSelId(first);
  }, [queue]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadDetail = (item: ExamItem, token: number) => {
    if (detailMap[item.id]) return; // cache por exame
    setDetailLoading(true); setDetailErr(null);
    fetchExamDetail(item)
      .then((d) => { if (token !== selReqRef.current) return; setDetailMap((m) => ({ ...m, [item.id]: d })); const first = d.marks.vb[0]; if (first) setSelCode(first.code); })
      .catch((e: Error) => { if (token !== selReqRef.current) return; setDetailErr("Não foi possível carregar o exame/vídeo. " + e.message); })
      .finally(() => { if (token === selReqRef.current) setDetailLoading(false); });
  };
  // dispara o fetch do detalhe quando muda a seleção / chega a fila.
  useEffect(() => {
    if (!selId) return;
    const item = queue.find((x) => x.id === selId);
    if (!item) return;
    const token = ++selReqRef.current;
    if (detailMap[selId]) { setDetailLoading(false); setDetailErr(null); }
    else loadDetail(item, token);
  }, [selId, queue]); // eslint-disable-line react-hooks/exhaustive-deps

  // exame "ativo": item da fila enriquecido pelo detalhe quando disponível.
  const baseItem = (selId && queue.find((x) => x.id === selId)) || null;
  const detailCur: ExamDetail | null = (selId && detailMap[selId]) || null;
  const q: ExamItem | null = detailCur ? detailCur.q : baseItem;
  const marks: ClipMarks = detailCur ? detailCur.marks : EMPTY_MARKS;
  const dur = q ? q.dur : 0;
  const videoUrl = detailCur ? detailCur.videoUrl : null;

  const laudo = (selId && laudoMap[selId]) || [];
  const setLaudo = (updater: MarkRef[] | ((l: MarkRef[]) => MarkRef[])) => {
    if (!selId) return;
    setLaudoMap((m) => ({ ...m, [selId]: typeof updater === "function" ? (updater as (l: MarkRef[]) => MarkRef[])(m[selId] || []) : updater }));
  };
  const divCount = marks.onlyTp.length + marks.onlyVb.length;

  const toastRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flash = (msg: string) => { setToast(msg); if (toastRef.current) clearTimeout(toastRef.current); toastRef.current = setTimeout(() => setToast(null), 1900); };

  useEffect(() => { document.documentElement.setAttribute("data-dir", dir); saveState({ dir }); return () => { document.documentElement.removeAttribute("data-dir"); }; }, [dir]);
  // Fila imersiva = fullscreen sem scroll. Trava o body só enquanto montada
  // (restaura no unmount pra não vazar pras outras telas, que precisam rolar).
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);
  useEffect(() => { if (selId) saveState({ selId, pos: Math.round(pos) }); }, [selId, pos]);
  useEffect(() => { if (overlay === "vb" && q && !q.vb) setOverlay("tp"); }, [selId, q]); // eslint-disable-line react-hooks/exhaustive-deps

  // play loop (relógio simulado) — só quando NÃO há vídeo real (fallback).
  useEffect(() => {
    if (!playing || videoUrl || !q) return;
    const iv = setInterval(() => setPos((p) => { const n = p + 0.1; if (n >= q.dur) { setPlaying(false); return q.dur; } return n; }), 100);
    return () => clearInterval(iv);
  }, [playing, selId, videoUrl, q]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const v = videoRef.current; if (!v || !videoUrl) return; if (playing) v.play().catch(() => {}); else v.pause(); }, [playing, videoUrl, selId]);
  useEffect(() => { const v = videoRef.current; if (!v || !videoUrl) return; if (Math.abs(v.currentTime - pos) > 0.4) v.currentTime = pos; }, [pos, videoUrl]);
  // telemetria
  useEffect(() => { if (selId) bumpTele(selId, (c) => ({ ...c, views: c.views + 1 })); }, [selId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!selId) return; const iv = setInterval(() => bumpTele(selId, (c) => ({ ...c, secs: c.secs + 1 })), 1000); return () => clearInterval(iv); }, [selId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (selId && q) bumpTele(selId, (c) => pos <= c.watchedTo ? c : ({ ...c, watchedTo: pos, full: c.full || pos >= q.dur - 1.5 })); }, [pos, selId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { saveState({ tele }); }, [tele]);

  const selectClip = (clip: ExamItem) => {
    const c = tele[clip.id];
    const d = detailMap[clip.id];
    const def = d ? (d.marks.onlyVb[0] || d.marks.vb[0] || null) : null;
    setSelId(clip.id); setPlaying(false);
    setSelCode(def ? def.code : null);
    setPos((c && c.full && def) ? def.t : 0);
  };
  const retryDetail = () => { const it = selId ? queue.find((x) => x.id === selId) : null; if (it) { const token = ++selReqRef.current; setDetailErr(null); loadDetail(it, token); } };
  const onVideoError = () => { if (!videoUrl || detailErr) return; setPlaying(false); setDetailErr("Não foi possível carregar o vídeo deste exame (arquivo indisponível ou expirado)."); };

  const guardedSeek = (t: number) => { const c = tele[selId || ""]; if (c && !c.full && t > c.watchedTo + 2) { flash("1ª revisão — o avanço libera conforme você assiste ao vídeo"); setPos(Math.min(t, c.watchedTo)); return; } setPos(t); };

  const seekToMark = (m: MarkRef) => { const c = tele[selId || ""]; const blocked = c && !c.full && m.t > c.watchedTo + 2; if (!blocked) { setPos(m.t); const v = videoRef.current; if (v && videoUrl) { try { v.currentTime = m.t; } catch { /* noop */ } } } else { flash("1ª revisão — assista até o ponto antes de pular para a infração"); } setSelCode(m.code); if (m.code) setDetail(m); };
  const resizeLaudo = (code: string, t: number, len: number) => setLaudo((l) => l.map((x) => x.code === code ? { ...x, t: Math.round(t), len: Math.max(1, Math.round(len)) } : x));
  const acceptMark = (m: MarkRef) => {
    setLaudo((l) => l.some((x) => x.code === m.code) ? l : [...l, { code: m.code, t: m.t, len: m.len, grav: m.grav }].sort((a, b) => a.t - b.t));
    setSelCode(m.code);
    flash("Infração " + m.code + " adicionada ao laudo");
  };

  const advanceNext = () => {
    const i = queue.findIndex((x) => x.id === selId);
    const next = queue[i + 1];
    if (next) { selectClip(next); flash("Laudo registrado — novo exame: " + next.renach); }
    else { flash("Laudo registrado — fila concluída"); }
  };

  // DECISÃO REAL: POST /api/exams/{hash}/parecer-auditor. Em falha de rede, grava
  // o parecer localmente (não perde) e avança mesmo assim.
  const resolve = async (result: string, faults: MarkRef[], note: string) => {
    if (!q) return;
    const hash = q.dbId;
    const r = result as "aprovado" | "reprovado";
    const vbResult = q.vb ? q.vb.result : null;
    const decisao: "concorda" | "discorda" = vbResult == null || vbResult === r ? "concorda" : "discorda";
    const payload = {
      decisao, resultado_final: r,
      infracoes: faults.map((f) => ({ code: f.code, t: f.t, len: f.len, grav: f.grav })),
      justificativa: note || "", referencia_mbedv: null as string | null,
    };
    // marca o exame como finalizado localmente (some da fila divergente ao refetch).
    q.status = "finalizado"; q.revisor = "Renata Moura";
    q.final = { result: r, faults: faults.map((f) => f.code), note };
    try {
      const res = await postParecerAuditor(hash, payload);
      if (res.persisted) flash("Laudo " + (r === "aprovado" ? "aprovado" : "reprovado") + " e registrado");
      else { savePendingParecer(hash, payload); flash("Salvo localmente — sincroniza depois"); }
    } catch {
      savePendingParecer(hash, payload);
      flash("Sem conexão — salvo localmente, sincroniza depois");
    }
  };
  const launchDivergence = () => { if (q) { q.status = "divergencia"; } flash("Divergência lançada para revisão da Comissão Examinadora"); };

  // teclado
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const tgt = e.target as HTMLElement;
      if (tgt.tagName === "INPUT" || tgt.tagName === "TEXTAREA") return;
      if (e.code === "Space") { e.preventDefault(); setPlaying((p) => !p); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); setPos((p) => Math.max(0, p - 1)); }
      else if (e.key === "ArrowRight") { e.preventDefault(); setPos((p) => q ? Math.min(q.dur, p + 1) : p); }
      else if (e.key === "[" || e.key === "]") { const i = queue.findIndex((x) => x.id === selId); const n = queue[i + (e.key === "]" ? 1 : -1)]; if (n) selectClip(n); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [selId, queue, q]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="painel">
      <div className="pchrome">
        <div className="pbrand">
          <div className="pbrand-mark">
            <img src="/logo.png" alt="ValBot" width="36" height="36" />
          </div>
          <div><div className="pbrand-name">Val<b>Bot</b></div></div>
        </div>
        <span className="pchrome-sub">Painel do Auditor</span>
        <span className="pchrome-spacer" style={{ marginLeft: "auto" }} />

        <div className="pchrome-right">
          <div className="dirseg">
            {DIRS.map((d) => <button key={d.k} className={dir === d.k ? "on" : ""} onClick={() => setDir(d.k)}>{d.label}</button>)}
          </div>
          <button className="pchrome-btn" onClick={() => setSupOpen(true)} title="Painel do Supervisor"><I.user width="15" height="15" />Supervisor</button>
          <a href="Dashboard.html" className="pchrome-btn"><I.dash width="15" height="15" />Dashboard</a>
        </div>
      </div>

      {queueLoading && <div style={{ padding: 60, textAlign: "center", color: "var(--faint)" }}>Carregando exames…</div>}
      {!queueLoading && queueError && (
        <div style={{ padding: 60, textAlign: "center" }}>
          <div style={{ color: "var(--bad)", fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Falha ao carregar a fila de exames.</div>
          <button className="lbtn warn" onClick={() => refetchQueue()}>Tentar de novo</button>
        </div>
      )}
      {!queueLoading && !queueError && !queue.length && <div style={{ padding: 60, textAlign: "center", color: "var(--faint)" }}>Nenhum exame divergente.</div>}

      {!queueLoading && !queueError && q && (
        <Fragment>
          <div className="pwork">
            <div className="pcenter">
              {detailErr ? (
                <div className="viewer-wrap"><div className="viewer" style={{ display: "grid", placeItems: "center", gap: 14, padding: 24, textAlign: "center" }}>
                  <div style={{ color: "var(--bad)", fontSize: 14, fontWeight: 600, maxWidth: 420 }}>{detailErr}</div>
                  <button className="lbtn warn" onClick={retryDetail} disabled={detailLoading}>{detailLoading ? "Tentando…" : "Tentar de novo"}</button>
                </div></div>
              ) : detailLoading && !detailCur ? (
                <div className="viewer-wrap"><div className="viewer" style={{ display: "grid", placeItems: "center", color: "var(--faint)" }}>Carregando vídeo e análise…</div></div>
              ) : (
                <Viewer q={q} marks={marks} laudo={laudo} pos={pos} dur={dur} playing={playing} setPlaying={setPlaying} overlay={overlay} onSeek={guardedSeek} selCode={selCode} videoUrl={videoUrl} videoRef={videoRef} onVideoError={onVideoError} />
              )}
              <Transport queue={queue} selId={selId || ""} setSel={selectClip} pos={pos} dur={dur} playing={playing} setPlaying={setPlaying} onSeek={guardedSeek} />
            </div>
            <Inspector q={q} marks={marks} laudo={laudo} setLaudo={setLaudo} pos={pos} selCode={selCode} onSelectMark={seekToMark} onResolve={resolve} onDivergence={launchDivergence} onAfterResolve={advanceNext} onPause={() => setPlaying(false)} />
          </div>
          {detail && <DetailModal m={detail} q={q} onClose={() => setDetail(null)} />}
          {supOpen && <SupervisorModal tele={tele} queue={queue} onClose={() => setSupOpen(false)} />}
          {tourOpen && <TourOverlay onClose={() => setTourOpen(false)} api={{
            seekInfra: () => { const mk = (marks.vb || [])[0] || (marks.tp || [])[0]; if (mk) { setPos(mk.t); setSelCode(mk.code); } },
            openFicha: () => { const mk = (marks.vb || [])[0] || (marks.tp || [])[0]; if (mk) { setSelCode(mk.code); setDetail(mk); } },
            closeFicha: () => setDetail(null),
          }} />}

          <HowItWorks />

          <Timeline q={q} marks={marks} laudo={laudo} pos={pos} dur={dur} onSeek={guardedSeek} selCode={selCode} onMarker={seekToMark} onAccept={acceptMark} onLaudoResize={resizeLaudo} divCount={divCount} />
        </Fragment>
      )}

      {toast && <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 80, background: "var(--elev)", color: "var(--text)", border: "1px solid var(--line)", padding: "10px 18px", borderRadius: 9, fontSize: 13, fontWeight: 600, boxShadow: "0 12px 36px rgba(0,0,0,.4)" }}>{toast}</div>}
    </div>
  );
}
