import { useMemo, useState } from "react";
import "./FaultPicker.css";

/* ============ Tipos ============ */

/** Enquadramento normativo da regra (CTB + MBEDV). */
export interface RuleEnquad {
  /** Artigo do CTB, ex. "Art. 165". Usado também na busca textual. */
  ctb: string;
  /** Referência no MBEDV, ex. "MBEDV 2.4.1". */
  mbedv: string;
  /** Artigo/dispositivo livre (campo extra usado só na busca). */
  art?: string;
}

/** Regra de infração exibida no picker e na ficha. */
export interface Rule {
  /** Código único da regra (chave de duplicidade e de seleção). */
  code: string;
  /** Gravidade — define a cor/token visual. */
  grav: "gravissima" | "grave" | "media" | "leve";
  /** Nome curto da infração. */
  nome: string;
  /** Definição/descrição longa (ficha + busca). */
  desc?: string;
  /** Pontos do CTB; `null`/`undefined` ⇒ eliminatória. */
  pontos?: number | null;
  /** Texto "como o ValBot detecta" (opcional, só na ficha). */
  checks?: string;
  /** Enquadramento normativo. */
  enquad: RuleEnquad;
}

/** Sugestão da IA: infração detectada por proximidade de tempo. */
export interface Suggestion {
  /** Código da regra detectada (precisa existir em `rules`). */
  code: string;
  /** Gravidade detectada (token de cor do chip). */
  grav: Rule["grav"];
  /** Timestamp (s) da detecção. */
  t: number;
}

export interface FaultPickerProps {
  /** Catálogo completo de regras. */
  rules: Rule[];
  /** Início da infração (segundos) — vem do tempo atual do vídeo. */
  startTime: number;
  /** Detecções da IA próximas do `startTime`. */
  suggestions?: Suggestion[];
  /** Códigos já presentes no laudo (controle de duplicidade). */
  inLaudo?: string[];
  /** Lança a infração escolhida. */
  onPick: (ruleCode: string) => void;
  /** Fecha o modal. */
  onClose: () => void;
}

/* ============ Helpers ============ */

const GRAV_COLOR: Record<Rule["grav"], string> = {
  gravissima: "var(--g-elim)",
  grave: "var(--g-grave)",
  media: "var(--g-media)",
  leve: "var(--g-leve)",
};

function gravColor(g: Rule["grav"]): string {
  return GRAV_COLOR[g];
}

function gravTokens(g: Rule["grav"]): { color: string; bg: string } {
  const c = gravColor(g);
  return { color: c, bg: `color-mix(in oklab, ${c}, transparent 84%)` };
}

/** mm:ss */
function fmtDur(s: number): string {
  const sec = Math.max(0, Math.round(s));
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

const PK_FILTERS: Array<[string, string]> = [
  ["todas", "Todas"],
  ["gravissima", "Eliminatórias"],
  ["grave", "Graves"],
  ["media", "Médias"],
  ["leve", "Leves"],
];

const PK_GRAV_NAME: Record<Rule["grav"], string> = {
  gravissima: "Eliminatória",
  grave: "Grave",
  media: "Média",
  leve: "Leve",
};

/** Realça o trecho que casa com a busca. */
function pkHighlight(text: string, q: string): React.ReactNode {
  if (!q) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark className="pk-hl">{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

/* ============ Ícones inline ============ */

function IconSearch() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function IconClose({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function IconArrow({ size = 16, flip = false }: { size?: number; flip?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={flip ? { transform: "rotate(180deg)" } : undefined}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function IconPlus({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function IconTarget({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4" />
    </svg>
  );
}

/* ============ Ficha do procedimento (por regra) ============ */

interface RuleFichaProps {
  r: Rule;
  added: boolean;
  onAdd: (code: string) => void;
  onBack: () => void;
}

function RuleFicha({ r, added, onAdd, onBack }: RuleFichaProps) {
  const tk = gravTokens(r.grav);
  const enquad = r.enquad || { ctb: r.code, mbedv: "—" };
  const ptsLbl = r.pontos == null ? "Eliminatória" : `${r.pontos}${r.pontos === 1 ? " ponto" : " pontos"}`;
  return (
    <div className="pkf">
      <div className="pkf-bar">
        <button className="pkf-back" onClick={onBack}>
          <IconArrow size={15} flip />
          Voltar à busca
        </button>
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
          <>
            <div className="pkf-sec"><IconTarget />Como o ValBot detecta</div>
            <p className="pkf-text">{r.checks}</p>
          </>
        )}
        <div className="pkf-sec">Enquadramento normativo</div>
        <div className="pkf-norm mono">{enquad.ctb} · {enquad.mbedv}</div>
      </div>
      <div className="pkf-foot">
        <button className="lbtn" onClick={onBack}>Voltar</button>
        <button className="lbtn warn" disabled={added} onClick={() => onAdd(r.code)}>
          {added ? "Já no laudo" : <><IconPlus />Lançar esta infração</>}
        </button>
      </div>
    </div>
  );
}

/* ============ Modal "Lançar infração" ============ */

export function FaultPicker({ rules, startTime, suggestions, inLaudo, onPick, onClose }: FaultPickerProps) {
  const [q, setQ] = useState("");
  const [g, setG] = useState("todas");
  const [view, setView] = useState<Rule | null>(null);

  const has = useMemo(() => new Set(inLaudo || []), [inLaudo]);
  const ruleByCode = useMemo(() => {
    const m: Record<string, Rule> = {};
    for (const r of rules) m[r.code] = r;
    return m;
  }, [rules]);

  // disponíveis = ainda não estão no laudo
  const avail = useMemo(() => rules.filter((r) => !has.has(r.code)), [rules, has]);

  const list = useMemo(
    () =>
      avail.filter((r) => {
        if (g !== "todas" && r.grav !== g) return false;
        if (!q) return true;
        const hay = `${r.nome} ${r.code} ${r.enquad.art || ""} ${r.enquad.ctb} ${r.desc || ""}`.toLowerCase();
        return hay.includes(q.toLowerCase());
      }),
    [avail, g, q],
  );

  const counts = useMemo(
    () =>
      Object.fromEntries(
        PK_FILTERS.map(([k]) => [k, k === "todas" ? avail.length : avail.filter((r) => r.grav === k).length]),
      ) as Record<string, number>,
    [avail],
  );

  // sugestões: detecções da IA próximas (≤ 8s) ao início, sem duplicar laudo
  const near = useMemo(() => {
    const out: Suggestion[] = [];
    const seen = new Set<string>();
    [...(suggestions || [])]
      .sort((a, b) => Math.abs(a.t - startTime) - Math.abs(b.t - startTime))
      .forEach((m) => {
        if (!has.has(m.code) && !seen.has(m.code) && Math.abs(m.t - startTime) <= 8) {
          seen.add(m.code);
          out.push(m);
        }
      });
    return out;
  }, [suggestions, startTime, has]);

  return (
    <div className="pk-scrim" onClick={onClose}>
      <div className="pk" onClick={(e) => e.stopPropagation()}>
        {view ? (
          <RuleFicha r={view} added={has.has(view.code)} onAdd={onPick} onBack={() => setView(null)} />
        ) : (
          <>
            {/* destaque: início da infração */}
            <div className="pk-start">
              <span className="pk-start-ic">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 8v4l2.5 1.5" />
                </svg>
              </span>
              <div className="pk-start-body">
                <div className="pk-start-lbl">Início da infração</div>
                <div className="pk-start-help">A ocorrência começa neste ponto do vídeo — o fim você ajusta depois no laudo.</div>
              </div>
              <div className="pk-start-tc mono">{fmtDur(startTime)}</div>
            </div>

            <div className="pk-search-row">
              <div className="pk-search">
                <IconSearch />
                <input
                  autoFocus
                  placeholder="Buscar infração, artigo do CTB ou palavra-chave…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />
                {q && (
                  <button className="pk-clear" onClick={() => setQ("")} title="Limpar">
                    <IconClose size={13} />
                  </button>
                )}
              </div>
              <button className="pk-x" onClick={onClose} title="Fechar">
                <IconClose />
              </button>
            </div>

            {near.length > 0 && !q && (
              <div className="pk-sug">
                <div className="pk-sug-lbl">
                  <img src="logo.png" alt="ValBot" width={14} height={14} style={{ borderRadius: 3 }} />
                  Detectadas pela IA neste trecho
                </div>
                <div className="pk-sug-row">
                  {near.map((m) => {
                    const r = ruleByCode[m.code];
                    if (!r) return null;
                    const tk = gravTokens(m.grav);
                    return (
                      <button
                        key={m.code}
                        className="pk-sug-chip"
                        style={{ color: tk.color, background: tk.bg }}
                        onClick={() => onPick(m.code)}
                        title={`${r.nome} · ${fmtDur(m.t)}`}
                      >
                        <span className="mono">{r.enquad.ctb}</span>
                        <span className="pk-sug-t mono">{fmtDur(m.t)}</span>
                        <IconPlus size={12} />
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="pk-filters">
              {PK_FILTERS.map(([k, l]) => (
                <button key={k} className={"pk-chip" + (g === k ? " on" : "")} onClick={() => setG(k)}>
                  {k !== "todas" && <span className="pk-chip-dot" style={{ background: gravColor(k as Rule["grav"]) }} />}
                  {l}
                  <span className="pk-chip-n mono">{counts[k]}</span>
                </button>
              ))}
            </div>

            <div className="pk-list">
              {list.map((r) => {
                const tk = gravTokens(r.grav);
                const ptsLbl = r.pontos == null ? "Elim." : `${r.pontos}${r.pontos === 1 ? " pt" : " pts"}`;
                return (
                  <div key={r.code} className="pk-item2" style={{ ["--gc" as string]: tk.color }}>
                    <button className="pk-item2-main" onClick={() => onPick(r.code)} title="Lançar esta infração">
                      <span className="pk-code mono" style={{ color: tk.color, background: tk.bg }}>{r.enquad.ctb}</span>
                      <div className="pk-item2-txt">
                        <div className="pk-name">{pkHighlight(r.nome, q)}</div>
                        <div className="pk-norm mono">{r.enquad.ctb} · {r.enquad.mbedv}</div>
                      </div>
                      <span className="pk-pts mono" style={{ color: tk.color }}>{ptsLbl}</span>
                    </button>
                    <button className="pk-ficha" onClick={() => setView(r)} title="Abrir ficha do procedimento">
                      <IconArrow />
                    </button>
                  </div>
                );
              })}
              {!list.length && (
                <div className="pk-empty">
                  Nenhuma infração encontrada{q ? <> para “<b>{q}</b>”</> : null}.
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default FaultPicker;
