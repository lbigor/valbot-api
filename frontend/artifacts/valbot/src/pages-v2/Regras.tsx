/* ============================================================================
   ValBot — Regras · matriz CTB/MBEDV + Ficha de Procedimento rica (3 colunas)
   Porte fiel de .design-ref/page-regras.jsx.
   DADOS REAIS: GET /api/rubricas/1020-2025 (credentials:"include") via react-query.
   META_GRAV é CONSTANTE de config (cores/labels por gravidade) — mantida local.
   Estilos .fp-* adicionados em system/vb.css (origem: infracoes.css).
   ============================================================================ */
import { useState, useMemo, Fragment } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { CSSProperties, ReactNode } from "react";
import { Shell } from "@/system/Shell";
import { I } from "@/system/icons";

/* ---- tipos (any tolerável) ---- */
type Grav = "gravissima" | "grave" | "media" | "leve";
interface Enquad {
  ctb?: string;
}
interface Rule {
  codigo: string;
  code?: string;
  nome: string;
  grav: Grav;
  pontos: number;
  ctb: string;
  enquad?: Enquad;
  categorias?: string;
  constatacao?: string;
  desc?: string;
  pontua?: ReactNode;
  checks?: ReactNode;
  naoPontua?: ReactNode;
  definicoes?: ReactNode;
  compl?: ReactNode;
  [k: string]: unknown;
}
interface GravMeta {
  label: string;
  color: string;
  bg: string;
  ring: string;
  pontos: number;
}

const NAT_ORDER: Grav[] = ["gravissima", "grave", "media", "leve"];
const NAT_ASC: Grav[] = ["leve", "media", "grave", "gravissima"];
const PTS_OF: Record<Grav, number> = { gravissima: 6, grave: 4, media: 2, leve: 1 };

/* META_GRAV — CONSTANTE de config (cores/labels por gravidade). NÃO é mock de
   negócio; copiado de .design-ref/vb-data.js (sistema vb-data). */
const META_GRAV: Record<Grav, GravMeta> = {
  gravissima: { label: "Gravíssima", pontos: 6, color: "#BE123C", bg: "#FCEAEF", ring: "#F3C2CF" },
  grave: { label: "Grave", pontos: 4, color: "#B45309", bg: "#FBF1E3", ring: "#F0D9B3" },
  media: { label: "Média", pontos: 2, color: "#1D4ED8", bg: "#E7EEFD", ring: "#C5D6F8" },
  leve: { label: "Leve", pontos: 1, color: "#6B7689", bg: "#F1F4F9", ring: "#E5E9F0" },
};

const natMeta = (g: Grav): GravMeta =>
  META_GRAV[g] || {
    label: "—",
    color: "var(--faint)",
    bg: "var(--surface-3)",
    ring: "var(--border)",
    pontos: 0,
  };

/* ---- normalização tolerante da gravidade vinda do endpoint ---- */
function normGrav(v: unknown): Grav {
  const s = String(v ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
  if (s.startsWith("gravissim") || s === "eliminatoria") return "gravissima";
  if (s.startsWith("grav")) return "grave";
  if (s.startsWith("med")) return "media";
  if (s.startsWith("lev")) return "leve";
  return "media";
}

/* ---- mapeia uma infração do endpoint pro shape Rule da tela (tolerante) ---- */
function toRule(inf: any): Rule {
  const codigo = String(inf.codigo ?? inf.id ?? inf.code ?? "");
  const nome = String(inf.descricao ?? inf.nome ?? inf.desc ?? "");
  const grav = normGrav(inf.gravidade ?? inf.grav);
  const ctb = String(inf.base_legal ?? inf.ctb ?? inf.artigo ?? codigo);
  const pontos =
    typeof inf.pontos === "number" ? inf.pontos : Number(inf.pontos ?? PTS_OF[grav]);
  return {
    ...inf,
    codigo,
    code: codigo,
    nome,
    grav,
    ctb,
    pontos: Number.isFinite(pontos) ? pontos : PTS_OF[grav],
    enquad: { ctb },
  } as Rule;
}

/* GET /api/rubricas/{slug} — catálogo real de regras (credentials:include) */
async function fetchRubrica(slug: string): Promise<Rule[]> {
  const r = await fetch(`/api/rubricas/${slug}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const d = await r.json();
  const arr: any[] = Array.isArray(d?.infracoes)
    ? d.infracoes
    : Array.isArray(d)
      ? d
      : [];
  return arr.map(toRule);
}

interface EditState {
  mode: "new" | "edit";
  rule: Rule;
}

const QK = ["v2-rubricas", "1020-2025"] as const;

export default function Regras() {
  const qc = useQueryClient();
  const {
    data: rulesData,
    isLoading,
    isError,
  } = useQuery<Rule[]>({
    queryKey: QK,
    queryFn: () => fetchRubrica("1020-2025"),
  });
  // blindagem: nunca confiar no shape do cache (colisão de queryKey já causou
  // `i.filter is not a function` → tela branca). Sempre coagir para array.
  const rules: Rule[] = Array.isArray(rulesData) ? rulesData : [];
  const [q, setQ] = useState("");
  const [natF, setNatF] = useState<Grav | "todas">("todas");
  const [edit, setEdit] = useState<EditState | null>(null);
  const [ficha, setFicha] = useState<Rule | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => {
    setToast(m);
    clearTimeout((window as any).__t);
    (window as any).__t = setTimeout(() => setToast(null), 1800);
  };

  const counts = useMemo(() => {
    const c: Record<string, number> = { todas: rules.length };
    NAT_ORDER.forEach((g) => (c[g] = rules.filter((r) => r.grav === g).length));
    return c;
  }, [rules]);

  const shown = rules.filter(
    (r) =>
      (natF === "todas" || r.grav === natF) &&
      (!q || (r.nome + " " + r.codigo + " " + r.ctb).toLowerCase().includes(q.toLowerCase())),
  );

  const save = (rule: Rule) => {
    // edição/criação otimista no cache da query (catálogo é read-only no backend)
    qc.setQueryData<Rule[]>(QK, (l = []) => {
      const i = l.findIndex((x) => x.codigo === rule.codigo);
      if (i >= 0) {
        const c = l.slice();
        c[i] = rule;
        return c;
      }
      return [...l, rule];
    });
    const mode = edit?.mode;
    setEdit(null);
    flash(mode === "new" ? "Infração adicionada" : "Infração atualizada");
  };

  const actions = (
    <button
      className="btn btn-primary"
      onClick={() =>
        setEdit({
          mode: "new",
          rule: { codigo: "", code: "", nome: "", grav: "media", pontos: 2, ctb: "", enquad: {} },
        })
      }
    >
      <I.plus w={16} />
      Nova infração
    </button>
  );

  return (
    <Shell
      active="regras"
      title="Regras"
      sub="Matriz CTB/MBEDV · modelo de pontuação Res. CONTRAN 1.020/2025"
      actions={actions}
    >
      <div className="row wrap" style={{ marginBottom: 16, gap: 12 }}>
        <span className="badge proc" style={{ height: 38, padding: "0 14px", fontSize: 14 }}>
          <span className="bd" />
          <span className="mono" style={{ fontWeight: 700 }}>
            v2.0
          </span>{" "}
          · Vigente
        </span>
        <span className="spacer" />
        <span className="badge neutral" style={{ height: 32 }}>
          CTB <b style={{ marginLeft: 4 }}>Lei 9.503/97</b>
        </span>
        <span className="badge neutral" style={{ height: 32 }}>
          Res. CONTRAN <b style={{ marginLeft: 4 }}>1.020/2025</b>
        </span>
        <span className="badge neutral" style={{ height: 32 }}>
          MBEDV <b style={{ marginLeft: 4 }}>Senatran</b>
        </span>
      </div>

      {/* modelo de pontuação */}
      <div className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-b" style={{ display: "flex", alignItems: "center", gap: 0, padding: 0 }}>
          <div style={{ display: "flex" }}>
            {NAT_ASC.map((g) => (
              <div
                key={g}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 3,
                  padding: "14px 22px",
                  borderRight: "1px solid var(--border)",
                }}
              >
                <span
                  className="mono"
                  style={{ fontSize: 24, fontWeight: 800, color: natMeta(g).color }}
                >
                  {PTS_OF[g]}
                </span>
                <span style={{ fontSize: 11.5, fontWeight: 600, color: "var(--muted)" }}>
                  {natMeta(g).label}
                </span>
              </div>
            ))}
          </div>
          <div style={{ padding: "14px 22px", display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>
              Aprovação por pontuação acumulada
            </span>
            <span className="badge ok" style={{ fontSize: 13 }}>
              <span className="bd" />≤{" "}
              <b className="mono" style={{ margin: "0 3px", fontSize: 15 }}>
                10
              </b>{" "}
              aprovado
            </span>
            <span className="badge bad" style={{ fontSize: 13 }}>
              <span className="bd" />&gt;{" "}
              <b className="mono" style={{ margin: "0 3px", fontSize: 15 }}>
                10
              </b>{" "}
              reprovado
            </span>
          </div>
          <span
            style={{
              marginLeft: "auto",
              padding: "0 22px",
              fontSize: 11.5,
              color: "var(--faint)",
              textAlign: "right",
              maxWidth: 220,
              lineHeight: 1.4,
            }}
          >
            Sem faltas eliminatórias automáticas · Art. 45
          </span>
        </div>
      </div>

      <div className="row wrap" style={{ marginBottom: 14, gap: 10 }}>
        <div className="search">
          <I.search />
          <input
            placeholder="Buscar por infração, código ou artigo…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        {[{ k: "todas", label: "Todas" }, ...NAT_ORDER.map((g) => ({ k: g, label: natMeta(g).label }))].map(
          (f) => (
            <button
              key={f.k}
              className={"chip" + (natF === f.k ? " on" : "")}
              onClick={() => setNatF(f.k as Grav | "todas")}
            >
              {f.k !== "todas" && (
                <span className="cdot" style={{ background: natMeta(f.k as Grav).color }} />
              )}
              {f.label}
              <span className="chip-n">{counts[f.k] || 0}</span>
            </button>
          ),
        )}
      </div>

      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: "54%" }}>Infração</th>
              <th>Peso</th>
              <th>Enquadramento CTB</th>
              <th style={{ width: 70 }}></th>
            </tr>
          </thead>
          <tbody>
            {NAT_ORDER.map((g) => {
              const grp = shown.filter((r) => r.grav === g);
              if (!grp.length) return null;
              const m = natMeta(g);
              return (
                <Fragment key={g}>
                  <tr>
                    <td colSpan={4} style={{ padding: 0, background: "var(--surface-2)" }}>
                      <div
                        style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 16px" }}
                      >
                        <span
                          style={{ width: 9, height: 9, borderRadius: "50%", background: m.color }}
                        />
                        <span style={{ fontWeight: 700, fontSize: 12.5, color: m.color }}>
                          {m.label}
                        </span>
                        <span className="badge neutral" style={{ height: 20 }}>
                          peso {PTS_OF[g]}
                        </span>
                        <span className="spacer t-sub">{grp.length} infrações</span>
                      </div>
                    </td>
                  </tr>
                  {grp.map((r) => (
                    <tr
                      key={r.codigo}
                      className="clickable"
                      title="Abrir ficha de procedimento"
                      onClick={() => setFicha(r)}
                    >
                      <td>
                        <div
                          className="t-strong"
                          style={{
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {r.nome}
                        </div>
                        <div className="mono t-sub">{r.codigo}</div>
                      </td>
                      <td>
                        <span
                          style={{
                            display: "inline-grid",
                            placeItems: "center",
                            width: 32,
                            height: 32,
                            borderRadius: 9,
                            fontFamily: "var(--mono)",
                            fontWeight: 700,
                            fontSize: 14,
                            color: m.color,
                            background: m.bg,
                            boxShadow: `inset 0 0 0 1px ${m.ring}`,
                          }}
                        >
                          {PTS_OF[g]}
                        </span>
                      </td>
                      <td className="mono t-sub">{r.ctb}</td>
                      <td>
                        <button
                          className="icon-btn"
                          style={{ width: 32, height: 32 }}
                          title="Editar"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEdit({ mode: "edit", rule: { ...r } });
                          }}
                        >
                          <I.edit w={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </Fragment>
              );
            })}
            {!shown.length && (
              <tr>
                <td
                  colSpan={4}
                  style={{ padding: "28px 16px", textAlign: "center", color: "var(--muted)" }}
                >
                  {isLoading
                    ? "Carregando infrações…"
                    : isError
                      ? "Não foi possível carregar as infrações."
                      : "Nenhuma infração."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="tbl-foot">
          <I.regras w={14} />
          {shown.length} infrações · matriz v2.0 (vigente)
        </div>
      </div>

      {ficha && (
        <FichaProcedimento
          r={ficha}
          onClose={() => setFicha(null)}
          onEdit={(r) => {
            setFicha(null);
            setEdit({ mode: "edit", rule: { ...r } });
          }}
        />
      )}
      {edit && (
        <RegraModal mode={edit.mode} rule={edit.rule} onSave={save} onClose={() => setEdit(null)} />
      )}
      {toast && <div className="toast">{toast}</div>}
    </Shell>
  );
}

/* Ficha de Procedimento — réplica fiel (vb.css .fp-*) */
interface FichaProps {
  r: Rule;
  onClose: () => void;
  onEdit?: (r: Rule) => void;
}
function FichaProcedimento({ r, onClose, onEdit }: FichaProps) {
  const m = natMeta(r.grav);
  const enquad = r.enquad || {};
  const cat = (r.categorias || "ACC, A, B, C, D e E.")
    .replace(/\.$/, "")
    .split(/[,;]\s*| e /)
    .map((s) => s.trim())
    .filter(Boolean);
  const constat = r.constatacao || "Será constatada durante a condução do veículo pelo candidato.";
  const na = <span className="fp-na">Não se aplica a esta infração.</span>;
  const col = (cls: string, label: string, content: ReactNode) => (
    <div className={"fp-col " + cls}>
      <div className="fp-col-h">
        <span className="cd" />
        {label}
      </div>
      <div className="fp-col-b">{content || na}</div>
    </div>
  );
  return (
    <div className="fp-scrim" onClick={onClose}>
      <div className="fp-shell" onClick={(e) => e.stopPropagation()}>
        <div className="fp-card">
          <div className="fp-hd">
            <button className="fp-x" onClick={onClose}>
              <I.x w={16} />
            </button>
            <span className="fp-eyebrow">
              <I.regras w={13} />
              Ficha de procedimento
            </span>
            <div className="fp-tags">
              <span
                className="fp-code"
                style={{ color: m.color, background: m.bg, boxShadow: `inset 0 0 0 1px ${m.ring}` }}
              >
                {enquad.ctb || r.codigo}
              </span>
              <span
                className="fp-grav"
                style={{ color: m.color, background: m.bg, boxShadow: `inset 0 0 0 1px ${m.ring}` }}
              >
                <span className="gd" style={{ background: m.color }} />
                {m.label}
              </span>
              <span className="fp-peso">
                peso <b style={{ color: m.color }}>{PTS_OF[r.grav] || r.pontos}</b>
              </span>
            </div>
            <h2 className="fp-name">{r.nome}</h2>
          </div>
          <div className="fp-bd">
            <div>
              <div className="fp-sec-l">Categorias habilitadas</div>
              <div className="fp-cats">
                {cat.map((c, i) => (
                  <span className="fp-cat" key={i}>
                    {c}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <div className="fp-sec-l">Descrição</div>
              <p className="fp-text">{r.desc || na}</p>
            </div>
            <div>
              <div className="fp-sec-l">
                <I.target w={13} />
                Constatação da infração
              </div>
              <p className="fp-text">{constat}</p>
            </div>
            <div>
              <div className="fp-sec-l">Condutas e procedimentos</div>
              <div className="fp-cols">
                {col("pontua", "Condutas que pontuam", r.pontua || r.checks || null)}
                {col("nao", "Condutas que não pontuam", r.naoPontua)}
                {col("def", "Definições e procedimentos", r.definicoes)}
              </div>
            </div>
            {r.compl && (
              <div className="fp-compl">
                <div className="fp-sec-l">Informações complementares</div>
                <p className="fp-text">{r.compl}</p>
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, paddingTop: 2 }}>
              <button className="btn" onClick={onClose}>
                Fechar
              </button>
              {onEdit && (
                <button className="btn btn-primary" onClick={() => onEdit(r)}>
                  <I.edit w={15} />
                  Editar infração
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface RegraModalProps {
  mode: "new" | "edit";
  rule: Rule;
  onSave: (r: Rule) => void;
  onClose: () => void;
}
function RegraModal({ mode, rule, onSave, onClose }: RegraModalProps) {
  const M = META_GRAV as Record<string, GravMeta>;
  const [r, setR] = useState<Rule>(rule);
  const set = (k: keyof Rule, v: unknown) => setR((x) => ({ ...x, [k]: v }));
  const pickGrav = (g: Grav) => setR((x) => ({ ...x, grav: g, pontos: M[g].pontos }));
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="modal" style={{ width: 540 }}>
        <div style={{ padding: "20px 22px 0" }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: ".08em",
              textTransform: "uppercase",
              color: "var(--brand)",
              fontWeight: 700,
            }}
          >
            {mode === "new" ? "Nova infração" : "Editar infração"}
          </div>
          <div style={{ fontSize: 18, fontWeight: 800, marginTop: 3 }}>{r.codigo || "Cadastro"}</div>
        </div>
        <div style={{ padding: "18px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="fld">
            <label className="fld-l">Natureza</label>
            <div className="grid g-4" style={{ gap: 6 }}>
              {NAT_ASC.map((g) => (
                <button
                  key={g}
                  type="button"
                  onClick={() => pickGrav(g)}
                  style={{
                    padding: "9px 4px",
                    borderRadius: 10,
                    border: "1px solid " + (r.grav === g ? "transparent" : "var(--border-strong)"),
                    boxShadow: r.grav === g ? `inset 0 0 0 1.5px ${M[g].color}` : "none",
                    background: r.grav === g ? M[g].bg : "var(--surface)",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 2,
                  } as CSSProperties}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: r.grav === g ? M[g].color : "var(--ink)",
                    }}
                  >
                    {M[g].label}
                  </span>
                  <span className="mono" style={{ fontSize: 11, color: "var(--muted)" }}>
                    {M[g].pontos} pt
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="fld">
            <label className="fld-l">Descrição da infração</label>
            <textarea
              rows={2}
              value={r.nome}
              onChange={(e) => set("nome", e.target.value)}
              placeholder="Ex.: Avançar o sinal vermelho do semáforo…"
            />
          </div>
          <div className="fld-row">
            <div className="fld">
              <label className="fld-l">Código / Artigo CTB</label>
              <input
                className="mono"
                value={r.codigo}
                onChange={(e) => {
                  const v = e.target.value;
                  setR((x) => ({
                    ...x,
                    codigo: v,
                    code: v,
                    ctb: "CTB " + v,
                    enquad: { ...(x.enquad || {}), ctb: "CTB " + v },
                  }));
                }}
                placeholder="Art. 208"
              />
            </div>
            <div className="fld">
              <label className="fld-l">Peso</label>
              <input
                className="mono"
                type="number"
                value={r.pontos}
                onChange={(e) => set("pontos", +e.target.value)}
              />
            </div>
          </div>
          <div className="fld">
            <label className="fld-l">Definição normativa</label>
            <textarea
              rows={2}
              value={(r.desc as string) || ""}
              onChange={(e) => set("desc", e.target.value)}
              placeholder="Texto da ficha de avaliação…"
            />
          </div>
        </div>
        <div className="drawer-f" style={{ borderRadius: "0 0 var(--r-xl) var(--r-xl)" }}>
          <button className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="btn btn-primary"
            onClick={() =>
              onSave({
                ...r,
                ctb: r.ctb || "CTB " + r.codigo,
                enquad: { ...(r.enquad || {}), ctb: r.ctb || "CTB " + r.codigo },
              })
            }
            disabled={!r.nome || !r.codigo}
          >
            {mode === "new" ? "Adicionar" : "Salvar"}
          </button>
        </div>
      </div>
    </>
  );
}
