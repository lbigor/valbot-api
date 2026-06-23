/* ============================================================================
   Painel — Inspetor de Auditoria (porte de painel-inspector.jsx)
   Pilares: Evidências · Detecção · Normativo · Pontuação · Comparação
   ============================================================================ */
import { useState, useEffect, Fragment } from "react";
import type { ReactNode, CSSProperties } from "react";
import { VB, gravColor, fmtDur } from "@/system/painel-data";
import type { MarkRef, ExamItem, Rule, Grav } from "@/system/painel-data";
import { I } from "./painelIcons";
import type { ClipMarks } from "./PainelModel";
// CSS completo do picker "Lançar infração" (classes pk- e pkf-). O porte para
// pages-v2 trouxe só um subconjunto antigo dessas classes para system/painel.css,
// então o modal renderizava SEM layout (chips grudados, itens sem card). Importar
// aqui o conjunto completo (63 seletores) garante o picker estilizado.
import "@/components/painel/FaultPicker.css";

function gravTokens(g: Grav) {
  return { color: gravColor(g), bg: "color-mix(in oklab," + gravColor(g) + ", transparent 84%)" };
}
function effVerdictP(q: ExamItem): string {
  if (q.final) return q.final.result;
  if (q.status === "processando") return "processando";
  if (q.status === "interrompido") return "interrompido";
  if (q.status === "divergencia") return "divergencia";
  return q.tp.result;
}
function ptsOf(faults: string[] | null): { pts: number; label: string; grav: boolean } {
  if (!faults) return { pts: 0, label: "—", grav: false };
  const pts = faults.reduce((s, c) => s + (VB.ruleByCode[c]?.pontos || 0), 0);
  const grav = faults.some((c) => VB.ruleByCode[c]?.grav === "gravissima");
  return { pts, grav, label: pts + (pts === 1 ? " pt" : " pts") };
}

/* ---- Comparação (Resultado · Pontuação · Infrações) ---- */
function Comparison({ q }: { q: ExamItem }) {
  const tpS = ptsOf(q.tp.faults);
  const vbS = q.vb ? ptsOf(q.vb.faults) : null;
  const rows = [
    { k: "Resultado", tp: q.tp.result === "aprovado" ? "Aprovado" : "Reprovado", vb: q.vb ? (q.vb.result === "aprovado" ? "Aprovado" : "Reprovado") : "—", div: !!q.vb && q.tp.result !== q.vb.result, tone: true },
    { k: "Pontuação", tp: tpS.label, vb: vbS ? vbS.label : "—", div: !!vbS && tpS.label !== vbS.label },
    { k: "Infrações", tp: String(q.tp.faults.length), vb: q.vb ? String(q.vb.faults.length) : "—", div: !!q.vb && q.tp.faults.length !== q.vb.faults.length },
  ];
  const tone = (txt: string) => (txt === "Aprovado" ? "var(--ok)" : txt === "Reprovado" ? "var(--bad)" : "var(--text-2)");
  return (
    <div className="cmp">
      <div className="cmp-head">
        <span className="cmp-pillar">Comparação</span>
        <span className="cmp-c"><span className="cmp-who tp">TechPrático</span></span>
        <span className="cmp-c"><span className="cmp-who vb">ValBot</span></span>
      </div>
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

/* ---- linha de infração do laudo final (completa) ---- */
interface FaultRowProps {
  m: MarkRef; onClick: (m: MarkRef) => void; onRemove?: (m: MarkRef) => void;
  onSetStart?: (m: MarkRef) => void; onSetEnd?: (m: MarkRef) => void;
  onNudge?: (m: MarkRef, edge: "start" | "end", d: number) => void;
}
function FaultRow({ m, onClick, onRemove, onSetStart, onSetEnd, onNudge }: FaultRowProps) {
  const r = VB.ruleByCode[m.code];
  const tk = gravTokens(m.grav);
  const ptsLbl = r.pontos == null ? "Elim." : r.pontos + (r.pontos === 1 ? " pt" : " pts");
  return (
    <div className="fault-row">
      <button className="fr-main" onClick={() => onClick(m)} title={r.desc}>
        <span className="fc-code mono" style={{ color: tk.color, background: tk.bg }}>{r.enquad.ctb}</span>
        <span className="fr-name">{r.nome}</span>
        <span className="fr-pts mono" style={{ color: tk.color }}>{ptsLbl}</span>
        {onRemove && <span className="fr-x" onClick={(e) => { e.stopPropagation(); onRemove(m); }}><I.close width="13" height="13" /></span>}
      </button>
      <div className="fr-obs">{r.desc}</div>
      <div className="fr-meta">
        <span className="fr-occ">Início</span>
        <span className="fr-stepper">
          {onNudge && <button className="fr-step" onClick={() => onNudge(m, "start", -1)} title="Recuar o início 1s">−</button>}
          <button className="fr-ev mono" onClick={() => onClick(m)} title="Ir para o início da infração"><I.video width="11" height="11" />{fmtDur(m.t)}</button>
          {onNudge && <button className="fr-step" onClick={() => onNudge(m, "start", 1)} title="Avançar o início 1s">+</button>}
        </span>
        {onSetStart && <button className="fr-settime" onClick={() => onSetStart(m)} title="Definir início no tempo atual do vídeo">marcar</button>}
        <span className="fr-occ" style={{ marginLeft: 4 }}>Fim</span>
        <span className="fr-stepper">
          {onNudge && <button className="fr-step" onClick={() => onNudge(m, "end", -1)} title="Recuar o fim 1s">−</button>}
          <button className="fr-ev mono" onClick={() => onClick({ ...m, t: m.t + m.len })} title="Ir para o fim da infração">{fmtDur(m.t + m.len)}</button>
          {onNudge && <button className="fr-step" onClick={() => onNudge(m, "end", 1)} title="Avançar o fim 1s">+</button>}
        </span>
        {onSetEnd && <button className="fr-settime" onClick={() => onSetEnd(m)} title="Finalizar a infração no tempo atual">marcar</button>}
      </div>
    </div>
  );
}

function pkHighlight(text: string, q: string): ReactNode {
  if (!q) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return text;
  return <Fragment>{text.slice(0, i)}<mark className="pk-hl">{text.slice(i, i + q.length)}</mark>{text.slice(i + q.length)}</Fragment>;
}

const PK_FILTERS: [string, string][] = [["todas", "Todas"], ["gravissima", "Gravíssimas"], ["grave", "Graves"], ["media", "Médias"], ["leve", "Leves"]];
const PK_GRAV_NAME: Record<string, string> = { gravissima: "Gravíssima", grave: "Grave", media: "Média", leve: "Leve" };

function RuleFicha({ r, added, onAdd, onBack }: { r: Rule; added: boolean; onAdd: (code: string) => void; onBack: () => void }) {
  const tk = gravTokens(r.grav);
  const enquad = r.enquad || { ctb: r.code, mbedv: "—" };
  const ptsLbl = r.pontos == null ? "Eliminatória" : r.pontos + (r.pontos === 1 ? " ponto" : " pontos");
  return (
    <div className="pkf">
      <div className="pkf-bar">
        <button className="pkf-back" onClick={onBack}><I.arrow width="15" height="15" style={{ transform: "rotate(180deg)" }} />Voltar à busca</button>
        <span className="pkf-tag">Ficha do procedimento</span>
      </div>
      <div className="pkf-body">
        <div className="pkf-top">
          <span className="pk-code mono" style={{ color: tk.color, background: tk.bg }}>{enquad.ctb}</span>
          <span className="pkf-grav" style={{ color: tk.color, background: tk.bg }}>{PK_GRAV_NAME[r.grav]} · {ptsLbl}</span>
        </div>
        <h3 className="pkf-name">{r.nome}</h3>
        <div className="pkf-sec">Definição</div>
        <p className="pkf-text">{r.desc}</p>
        {r.checks && (
          <Fragment>
            <div className="pkf-sec"><I.target width="13" height="13" />Como o ValBot detecta</div>
            <p className="pkf-text">{r.checks}</p>
          </Fragment>
        )}
        <div className="pkf-sec">Enquadramento normativo</div>
        <div className="pkf-norm mono">{enquad.ctb} · {enquad.mbedv}</div>
      </div>
      <div className="pkf-foot">
        <button className="lbtn" onClick={onBack}>Voltar</button>
        <button className="lbtn warn" disabled={added} onClick={() => onAdd(r.code)}>
          {added ? "Já no laudo" : <Fragment><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>Lançar esta infração</Fragment>}
        </button>
      </div>
    </div>
  );
}

interface FaultPickerProps {
  has: Set<string>; onAdd: (code: string) => void; onClose: () => void; pos: number; marks?: ClipMarks;
}
export function FaultPicker({ has, onAdd, onClose, pos, marks }: FaultPickerProps) {
  const [q, setQ] = useState("");
  const [g, setG] = useState("todas");
  const [view, setView] = useState<Rule | null>(null);

  const all = VB.rules;
  const avail = all.filter((r) => !has.has(r.code));
  const list = avail.filter((r) => (g === "todas" || r.grav === g) && (!q || (r.nome + " " + r.code + " " + (r.enquad.art || "") + " " + r.enquad.ctb + " " + (r.desc || "")).toLowerCase().includes(q.toLowerCase())));
  const counts = Object.fromEntries(PK_FILTERS.map(([k]) => [k, k === "todas" ? avail.length : avail.filter((r) => r.grav === k).length]));

  // sugestões: infrações detectadas pelo ValBot/examinador próximas ao início
  const near: MarkRef[] = [];
  const seen = new Set<string>();
  [...((marks && marks.vb) || []), ...((marks && marks.tp) || [])]
    // só infrações enquadráveis (com Art./ficha) viram sugestão — exclui notas do examinador.
    .filter((m) => m.kind !== "nota" && m.code && VB.ruleByCode[m.code])
    .sort((a, b) => Math.abs(a.t - pos) - Math.abs(b.t - pos))
    .forEach((m) => { if (!has.has(m.code) && !seen.has(m.code) && Math.abs(m.t - pos) <= 8) { seen.add(m.code); near.push(m); } });

  return (
    <div className="pk-scrim" onClick={onClose}>
      <div className="pk" onClick={(e) => e.stopPropagation()}>
        {view
          ? <RuleFicha r={view} added={has.has(view.code)} onAdd={onAdd} onBack={() => setView(null)} />
          : (
            <Fragment>
              <div className="pk-start">
                <span className="pk-start-ic">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4l2.5 1.5" /></svg>
                </span>
                <div className="pk-start-body">
                  <div className="pk-start-lbl">Início da infração</div>
                  <div className="pk-start-help">A ocorrência começa neste ponto do vídeo — o fim você ajusta depois no laudo.</div>
                </div>
                <div className="pk-start-tc mono">{fmtDur(Math.round(pos))}</div>
              </div>

              <div className="pk-search-row">
                <div className="pk-search">
                  <I.search />
                  <input autoFocus placeholder="Buscar infração, artigo do CTB ou palavra-chave…" value={q} onChange={(e) => setQ(e.target.value)} />
                  {q && <button className="pk-clear" onClick={() => setQ("")} title="Limpar"><I.close width="13" height="13" /></button>}
                </div>
                <button className="pk-x" onClick={onClose} title="Fechar"><I.close /></button>
              </div>

              {near.length > 0 && !q && (
                <div className="pk-sug">
                  <div className="pk-sug-lbl">
                    <img src="/logo.png" alt="ValBot" width="14" height="14" style={{ borderRadius: 3 }} />
                    Detectadas pela IA neste trecho
                  </div>
                  <div className="pk-sug-row">
                    {near.map((m) => {
                      const r = VB.ruleByCode[m.code];
                      const tk = gravTokens(m.grav);
                      return (
                        <button key={m.code} className="pk-sug-chip" style={{ color: tk.color, background: tk.bg }} onClick={() => onAdd(m.code)} title={r.nome + " · " + fmtDur(m.t)}>
                          <span className="mono">{r.enquad.ctb}</span>
                          <span className="pk-sug-t mono">{fmtDur(m.t)}</span>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="pk-filters">
                {PK_FILTERS.map(([k, l]) => (
                  <button key={k} className={"pk-chip" + (g === k ? " on" : "")} onClick={() => setG(k)}>
                    {k !== "todas" && <span className="pk-chip-dot" style={{ background: gravColor(k as Grav) }} />}{l}
                    <span className="pk-chip-n mono">{counts[k]}</span>
                  </button>
                ))}
              </div>

              <div className="pk-list">
                {list.map((r) => {
                  const tk = gravTokens(r.grav);
                  const ptsLbl = r.pontos == null ? "Elim." : r.pontos + (r.pontos === 1 ? " pt" : " pts");
                  return (
                    <div key={r.code} className="pk-item2" style={{ "--gc": tk.color } as CSSProperties}>
                      <button className="pk-item2-main" onClick={() => onAdd(r.code)} title="Lançar esta infração">
                        <span className="pk-code mono" style={{ color: tk.color, background: tk.bg }}>{r.enquad.ctb}</span>
                        <div className="pk-item2-txt">
                          <div className="pk-name">{pkHighlight(r.nome, q)}</div>
                          <div className="pk-norm mono">{r.enquad.ctb} · {r.enquad.mbedv}</div>
                        </div>
                        <span className="pk-pts mono" style={{ color: tk.color }}>{ptsLbl}</span>
                      </button>
                      <button className="pk-ficha" onClick={() => setView(r)} title="Abrir ficha do procedimento"><I.arrow /></button>
                    </div>
                  );
                })}
                {!list.length && <div className="pk-empty">Nenhuma infração encontrada{q ? <Fragment> para “<b>{q}</b>”</Fragment> : null}.</div>}
              </div>
            </Fragment>
          )}
      </div>
    </div>
  );
}

/* ---- Comentários do examinador (TechPrático) — training_annotations ---- */
// Lista TODAS as anotações do examinador (com e sem artigo do CTB), sempre
// visível, para o auditor ler. Clicar numa anotação com timestamp leva o
// playhead até o ponto e seleciona o marcador (quando há código Art.).
function TpAnnotations({ q, onSelectMark }: { q: ExamItem; onSelectMark: (m: MarkRef) => void }) {
  const anns = q.tpAnnotations || [];
  if (!anns.length) return null;
  return (
    <div className="insp-rec" style={{ borderColor: "var(--line)" }}>
      <div className="insp-rec-h">
        <span className="src-avatar tp" style={{ width: 16, height: 16, fontSize: 9, display: "inline-flex", alignItems: "center", justifyContent: "center", borderRadius: 4, background: "#6b7689", color: "#fff", fontWeight: 700 }}>TP</span>
        <span>Comentários do examinador (TechPrático)</span>
        <span className="insp-rec-conf mono">{anns.length}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 6 }}>
        {anns.map((a, i) => {
          const grav = a.code && VB.ruleByCode[a.code] ? VB.ruleByCode[a.code].grav : null;
          const tk = grav ? gravTokens(grav) : null;
          // com Art. -> seleciona o marcador de infração; sem Art. mas com timestamp
          // válido -> seek puro (marcador "nota" neutro, sem ficha).
          const go = () => {
            if (a.code) onSelectMark({ code: a.code, t: a.t, len: 4, grav: grav! });
            else if (a.t > 0) onSelectMark({ code: "", t: a.t, len: 4, grav: "leve", kind: "nota", note: a.text });
          };
          return (
            <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 12.5, lineHeight: 1.45, padding: "6px 8px", borderRadius: 7, background: "var(--inset)" }}>
              <button
                className="mono"
                onClick={go}
                title={a.code ? "Ir para o ponto da anotação no vídeo" : (a.t > 0 ? "Ir para o ponto da anotação no vídeo" : "Sem timestamp")}
                style={{
                  flexShrink: 0, fontSize: 11, padding: "1px 6px", borderRadius: 5,
                  border: "1px solid var(--line)", cursor: a.t > 0 || a.code ? "pointer" : "default",
                  color: tk ? tk.color : "var(--text-2)", background: tk ? tk.bg : "transparent",
                }}
                onClickCapture={(e) => { if (!(a.t > 0 || a.code)) e.preventDefault(); }}
              >
                {a.code ? a.code : (a.t > 0 ? fmtDur(a.t) : "—")}
                {a.code && a.t > 0 ? " · " + fmtDur(a.t) : ""}
              </button>
              <span style={{ color: "var(--text)", whiteSpace: "pre-wrap" }}>{a.text}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface InspectorProps {
  q: ExamItem; marks: ClipMarks; laudo: MarkRef[];
  setLaudo: (updater: MarkRef[] | ((l: MarkRef[]) => MarkRef[])) => void;
  pos: number; selCode: string | null; onSelectMark: (m: MarkRef) => void;
  onResolve: (result: string, laudo: MarkRef[], note: string) => void;
  onDivergence: () => void; onAfterResolve?: () => void; onPause?: () => void;
}
export function Inspector({ q, marks, laudo, setLaudo, pos, selCode, onSelectMark, onResolve, onAfterResolve, onPause }: InspectorProps) {
  const [note, setNote] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  useEffect(() => setNote(q.final ? (q.final.note || "") : ""), [q.id]);
  const v = effVerdictP(q);
  const diverge = q.status === "divergencia";
  const laudoHas = new Set(laudo.map((l) => l.code));

  const addLaudo = (code: string) => {
    if (laudoHas.has(code)) return;
    const ref = marks.tp.find((x) => x.code === code) || marks.vb.find((x) => x.code === code);
    setLaudo((l) => [...l, { code, t: ref ? ref.t : Math.round(pos), len: ref ? ref.len : 4, grav: VB.ruleByCode[code].grav as Grav }].sort((a, b) => a.t - b.t));
    setPickerOpen(false);
  };
  const removeLaudo = (m: MarkRef) => setLaudo((l) => l.filter((x) => x.code !== m.code));
  const nudgeLaudo = (m: MarkRef, edge: "start" | "end", d: number) => setLaudo((l) => l.map((x) => {
    if (x.code !== m.code) return x;
    if (edge === "start") {
      const end = x.t + x.len;
      const nt = Math.max(0, Math.min(end - 1, x.t + d));
      return { ...x, t: nt, len: end - nt };
    }
    const maxLen = Math.max(1, Math.round(q.dur) - x.t);
    return { ...x, len: Math.max(1, Math.min(maxLen, x.len + d)) };
  }).sort((a, b) => a.t - b.t));
  const setStartLaudo = (m: MarkRef) => setLaudo((l) => l.map((x) => x.code === m.code ? { ...x, len: Math.max(1, (x.t + x.len) - Math.round(pos)), t: Math.round(pos) } : x).sort((a, b) => a.t - b.t));
  const setEndLaudo = (m: MarkRef) => setLaudo((l) => l.map((x) => x.code === m.code ? { ...x, len: Math.max(1, Math.round(pos) - x.t) } : x));

  const laudoS = ptsOf(laudo.map((l) => l.code));
  const laudoResult = laudoS.grav || laudoS.pts > 4 ? "reprovado" : "aprovado";

  const verdictLabel = v === "aprovado" ? "Aprovado" : v === "reprovado" ? "Reprovado" : v === "divergencia" ? "Em divergência" : v === "interrompido" ? "Exame interrompido" : "Processando";
  void verdictLabel;

  return (
    <div className="ppane insp">
      <div className="pane-head">
        <I.target width="14" height="14" />
        <span className="ph-title">Auditoria do laudo</span>
        <span className="ph-formal">IA consultiva · decisão humana</span>
      </div>
      <div className="insp-body">
        <Comparison q={q} />
        {q.vbComment && (
          <div className="insp-rec">
            <div className="insp-rec-h">
              <img src="/logo.png" alt="ValBot" width="13" height="13" style={{ borderRadius: 3 }} />
              <span>Parecer do ValBot</span>
              {q.vb && <span className="insp-rec-conf mono">{Math.round(q.vb.conf! * 100)}% confiança</span>}
            </div>
            <p className="insp-rec-t" title={q.vbComment}>{q.vbComment}</p>
          </div>
        )}
        <div className="insp-actions">
          <div className="ia-row">
            <button className="lbtn bad" onClick={() => setConfirm("reprovado")}><I.close width="15" height="15" />Reprovar</button>
            <button className="lbtn ok" onClick={() => setConfirm("aprovado")}><I.check width="15" height="15" />Aprovar</button>
            <button className="lbtn warn" onClick={() => { onPause && onPause(); setPickerOpen(true); }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
              Lançar infração
            </button>
          </div>
        </div>

        <div className="laudo">
          <div className="laudo-head">
            <span className="src-avatar rev"><I.user /></span>
            <div style={{ minWidth: 0, flex: 1 }}><div className="src-title">Infrações do laudo</div><div className="src-sub">Sua análise · Renata Moura</div></div>
            <span className="lv-tag mono" style={{ background: laudoResult === "aprovado" ? "color-mix(in oklab,var(--ok),transparent 84%)" : "color-mix(in oklab,var(--bad),transparent 84%)", color: laudoResult === "aprovado" ? "var(--ok)" : "var(--bad)" }}>{laudoS.label} → {laudoResult === "aprovado" ? "Aprovado" : "Reprovado"}</span>
          </div>
          <div className="laudo-faults">
            {laudo.length ? laudo.map((m) => <FaultRow key={m.code} m={m} onClick={onSelectMark} onRemove={removeLaudo} onSetStart={setStartLaudo} onSetEnd={setEndLaudo} onNudge={nudgeLaudo} />)
              : <div className="laudo-hint">Use <b>Lançar infração</b> para registrar uma ocorrência — cada lançamento exige o <b>timestamp</b> e a <b>infração</b>. Também dá para aceitar marcadores das trilhas.</div>}
          </div>
          <textarea className="laudo-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Fundamentação técnica do auditor…" />
        </div>
      </div>

      {pickerOpen && <FaultPicker has={laudoHas} onAdd={addLaudo} onClose={() => setPickerOpen(false)} pos={pos} marks={marks} />}

      {confirm && (
        <div className="conf-scrim" onClick={() => setConfirm(null)}>
          <div className="conf" onClick={(e) => e.stopPropagation()}>
            <div className="conf-head"><span className="conf-dot" style={{ background: confirm === "aprovado" ? "var(--ok)" : "var(--bad)" }} />Confirmar {confirm === "aprovado" ? "aprovação" : "reprovação"}</div>
            <div className="conf-body">
              <div className="conf-line">Exame <b className="mono">{q.renach}</b></div>
              <div className="conf-line">Infrações no laudo <b>{laudo.length}</b></div>
              <div className="conf-line">Pontuação <b className="mono">{laudoS.label}</b> · laudo configura <b style={{ color: laudoResult === "aprovado" ? "var(--ok)" : "var(--bad)" }}>{laudoResult === "aprovado" ? "Apto" : "Inapto"}</b></div>
              {confirm === laudoResult
                ? <div className="conf-valid ok"><I.check width="15" height="15" />Decisão coerente com o laudo. Ao confirmar, o laudo é registrado e o próximo exame da fila é carregado.</div>
                : <div className="conf-valid bad"><span style={{ fontWeight: 800 }}>⚠</span>{confirm === "aprovado" ? "O laudo soma " + laudoS.label + " e configura reprovação. Remova infrações ou reprove o exame." : "O laudo não soma pontuação de reprovação. Enquadre as infrações antes de reprovar."}</div>}
            </div>
            <div className="conf-foot">
              <button className="lbtn" onClick={() => setConfirm(null)}>Cancelar</button>
              <button className={"lbtn " + (confirm === "aprovado" ? "ok" : "bad")} disabled={confirm !== laudoResult} onClick={() => { onResolve(confirm, laudo, note); setConfirm(null); onAfterResolve && onAfterResolve(); }}>{confirm === "aprovado" ? "Aprovar e avançar" : "Reprovar e avançar"}</button>
            </div>
          </div>
        </div>
      )}

      {diverge && null}
    </div>
  );
}

export default Inspector;
