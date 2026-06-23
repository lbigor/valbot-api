/* ============================================================================
   Painel — Matriz Nacional de Regras (catálogo de infrações) · porte de painel-bin.jsx
   Rail lateral que lista as infrações que o revisor adiciona ao laudo.
   (Componente disponível; o shell atual usa o FaultPicker do Inspector.)
   ============================================================================ */
import { useState, Fragment } from "react";
import { VB, gravColor } from "@/system/painel-data";
import type { Rule, MarkRef, Grav } from "@/system/painel-data";
import { I } from "./painelIcons";

const GRAV_ORDER: Grav[] = ["gravissima", "grave", "media", "leve"];
const GRAV_LABEL: Record<Grav, string> = { gravissima: "Gravíssimas", grave: "Graves", media: "Médias", leve: "Leves" };

interface RuleCardProps {
  r: Rule; added: boolean; suggested: boolean; onAdd: (code: string) => void; onShow: (r: Rule) => void;
}
function RuleCard({ r, added, suggested, onAdd, onShow }: RuleCardProps) {
  const tk = { color: gravColor(r.grav), bg: "color-mix(in oklab," + gravColor(r.grav) + ", transparent 84%)" };
  const ptsLbl = r.pontos == null ? "Eliminatória" : r.pontos + (r.pontos === 1 ? " pt" : " pts");
  return (
    <div className={"rule-card" + (added ? " added" : "") + (suggested ? " sug" : "")}>
      <button className="rc-main" onClick={() => onShow(r)} title={r.desc}>
        <div className="rc-top">
          <span className="rc-code mono" style={{ color: tk.color, background: tk.bg }}>{r.code}</span>
          {suggested && <span className="rc-sug">sugerida</span>}
          <span className="rc-pts mono" style={{ color: tk.color, marginLeft: "auto" }}>{ptsLbl}</span>
        </div>
        <div className="rc-name">{r.nome}</div>
        <div className="rc-norm mono">{r.enquad.ctb} · {r.enquad.mbedv}</div>
      </button>
      <button className={"rc-add" + (added ? " on" : "")} onClick={() => onAdd(r.code)} title={added ? "Já no laudo" : "Adicionar ao laudo no tempo atual"}>
        {added ? <Fragment><I.check width="13" height="13" />no laudo</Fragment> : <Fragment><span className="rc-plus">+</span>laudo</Fragment>}
      </button>
    </div>
  );
}

interface MatrizRailProps {
  laudo: MarkRef[]; onAdd: (code: string) => void; onShowRule: (r: Rule) => void; suggestSet?: Set<string>;
}
export function MatrizRail({ laudo, onAdd, onShowRule, suggestSet }: MatrizRailProps) {
  const [q, setQ] = useState("");
  const [g, setG] = useState("todas");
  const laudoHas = new Set(laudo.map((l) => l.code));
  const chips = [
    { k: "todas", label: "Todas", n: VB.rules.length },
    { k: "gravissima", label: "Gravíssimas", n: VB.rules.filter((r) => r.grav === "gravissima").length },
    { k: "grave", label: "Graves", n: VB.rules.filter((r) => r.grav === "grave").length },
    { k: "media", label: "Médias", n: VB.rules.filter((r) => r.grav === "media").length },
    { k: "leve", label: "Leves", n: VB.rules.filter((r) => r.grav === "leve").length },
  ];
  const filtered = VB.rules.filter((r) =>
    (g === "todas" || r.grav === g) &&
    (!q || (r.nome + r.code + r.enquad.ctb + r.enquad.mbedv).toLowerCase().includes(q.toLowerCase()))
  );
  const groups = GRAV_ORDER.map((gr) => ({ gr, items: filtered.filter((r) => r.grav === gr) })).filter((x) => x.items.length);

  return (
    <div className="ppane bin">
      <div className="pane-head">
        <I.rules width="14" height="14" />
        <span className="ph-title">Matriz Nacional de Regras</span>
        <span className="ph-count mono">{filtered.length}</span>
      </div>
      <div className="matriz-norm">Infrações vinculadas · CTB · Res. 1.020/2025 · MBEDV</div>
      <div className="bin-search">
        <I.search /><input placeholder="Buscar infração, código ou artigo…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="bin-filters">
        {chips.map((c) => (
          <button key={c.k} className={"bin-chip" + (g === c.k ? " on" : "")} onClick={() => setG(c.k)}>
            {c.label}<span className="n mono">{c.n}</span>
          </button>
        ))}
      </div>
      <div className="bin-list">
        {groups.map(({ gr, items }) => (
          <Fragment key={gr}>
            <div className="rail-group"><span className="rg-led" style={{ background: gravColor(gr) }} />{GRAV_LABEL[gr]}<span className="rg-n mono">{items.length}</span></div>
            {items.map((r) => (
              <RuleCard key={r.code} r={r} added={laudoHas.has(r.code)} suggested={!!suggestSet && suggestSet.has(r.code) && !laudoHas.has(r.code)} onAdd={onAdd} onShow={onShowRule} />
            ))}
          </Fragment>
        ))}
        {!filtered.length && <div style={{ textAlign: "center", color: "var(--faint)", fontSize: 12.5, padding: "30px 0" }}>Nenhuma infração encontrada.</div>}
      </div>
    </div>
  );
}

export default MatrizRail;
