import { useState } from "react";
import "./DetailModal.css";

/**
 * Ficha da regra/infração exibida no modal.
 * Todos os campos são opcionais — o componente é à prova de falhas:
 * um código de regra inexistente ou parcial NÃO derruba a tela.
 */
export interface RuleEnquad {
  art?: string;
  ctb?: string;
  mbedv?: string;
}

export interface RuleComment {
  /** "tp" = TechPrático (examinador) · "vb" = ValBot (IA) · "auditor" */
  source?: "tp" | "vb" | "auditor" | string;
  /** Rótulo do avatar (ex.: "TP", "IA", "AU"). Default derivado de `source`. */
  avatar?: string;
  /** Linha de autoria (ex.: "TechPrático · examinador"). */
  author?: string;
  /** Meta à direita do cabeçalho (ex.: "02:14" ou "91% · 02:14"). */
  meta?: string;
  /** Corpo do comentário. */
  text?: string;
}

export interface Rule {
  code?: string;
  nome?: string;
  desc?: string;
  /** Gravidade: "leve" | "media" | "grave" | "gravissima". */
  grav?: string;
  /** Peso/pontos da infração. */
  pontos?: number;
  categorias?: string;
  constatacao?: string;
  /** Aba "Condutas que pontuam". */
  pontua?: string;
  /** Aba "Condutas que não pontuam". */
  naoPontua?: string;
  /** Aba "Definições e procedimentos". */
  definicoes?: string;
  /** Fallback de qualquer aba quando o texto específico não existe. */
  checks?: string;
  /** Informações complementares. */
  compl?: string;
  enquad?: RuleEnquad;
  /** Comentários (TP / ValBot / Auditor). Opcional. */
  comentarios?: RuleComment[];
  /** Linha "Detectado por" do bloco de auditoria. */
  detectadoPor?: string;
  /** Janela de ocorrência (ex.: "02:14 – 02:19"). */
  ocorrencia?: string;
}

interface GravMeta {
  label: string;
  color: string;
  bg: string;
  pontos: number;
}

const GRAV_META: Record<string, GravMeta> = {
  gravissima: { label: "Gravíssima", color: "#BE123C", bg: "#FCEAEF", pontos: 6 },
  grave: { label: "Grave", color: "#B45309", bg: "#FBF1E3", pontos: 4 },
  media: { label: "Média", color: "#1D4ED8", bg: "#E7EEFD", pontos: 2 },
  leve: { label: "Leve", color: "#6B7689", bg: "#F1F4F9", pontos: 1 },
};

const GRAV_COLOR: Record<string, string> = {
  gravissima: "var(--g-elim)",
  grave: "var(--g-grave)",
  media: "var(--g-media)",
  leve: "var(--g-leve)",
};

function gravColor(g?: string): string {
  return (g && GRAV_COLOR[g]) || "var(--faint)";
}

function avatarOf(c: RuleComment): { cls: string; label: string } {
  const s = c?.source;
  if (s === "tp") return { cls: "tp", label: c?.avatar || "TP" };
  if (s === "vb") return { cls: "vb", label: c?.avatar || "IA" };
  return { cls: "tp", label: c?.avatar || "AU" };
}

export function DetailModal({ rule, onClose }: { rule: any; onClose: () => void }) {
  const [view, setView] = useState<number>(0); // 0 = comentários (padrão), 1 = ficha
  const [tab, setTab] = useState<number>(0);

  // Fallback à prova de falhas: regra ausente/parcial degrada em vez de quebrar.
  const r: Rule = rule || {};
  const code = r.code ?? "—";
  const ctb = r.enquad?.ctb ?? code;
  const nome = r.nome ?? "Infração " + code;
  const desc = r.desc ?? "Detalhe não disponível para este código.";

  const grav: GravMeta =
    (r.grav && GRAV_META[r.grav]) || { label: "—", color: "var(--faint)", bg: "transparent", pontos: 0 };
  const pontos = typeof r.pontos === "number" ? r.pontos : grav.pontos;

  const comentarios: RuleComment[] = Array.isArray(r.comentarios) ? r.comentarios : [];
  const tabBodies = [r.pontua, r.naoPontua, r.definicoes];

  return (
    <div className="dm-scrim" onClick={onClose}>
      <div
        className="dm"
        onClick={(e) => e.stopPropagation()}
        style={{ ["--gc" as any]: gravColor(r.grav) }}
      >
        <div className="dm-head">
          <span className="dm-code mono">{ctb}</span>
          <span className="dm-grav" style={{ color: grav.color, background: grav.bg }}>
            {grav.label} · peso {pontos}
          </span>
          <button className="dm-x" onClick={onClose} aria-label="Fechar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="dm-toptabs">
          <button className={"dm-toptab" + (view === 0 ? " on" : "")} onClick={() => setView(0)}>
            Comentários
          </button>
          <button className={"dm-toptab" + (view === 1 ? " on" : "")} onClick={() => setView(1)}>
            Ficha do procedimento
          </button>
        </div>

        <div className="dm-body">
          {view === 0 ? (
            <>
              <div className="dm-title">
                {ctb} — {nome}
              </div>
              {comentarios.length > 0 ? (
                comentarios.map((c, i) => {
                  const av = avatarOf(c);
                  return (
                    <div className="cmt" key={i}>
                      <div className="cmt-h">
                        <span className={"cmt-av " + av.cls}>{av.label}</span>
                        {c?.author ?? "Comentário"}
                        {c?.meta && <span className="cmt-meta mono">{c.meta}</span>}
                      </div>
                      <p className="dm-text">{c?.text ?? desc}</p>
                    </div>
                  );
                })
              ) : (
                <p className="dm-text" style={{ color: "var(--faint)" }}>
                  Nenhum comentário registrado para esta infração.
                </p>
              )}
            </>
          ) : (
            <>
              <div className="fic-row">
                <span className="fic-k">Infração</span>
                <div className="fic-v">
                  <b className="mono">{ctb}</b> — {nome}
                </div>
              </div>
              {r.categorias && (
                <div className="fic-row">
                  <span className="fic-k">Categorias</span>
                  <div className="fic-v">{r.categorias}</div>
                </div>
              )}
              <div className="fic-row">
                <span className="fic-k">Descrição</span>
                <div className="fic-v">{desc}</div>
              </div>
              <div className="fic-row">
                <span className="fic-k">Gravidade · Peso</span>
                <div className="fic-v">
                  {grav.label} · {pontos} ponto{pontos !== 1 ? "s" : ""}
                </div>
              </div>

              {r.constatacao && (
                <>
                  <div className="dm-sec">Constatação da infração</div>
                  <p className="dm-text">{r.constatacao}</p>
                </>
              )}

              <div className="dm-tabs">
                {["Condutas que pontuam", "Condutas que não pontuam", "Definições e procedimentos"].map(
                  (t, k) => (
                    <button
                      key={k}
                      className={"dm-tab" + (tab === k ? " on" : "")}
                      onClick={() => setTab(k)}
                    >
                      {t}
                    </button>
                  )
                )}
              </div>
              <p className="dm-text dm-tabbody">{tabBodies[tab] || r.checks || "—"}</p>

              {r.compl && (
                <>
                  <div className="dm-sec">Informações complementares</div>
                  <p className="dm-text">{r.compl}</p>
                </>
              )}

              <div className="dm-sec">Auditoria deste exame</div>
              <div className="dm-grid">
                <div className="dm-cell">
                  <span>Detectado por</span>
                  <b>{r.detectadoPor || "Laudo do auditor"}</b>
                </div>
                <div className="dm-cell">
                  <span>Ocorrência</span>
                  <b className="mono">{r.ocorrencia || "—"}</b>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
