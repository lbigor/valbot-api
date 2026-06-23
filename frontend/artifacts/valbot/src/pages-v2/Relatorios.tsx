/* ============================================================================
   ValBot — Relatórios · confronto entre resultado oficial e o calculado pelo Val
   Espelha a tela "Relatório de resultado" de produção (filtros + tabela + export).
   Religado aos endpoints reais do backend (sem mock):
     GET /api/relatorios/resultados?dias=&unidade=&examinador=&resultado=&categoria=&page=&page_size=
     GET /api/exams/{hash}/laudo-json   → 14 blocos (§14.2) — drawer Resumo/JSON
     GET /api/exams/{hash}/laudo-pdf    → nova aba
     GET /api/relatorios/export.csv?... → CSV (mesmos filtros)
     GET /api/relatorios/consolidado?hashes=  → PDF consolidado
   Layout pixel-perfect preservado (.flt/.tbl/.drawer/.scrim/.tabs/.json-view/.badge/.bar).
   ============================================================================ */
import { useState, useMemo, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/system/Shell";
import { I } from "@/system/icons";
import { fmt } from "@/system/ui";

/* ---- Labels/cores (taxonomia 1.020/2025) — constantes locais, NÃO são mock de negócio ---- */
const TIPO_DIV_LABEL: Record<string, string> = {
  "1_resultado": "Resultado",
  "2_pontuacao": "Pontuação",
  "3_infracao": "Infração",
  "4_enquadramento": "Enquadramento",
  "5_evidencia_insuficiente": "Evidência insuficiente",
};
interface GravMeta {
  label: string;
  pontos: number;
  color: string;
  bg: string;
  ring: string;
}
const META_GRAV: Record<string, GravMeta> = {
  gravissima: { label: "Gravíssima", pontos: 6, color: "#BE123C", bg: "#FCEAEF", ring: "#F3C2CF" },
  grave: { label: "Grave", pontos: 4, color: "#B45309", bg: "#FBF1E3", ring: "#F0D9B3" },
  media: { label: "Média", pontos: 2, color: "#1D4ED8", bg: "#E7EEFD", ring: "#C5D6F8" },
  leve: { label: "Leve", pontos: 1, color: "#6B7689", bg: "#F1F4F9", ring: "#E5E9F0" },
};

/* ---- Contrato GET /api/relatorios/resultados (item) ---- */
interface ResultadoItem {
  hash: string;
  candidato_nome?: string;
  candidato?: string; // cpf mascarado
  renach?: string;
  unidade?: string;
  examinador?: string;
  categoria?: string;
  resultado_exame?: string | null; // oficial (A/R/N)
  resultado_calculado?: string | null; // Val (A/R/N)
  pontuacao_total?: number | null;
  pontuacao_oficial?: number | null;
  pontuacao_calculada?: number | null;
  tipo_divergencia?: string | null;
  data_hora_exame?: string | null;
  num_infracoes?: number | null;
  created_at?: string | null;
  [k: string]: unknown;
}
interface ResultadosPage {
  items: ResultadoItem[];
  total: number;
  pages: number;
  page: number;
  page_size: number;
}

/* Shape que a tela consome (espelha o antigo `Exame` do mock, só os campos usados) */
interface Exame {
  hash: string;
  candidato_nome: string;
  candidato_cpf: string;
  renach: string;
  unidade: string;
  examinador: string;
  categoria: string;
  resultado_oficial: string | null;
  resultado_calculado: string | null;
  pontuacao_total: number | null;
  pontuacao_oficial: number | null;
  diverge: boolean;
  tipo_divergencia: string | null;
  num_infracoes: number;
  created_at: string | null;
  __json?: boolean;
}

/* item do endpoint → shape da tela */
function toExame(it: ResultadoItem): Exame {
  const td = it.tipo_divergencia ?? null;
  return {
    hash: it.hash,
    candidato_nome: it.candidato_nome || "—",
    candidato_cpf: it.candidato || "",
    renach: it.renach || "—",
    unidade: it.unidade || "—",
    examinador: it.examinador || "—",
    categoria: it.categoria || "—",
    resultado_oficial: it.resultado_exame ?? null,
    resultado_calculado: it.resultado_calculado ?? null,
    pontuacao_total:
      it.pontuacao_calculada != null ? it.pontuacao_calculada : (it.pontuacao_total ?? null),
    pontuacao_oficial: it.pontuacao_oficial ?? null,
    diverge: td != null && td !== "" && td !== "sem_divergencia",
    tipo_divergencia: td,
    num_infracoes: it.num_infracoes ?? 0,
    created_at: it.data_hora_exame || it.created_at || null,
  };
}

function buildParams(f: {
  periodo: string;
  unidade: string;
  examinador: string;
  resultado: string;
  categoria: string;
}): URLSearchParams {
  const p = new URLSearchParams();
  if (f.periodo) p.set("dias", f.periodo);
  if (f.unidade) p.set("unidade", f.unidade);
  if (f.examinador) p.set("examinador", f.examinador);
  // tela usa apto/reprovado/divergente → traduz pro contrato (A/R; divergente filtra cliente)
  if (f.resultado === "apto") p.set("resultado", "A");
  else if (f.resultado === "reprovado") p.set("resultado", "R");
  if (f.categoria) p.set("categoria", f.categoria);
  return p;
}

async function fetchResultados(
  f: { periodo: string; unidade: string; examinador: string; resultado: string; categoria: string },
  page: number,
  pageSize: number,
): Promise<ResultadosPage> {
  const p = buildParams(f);
  p.set("page", String(page));
  p.set("page_size", String(pageSize));
  const r = await fetch(`/api/relatorios/resultados?${p.toString()}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const data = await r.json();
  const items = (Array.isArray(data) ? data : (data?.items ?? [])) as ResultadoItem[];
  return {
    items,
    total: typeof data?.total === "number" ? data.total : items.length,
    pages: typeof data?.pages === "number" ? data.pages : 1,
    page: typeof data?.page === "number" ? data.page : page,
    page_size: typeof data?.page_size === "number" ? data.page_size : pageSize,
  };
}

function abrirNovaAba(url: string) {
  window.open(url, "_blank", "noopener,noreferrer");
}

/* ============================================================================
   Visualizador de laudo em TELA CHEIA — "explode" o PDF dentro do app.
   Overlay full-screen, fundo escurecido, <iframe> carregando
   /api/exams/{hash}/laudo-pdf (usa a sessão do cookie automaticamente).
   Cabeçalho com identificação + Imprimir / Baixar / Fechar (X).
   Fecha com Esc e com clique no fundo. Animação rápida de scale/opacity.
   ============================================================================ */
function pdfUrl(hash: string): string {
  return `/api/exams/${encodeURIComponent(hash)}/laudo-pdf`;
}

interface LaudoPdfViewerProps {
  hash: string;
  identificador: string; // ex.: "Fulano · RENACH 123 · hash abc"
  onClose: () => void;
}
function LaudoPdfViewer({ hash, identificador, onClose }: LaudoPdfViewerProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [shown, setShown] = useState(false);
  const url = pdfUrl(hash);

  // dispara a transição de "explodir" no próximo frame + Esc fecha + trava scroll
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(true));
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      cancelAnimationFrame(id);
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  const imprimir = () => {
    try {
      const w = iframeRef.current?.contentWindow;
      if (w) {
        w.focus();
        w.print();
        return;
      }
    } catch (x) {
      /* cross-origin / não pronto → fallback abre em nova aba para imprimir */
    }
    abrirNovaAba(url);
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 90,
        background: "rgba(12,18,32,.62)",
        backdropFilter: "blur(4px)",
        display: "flex",
        flexDirection: "column",
        padding: "clamp(12px, 2.5vh, 28px)",
        animation: "fade .16s ease",
      }}
    >
      <div
        onClick={(ev) => ev.stopPropagation()}
        style={{
          flex: 1,
          minHeight: 0,
          width: "min(1100px, 100%)",
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
          background: "var(--surface)",
          borderRadius: "var(--r-xl)",
          boxShadow: "var(--shadow-lg)",
          overflow: "hidden",
          transformOrigin: "center",
          opacity: shown ? 1 : 0,
          transform: shown ? "scale(1)" : "scale(.92)",
          transition: "opacity .22s cubic-bezier(.2,.7,.3,1), transform .22s cubic-bezier(.2,.7,.3,1)",
        }}
      >
        {/* cabeçalho */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "14px 18px",
            borderBottom: "1px solid var(--border)",
            background: "var(--surface-2)",
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 11,
                letterSpacing: ".08em",
                textTransform: "uppercase",
                color: "var(--brand)",
                fontWeight: 700,
              }}
            >
              Laudo oficial
            </div>
            <div
              className="t-strong"
              style={{
                fontSize: 14.5,
                fontWeight: 700,
                marginTop: 2,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {identificador}
            </div>
          </div>
          <span className="spacer" style={{ flex: 1 }} />
          <button className="btn btn-sm btn-primary" onClick={imprimir} title="Imprimir laudo">
            <I.pdf w={15} />
            Imprimir
          </button>
          <a
            className="btn btn-sm"
            href={url}
            download={`laudo_${hash}.pdf`}
            title="Baixar PDF"
            style={{ textDecoration: "none" }}
          >
            <I.download w={15} />
            Baixar
          </a>
          <a
            className="btn btn-sm"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            title="Abrir em nova aba (caso o documento não apareça abaixo)"
            style={{ textDecoration: "none" }}
          >
            Nova aba
          </a>
          <button className="icon-btn" style={{ width: 36, height: 36 }} onClick={onClose} title="Fechar (Esc)">
            <I.x w={16} />
          </button>
        </div>
        {/* documento — exibe o PDF inline (backend manda Content-Disposition: inline) */}
        <iframe
          ref={iframeRef}
          src={url}
          title={`Laudo ${hash}`}
          style={{ flex: 1, width: "100%", border: "none", background: "#525659" }}
        />
      </div>
    </div>
  );
}

/* exame com possível flag de abertura direta no JSON */
type SelExame = Exame;

export default function Relatorios() {
  const [periodo, setPeriodo] = useState("30");
  const [unidade, setUnidade] = useState("");
  const [examinador, setExaminador] = useState("");
  const [resultado, setResultado] = useState("");
  const [categoria, setCategoria] = useState("");
  const [page, setPage] = useState(0);
  const [sel, setSel] = useState<SelExame | null>(null);
  const [pdfExame, setPdfExame] = useState<Exame | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const flash = (msg: string) => {
    setToast(msg);
    clearTimeout((window as any).__t);
    (window as any).__t = setTimeout(() => setToast(null), 1800);
  };
  const PER = 12;

  const filtros = { periodo, unidade, examinador, resultado, categoria };
  const { data, isLoading, isError } = useQuery({
    queryKey: ["v2-relatorios", filtros, page],
    queryFn: () => fetchResultados(filtros, page + 1, PER),
    retry: false,
  });

  const allItems = useMemo(() => (data?.items ?? []).map(toExame), [data]);
  // "Com divergência" não tem filtro de servidor → aplica no cliente sobre a página
  const pageItems = useMemo(
    () => (resultado === "divergente" ? allItems.filter((e) => e.diverge) : allItems),
    [allItems, resultado],
  );
  const total = data?.total ?? pageItems.length;
  const totalPages = data?.pages ?? 1;
  const divergentes = pageItems.filter((e) => e.diverge).length;

  // opções de filtro derivadas (distinct) dos resultados retornados
  const UNIDADES = useMemo(
    () => Array.from(new Set(allItems.map((e) => e.unidade).filter((v) => v && v !== "—"))).sort(),
    [allItems],
  );
  const EXAMINADORES = useMemo(
    () =>
      Array.from(new Set(allItems.map((e) => e.examinador).filter((v) => v && v !== "—"))).sort(),
    [allItems],
  );
  const CATEGORIAS = useMemo(
    () => Array.from(new Set(allItems.map((e) => e.categoria).filter((v) => v && v !== "—"))).sort(),
    [allItems],
  );

  const resetPage =
    (fn: (v: string) => void) =>
    (v: string) => {
      fn(v);
      setPage(0);
    };

  function exportarCsv() {
    abrirNovaAba(`/api/relatorios/export.csv?${buildParams(filtros).toString()}`);
  }
  function pdfConsolidado() {
    const hashes = pageItems.map((e) => e.hash);
    if (!hashes.length) return;
    abrirNovaAba(`/api/relatorios/consolidado?hashes=${encodeURIComponent(hashes.join(","))}`);
  }

  interface SelProps {
    label: string;
    value: string;
    onChange: (v: string) => void;
    opts: (string | { v: string; l: string })[];
    all: string;
  }
  const Sel = ({ label, value, onChange, opts, all }: SelProps) => (
    <div className="flt">
      <label>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{all}</option>
        {opts.map((o) => {
          const v = typeof o === "object" ? o.v : o;
          const l = typeof o === "object" ? o.l : o;
          return (
            <option key={v} value={v}>
              {l}
            </option>
          );
        })}
      </select>
    </div>
  );

  return (
    <Shell
      active="relatorios"
      title="Relatórios"
      sub="Confronto entre o resultado oficial e o resultado calculado pelo Val"
    >
      {/* filtros */}
      <div className="panel">
        <div
          className="panel-b"
          style={{ display: "flex", gap: 14, alignItems: "flex-end", flexWrap: "wrap" }}
        >
          <Sel
            label="Período"
            value={periodo}
            onChange={resetPage(setPeriodo)}
            all="30 dias"
            opts={[
              { v: "7", l: "7 dias" },
              { v: "30", l: "30 dias" },
              { v: "90", l: "90 dias" },
            ]}
          />
          <Sel
            label="Unidade"
            value={unidade}
            onChange={resetPage(setUnidade)}
            all="Todas"
            opts={UNIDADES}
          />
          <Sel
            label="Examinador"
            value={examinador}
            onChange={resetPage(setExaminador)}
            all="Todos"
            opts={EXAMINADORES}
          />
          <Sel
            label="Resultado"
            value={resultado}
            onChange={resetPage(setResultado)}
            all="Todos"
            opts={[
              { v: "apto", l: "Apto" },
              { v: "reprovado", l: "Reprovado" },
              { v: "divergente", l: "Com divergência" },
            ]}
          />
          <Sel
            label="Categoria"
            value={categoria}
            onChange={resetPage(setCategoria)}
            all="Todas"
            opts={CATEGORIAS}
          />
          <button className="btn">
            <I.filter w={16} />
            Aplicar
          </button>
        </div>
      </div>

      {/* barra de resultado */}
      <div className="row wrap" style={{ margin: "16px 0 14px" }}>
        <span style={{ fontSize: 14 }}>
          <b className="mono">{fmt.int(total)}</b> exame(s) · pág. {page + 1}/{totalPages}
        </span>
        {divergentes > 0 && (
          <span className="badge warn">
            <I.alert w={13} />
            {divergentes} divergência(s)
          </span>
        )}
        <span className="spacer" />
        <button className="btn btn-sm" onClick={pdfConsolidado}>
          <I.pdf w={15} />
          PDF consolidado
        </button>
        <button className="btn btn-sm" onClick={exportarCsv}>
          <I.download w={15} />
          Exportar CSV
        </button>
      </div>

      {/* tabela */}
      <div className="tbl-wrap">
        <div className="tbl-scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Candidato</th>
                <th>Data</th>
                <th>Unidade</th>
                <th>Oficial</th>
                <th>Val</th>
                <th>Divergência</th>
                <th>Acessos</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={8} className="t-sub" style={{ padding: "18px 14px" }}>
                    Carregando…
                  </td>
                </tr>
              )}
              {isError && !isLoading && (
                <tr>
                  <td colSpan={8} className="t-sub" style={{ padding: "18px 14px" }}>
                    Não foi possível carregar os resultados.
                  </td>
                </tr>
              )}
              {!isLoading && !isError && pageItems.length === 0 && (
                <tr>
                  <td colSpan={8} className="t-sub" style={{ padding: "18px 14px" }}>
                    Nenhum exame no período/filtros.
                  </td>
                </tr>
              )}
              {!isLoading &&
                !isError &&
                pageItems.map((e) => (
                  <tr
                    key={e.hash}
                    className="clickable"
                    title="Ver laudo e JSON"
                    onClick={() => setSel(e)}
                  >
                    <td>
                      <div className="t-strong">{e.candidato_nome}</div>
                      <div className="mono t-sub">{e.renach}</div>
                    </td>
                    <td className="t-sub mono" style={{ whiteSpace: "nowrap" }}>
                      {fmt.dmyhm(e.created_at)}
                    </td>
                    <td>
                      <div className="t-strong" style={{ fontWeight: 600 }}>
                        {e.unidade}
                      </div>
                      <div className="t-sub">
                        Cat {e.categoria} · {e.examinador}
                      </div>
                    </td>
                    <td>
                      <ResCell c={e.resultado_oficial} />
                    </td>
                    <td>
                      <ResCell
                        c={e.resultado_calculado}
                        pts={e.resultado_calculado ? e.pontuacao_total : null}
                      />
                    </td>
                    <td>
                      {e.diverge ? (
                        <span className="badge warn">
                          <span className="bd" />
                          {TIPO_DIV_LABEL[e.tipo_divergencia!] ?? e.tipo_divergencia}
                        </span>
                      ) : (
                        <span className="badge ok">
                          <I.check w={13} />
                          OK
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="faint">—</span>
                    </td>
                    <td>
                      <div
                        className="row"
                        style={{ gap: 4, justifyContent: "flex-end" }}
                        onClick={(ev) => ev.stopPropagation()}
                      >
                        <button
                          className="icon-btn"
                          style={{ width: 32, height: 32 }}
                          title="Ver laudo (PDF em tela cheia)"
                          onClick={() => setPdfExame(e)}
                        >
                          <I.pdf w={15} />
                        </button>
                        <button
                          className="icon-btn"
                          style={{ width: 32, height: 32 }}
                          title="Laudo explicável (resumo)"
                          onClick={() => setSel(e)}
                        >
                          <I.relatorios w={15} />
                        </button>
                        <button
                          className="icon-btn"
                          style={{ width: 32, height: 32 }}
                          title="Ver JSON"
                          onClick={() => setSel({ ...e, __json: true })}
                        >
                          <span className="mono" style={{ fontSize: 12, fontWeight: 700 }}>
                            {"{}"}
                          </span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="tbl-foot">
          <span>
            Exibindo {pageItems.length ? page * PER + 1 : 0}–{page * PER + pageItems.length} de{" "}
            {fmt.int(total)}
          </span>
          <span className="spacer" />
          <button
            className="btn btn-sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Anterior
          </button>
          <button
            className="btn btn-sm"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
          >
            Próxima
          </button>
        </div>
      </div>
      {sel && (
        <LaudoDrawer
          e={sel}
          jsonFirst={!!sel.__json}
          onClose={() => setSel(null)}
          onCopy={() => flash("JSON copiado")}
          onPdf={() => {
            // abre o visualizador full-screen e fecha o drawer (evita overlay duplo
            // e o re-lock de body.overflow ao fechar o PDF por cima do drawer)
            setPdfExame(sel);
            setSel(null);
          }}
        />
      )}
      {pdfExame && (
        <LaudoPdfViewer
          hash={pdfExame.hash}
          identificador={`${pdfExame.candidato_nome} · ${pdfExame.renach} · hash ${pdfExame.hash}`}
          onClose={() => setPdfExame(null)}
        />
      )}
      {toast && <div className="toast">{toast}</div>}
    </Shell>
  );
}

/* ---- Laudo real: GET /api/exams/{hash}/laudo-json (14 blocos §14.2) ---- */
interface LaudoJson {
  exame_hash?: string;
  laudo_versao?: string;
  emitido_em?: string;
  fonte?: string;
  blocos?: Record<string, unknown>;
  [k: string]: unknown;
}

const BLOCO_TITULOS: Record<string, string> = {
  "1_identificacao": "Identificação",
  "2_candidato": "Candidato",
  "3_examinador": "Examinador",
  "4_resultado_oficial": "Resultado oficial",
  "5_resultado_calculado": "Resultado calculado (Val)",
  "6_cobertura": "Cobertura da análise",
  "7_analise_detalhada": "Análise detalhada (infrações)",
  "8_divergencia": "Divergência",
  "9_comite_ia": "Comitê de IA",
  "10_parecer_auditor": "Parecer do auditor",
  "11_decisao_supervisor": "Decisão do supervisor",
  "12_eventos_os": "Trilha de auditoria / Eventos",
  "13_envio_unidade_gestora": "Envio à unidade gestora",
  "14_integridade": "Integridade",
};

async function fetchLaudo(hash: string): Promise<LaudoJson> {
  const r = await fetch(`/api/exams/${encodeURIComponent(hash)}/laudo-json`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<LaudoJson>;
}

// JSON inicial do init_upload — payload que o integrador (TechPrático) enviou no
// POST, reconstruído pelo backend a partir do upload.json. Exibido no drawer de
// laudo (view JSON) sob o grupo `init_upload`.
async function fetchInitUpload(hash: string): Promise<Record<string, unknown>> {
  const r = await fetch(`/api/exams/${encodeURIComponent(hash)}/init-upload`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<Record<string, unknown>>;
}

function hlJson(obj: unknown): { __html: string } {
  let s = JSON.stringify(obj, null, 2);
  s = s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  s = s.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false)\b|\bnull\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (m) => {
      let cls = "j-num";
      if (/^"/.test(m)) cls = /:$/.test(m) ? "j-key" : "j-str";
      else if (/true|false/.test(m)) cls = "j-bool";
      else if (/null/.test(m)) cls = "j-null";
      return '<span class="' + cls + '">' + m + "</span>";
    },
  );
  return { __html: s };
}

/* helpers de leitura tolerante dos blocos */
function bloco(laudo: LaudoJson | undefined, key: string): Record<string, unknown> {
  const b = laudo?.blocos?.[key];
  return b && typeof b === "object" && !Array.isArray(b) ? (b as Record<string, unknown>) : {};
}
function asStr(v: unknown): string | null {
  if (v == null || v === "") return null;
  return String(v);
}
function asNum(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return isNaN(n) ? null : n;
}

interface LaudoDrawerProps {
  e: Exame;
  jsonFirst: boolean;
  onClose: () => void;
  onCopy?: () => void;
  onPdf?: () => void;
}
function LaudoDrawer({ e, jsonFirst, onClose, onCopy, onPdf }: LaudoDrawerProps) {
  const [view, setView] = useState<"resumo" | "acessos" | "json">(jsonFirst ? "json" : "resumo");
  const { data: laudo, isLoading, isError } = useQuery({
    queryKey: ["v2-laudo", e.hash],
    queryFn: () => fetchLaudo(e.hash),
    retry: false,
  });
  // JSON inicial do init_upload (payload original do integrador). Carregado em
  // paralelo; ausência não quebra o laudo (grupo só entra no JSON quando há dados).
  const { data: initUpload } = useQuery({
    queryKey: ["v2-init-upload", e.hash],
    queryFn: () => fetchInitUpload(e.hash),
    retry: false,
  });
  // Laudo + grupo init_upload, na ordem exibida/baixada na view JSON.
  const laudoComInit = initUpload
    ? { ...(laudo ?? {}), init_upload: initUpload }
    : laudo ?? {};

  const copy = () => {
    try {
      navigator.clipboard.writeText(JSON.stringify(laudoComInit, null, 2));
    } catch (x) {
      /* noop */
    }
    onCopy && onCopy();
  };
  const baixarJson = () => {
    const blob = new Blob([JSON.stringify(laudoComInit, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "laudo_" + e.hash + ".json";
    a.click();
    URL.revokeObjectURL(a.href);
  };
  // "Imprimir laudo" agora EXPLODE o PDF na tela (visualizador full-screen);
  // sem visualizador disponível, cai no fallback de abrir em nova aba.
  const baixarPdf = () => (onPdf ? onPdf() : abrirNovaAba(pdfUrl(e.hash)));

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="drawer" style={{ width: 600 }}>
        <div className="drawer-h">
          <div>
            <div
              style={{
                fontSize: 11,
                letterSpacing: ".08em",
                textTransform: "uppercase",
                color: "var(--brand)",
                fontWeight: 700,
              }}
            >
              Laudo explícavel
            </div>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 800,
                margin: "3px 0 0",
                letterSpacing: "-.02em",
              }}
            >
              {e.candidato_nome}
            </h2>
            <div className="mono t-sub" style={{ marginTop: 2 }}>
              {e.renach} · hash {e.hash}
            </div>
          </div>
          <button className="icon-btn spacer" onClick={onClose}>
            <I.x w={16} />
          </button>
        </div>
        <div
          style={{
            padding: "12px 22px",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div className="tabs">
            <button className={view === "resumo" ? "on" : ""} onClick={() => setView("resumo")}>
              Resumo
            </button>
            <button className={view === "acessos" ? "on" : ""} onClick={() => setView("acessos")}>
              Acessos
            </button>
            <button className={view === "json" ? "on" : ""} onClick={() => setView("json")}>
              JSON
            </button>
          </div>
          <span className="spacer" />
          <button className="btn btn-sm" onClick={baixarPdf} title="Abrir laudo em tela cheia">
            <I.pdf w={14} />
            Imprimir laudo
          </button>
          {view === "json" && (
            <>
              <button className="btn btn-sm" onClick={copy}>
                Copiar
              </button>
              <button className="btn btn-sm" onClick={baixarJson}>
                <I.download w={14} />
                Baixar
              </button>
            </>
          )}
        </div>
        <div className="drawer-b">
          {isLoading ? (
            <div className="t-sub" style={{ padding: "8px 0" }}>
              Carregando laudo…
            </div>
          ) : isError ? (
            <div className="t-sub" style={{ padding: "8px 0" }}>
              Não foi possível carregar o laudo deste exame.
            </div>
          ) : view === "resumo" ? (
            <ResumoTab e={e} laudo={laudo} />
          ) : view === "acessos" ? (
            <AcessosTab laudo={laudo} />
          ) : (
            <pre className="json-view" dangerouslySetInnerHTML={hlJson(laudoComInit)} />
          )}
        </div>
      </div>
    </>
  );
}

/* Resumo derivado dos blocos reais do laudo-json (§14.2) */
function ResumoTab({ e, laudo }: { e: Exame; laudo: LaudoJson | undefined }) {
  const oficial = bloco(laudo, "4_resultado_oficial");
  const calc = bloco(laudo, "5_resultado_calculado");
  const div = bloco(laudo, "8_divergencia");
  const analise = laudo?.blocos?.["7_analise_detalhada"];
  const infracoes = useMemo<Record<string, unknown>[]>(() => {
    if (Array.isArray(analise)) return analise as Record<string, unknown>[];
    if (analise && typeof analise === "object") {
      const inf = (analise as Record<string, unknown>).infracoes;
      if (Array.isArray(inf)) return inf as Record<string, unknown>[];
    }
    return [];
  }, [analise]);

  const decisaoOficial = asStr(oficial.decisao) ?? asStr(oficial.resultado);
  const decisaoCalc = asStr(calc.decisao) ?? asStr(calc.resultado);
  const codFromDec = (d: string | null): string | null => {
    if (!d) return null;
    const x = d.toLowerCase();
    if (x.includes("aprov") || x === "a" || x === "apto") return "A";
    if (x.includes("reprov") || x === "r" || x === "inapto") return "R";
    if (x.includes("nao") || x.includes("não") || x === "n") return "N";
    return d.length === 1 ? d.toUpperCase() : null;
  };
  const resOficial = e.resultado_oficial ?? codFromDec(decisaoOficial);
  const resCalc = e.resultado_calculado ?? codFromDec(decisaoCalc);

  const ptsOficial =
    asNum(oficial.pontuacao) ?? asNum(oficial.pontuacao_total) ?? e.pontuacao_oficial;
  const ptsCalc =
    asNum(calc.pontuacao_calculada) ?? asNum(calc.pontuacao) ?? e.pontuacao_total;

  const tipoDiv = asStr(div.tipo_divergencia) ?? e.tipo_divergencia;
  const diverge =
    tipoDiv != null && tipoDiv !== "" && tipoDiv !== "sem_divergencia" ? true : e.diverge;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="grid g-2">
        <ConfBox titulo="Resultado oficial" res={resOficial} pts={ptsOficial} sub="Comissão presencial" />
        <ConfBox
          titulo="Calculado pelo Val"
          res={resCalc}
          pts={ptsCalc}
          sub={asStr(calc.modelo) ?? "Val"}
        />
      </div>
      <div>
        <div className="section-title" style={{ margin: "0 0 8px" }}>
          Divergência
        </div>
        {diverge ? (
          <span className="badge warn">
            <span className="bd" />
            {(tipoDiv && TIPO_DIV_LABEL[tipoDiv]) ?? tipoDiv ?? "Divergência"}
          </span>
        ) : (
          <span className="badge ok">
            <I.check w={13} />
            Sem divergência · encerramento
          </span>
        )}
      </div>
      <div>
        <div className="section-title" style={{ margin: "0 0 8px" }}>
          Infrações calculadas ({infracoes.length})
        </div>
        {infracoes.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {infracoes.map((i, k) => {
              const grav = (asStr(i.gravidade) ?? asStr(i.natureza) ?? "leve").toLowerCase();
              const m = META_GRAV[grav] ?? META_GRAV.leve;
              const pontos = asNum(i.peso) ?? asNum(i.pontos) ?? m.pontos;
              const ts = asNum(i.timestamp_s) ?? asNum(i.timestamp);
              const conf = asNum(i.confianca);
              const baseLegal =
                asStr(i.artigo_ctb) ?? asStr(i.base_legal) ?? asStr(i.regra_aplicada) ?? "—";
              const desc = asStr(i.descricao) ?? asStr(i.nome) ?? baseLegal;
              return (
                <div
                  key={k}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "9px 12px",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--r)",
                  }}
                >
                  <span
                    style={{
                      display: "inline-grid",
                      placeItems: "center",
                      width: 28,
                      height: 28,
                      borderRadius: 8,
                      fontFamily: "var(--mono)",
                      fontWeight: 700,
                      fontSize: 13,
                      color: m.color,
                      background: m.bg,
                    }}
                  >
                    {pontos}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="t-strong" style={{ fontSize: 13 }}>
                      {desc}
                    </div>
                    <div className="mono t-sub">
                      {baseLegal}
                      {ts != null ? " · " + fmt.dur(ts) : ""}
                      {conf != null ? " · conf. " + (conf * 100).toFixed(0) + "%" : ""}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="t-sub">Nenhuma infração detectada.</div>
        )}
      </div>
    </div>
  );
}

/* Acessos ao vídeo — sem endpoint dedicado de telemetria por enquanto.
   Se o laudo trouxer eventos/trilha (bloco 12_eventos_os), exibe-os; senão, estado vazio. */
function AcessosTab({ laudo }: { laudo: LaudoJson | undefined }) {
  const eventosRaw = laudo?.blocos?.["12_eventos_os"];
  const eventos = useMemo<Record<string, unknown>[]>(() => {
    if (Array.isArray(eventosRaw)) return eventosRaw as Record<string, unknown>[];
    if (eventosRaw && typeof eventosRaw === "object") {
      const ev = (eventosRaw as Record<string, unknown>).eventos;
      if (Array.isArray(ev)) return ev as Record<string, unknown>[];
    }
    return [];
  }, [eventosRaw]);

  if (!eventos.length) {
    return (
      <div className="t-sub" style={{ padding: "8px 0" }}>
        Sem registros de acesso.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="row wrap" style={{ gap: 8 }}>
        <span className="badge neutral">
          <I.usuarios w={13} />
          {eventos.length} evento(s)
        </span>
      </div>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Usuário</th>
              <th>Ação</th>
              <th>Quando</th>
            </tr>
          </thead>
          <tbody>
            {eventos.map((a, k) => {
              const usuario =
                asStr(a.usuario) ?? asStr(a.autor) ?? asStr(a.ator) ?? asStr(a.papel) ?? "—";
              const acao = asStr(a.acao) ?? asStr(a.evento) ?? asStr(a.tipo) ?? "—";
              const quando = asStr(a.entrou_em) ?? asStr(a.data_hora) ?? asStr(a.created_at);
              return (
                <tr key={k}>
                  <td>
                    <div className="row" style={{ gap: 9 }}>
                      <span className="sb-ava" style={{ width: 28, height: 28, fontSize: 11 }}>
                        {usuario
                          .split(" ")
                          .map((x) => x[0])
                          .slice(0, 2)
                          .join("")}
                      </span>
                      <div>
                        <div className="t-strong">{usuario}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className="badge neutral" style={{ textTransform: "capitalize" }}>
                      {acao}
                    </span>
                  </td>
                  <td className="t-sub mono">{fmt.dmyhm(quando)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="tbl-foot">
          <I.video w={13} />
          Trilha de auditoria · origem:{" "}
          <span className="mono" style={{ marginLeft: 4 }}>
            laudo-json
          </span>
        </div>
      </div>
    </div>
  );
}

interface ConfBoxProps {
  titulo: string;
  res: string | null;
  pts: number | null;
  sub: string;
}
function ConfBox({ titulo, res, pts, sub }: ConfBoxProps) {
  const map: Record<string, [string, string]> = {
    A: ["ok", "Apto"],
    R: ["bad", "Reprovado"],
    N: ["neutral", "Sem avaliação"],
  };
  const [cls, label] = (res && map[res]) || ["neutral", "—"];
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--r)",
        padding: "13px 15px",
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: "var(--faint)",
          textTransform: "uppercase",
          letterSpacing: ".05em",
          fontWeight: 700,
        }}
      >
        {titulo}
      </div>
      <div style={{ margin: "8px 0 6px" }}>
        <span className={"badge " + cls}>
          <span className="bd" />
          {label}
        </span>
      </div>
      <div className="mono" style={{ fontSize: 12.5, color: "var(--muted)" }}>
        {pts != null ? pts + " pts" : "—"} · {sub}
      </div>
    </div>
  );
}

function ResCell({ c, pts }: { c: string | null; pts?: number | null }) {
  const map: Record<string, [string, string]> = {
    A: ["ok", "Apto"],
    R: ["bad", "Reprovado"],
    N: ["neutral", "Sem aval."],
  };
  if (!c)
    return (
      <span className="row" style={{ gap: 6 }}>
        <span className="badge neutral">
          <span className="bd" />—
        </span>
      </span>
    );
  const fallback: [string, string] = ["neutral", c];
  const [cls, label] = map[c] || fallback;
  return (
    <span className="row" style={{ gap: 7 }}>
      <span className={"badge " + cls}>
        <span className="bd" />
        {label}
      </span>
      {pts != null && <span className="mono t-sub">{pts}</span>}
    </span>
  );
}
