import { type ReactNode, useState } from "react";
import { AppLayout } from "../components/AppLayout";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  Printer,
  Download,
  FileStack,
  X,
  Filter,
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import "./Relatorios.css";

// Tela "Relatório de resultado" — confronta o resultado OFICIAL do exame (DETRAN)
// contra o resultado CALCULADO pelo Val (auditoria automatizada). Lista exames
// com filtros, permite ver o laudo detalhado (14 blocos), imprimir/baixar PDF,
// gerar PDF consolidado de uma seleção e exportar CSV.
//
// Contratos consumidos (todos credentials:include, tolerantes a vazio/erro):
//   GET /api/relatorios/resultados?dias=&unidade=&examinador=&resultado=&categoria=
//   GET /api/exams/{hash}/laudo-json        → laudo completo (14 blocos)
//   GET /api/exams/{hash}/laudo-pdf         → abrir em nova aba
//   GET /api/relatorios/consolidado?hashes=h1,h2
//   GET /api/relatorios/export.csv?...      → mesmos filtros

interface ResultadoRow {
  hash: string;
  renach: string;
  candidato_nome: string;
  data_hora_exame: string;
  unidade: string;
  examinador: string;
  categoria: string;
  resultado_exame: string;        // resultado oficial (A/R/N)
  resultado_calculado: string;    // resultado calculado pelo Val (A/R/N)
  pontuacao_oficial: number | null;
  pontuacao_calculada: number | null;
  tipo_divergencia: string | null;
}

// Laudo completo — o JSON de retorno do backend (§14.2): metadados + `blocos`
// como OBJETO com 14 chaves (1_identificacao … 14_integridade).
interface LaudoJson {
  exame_hash?: string;
  laudo_versao?: string;
  emitido_em?: string;
  fonte?: string;
  blocos?: Record<string, unknown>;
  [k: string]: unknown;
}

// Títulos legíveis para as 14 chaves do §14.2.
const BLOCO_TITULOS: Record<string, string> = {
  "1_identificacao": "Identificação",
  "2_candidato": "Candidato",
  "3_examinador": "Examinador",
  "4_resultado_oficial": "Resultado Oficial",
  "5_resultado_calculado": "Resultado Calculado (Val)",
  "6_cobertura": "Cobertura da Análise",
  "7_analise_detalhada": "Análise Detalhada (Infrações)",
  "8_divergencia": "Divergência",
  "9_comite_ia": "Comitê de IA",
  "10_parecer_auditor": "Parecer do Auditor",
  "11_decisao_supervisor": "Decisão do Supervisor",
  "12_eventos_os": "Trilha de Auditoria / Eventos",
  "13_envio_unidade_gestora": "Envio à Unidade Gestora",
  "14_integridade": "Integridade",
};

interface Filtros {
  dias: number;
  unidade: string;
  examinador: string;
  resultado: string; // "" | "A" | "R" | "N"
  categoria: string;
}

const RESULTADO_LABEL: Record<string, string> = {
  A: "Apto",
  R: "Reprovado",
  N: "Não realizado",
};
const RESULTADO_CLASS: Record<string, string> = {
  A: "badge-apto",
  R: "badge-reprovado",
  N: "badge-na",
};

function fmtData(s: string): string {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
function fmtPts(n: number | null): string {
  return n == null ? "—" : String(n);
}
function resBadge(r: string): ReactNode {
  const cls = RESULTADO_CLASS[r] ?? "badge-na";
  return <span className={`badge ${cls}`}>{RESULTADO_LABEL[r] ?? r ?? "—"}</span>;
}

function buildQuery(f: Filtros): string {
  const p = new URLSearchParams();
  p.set("dias", String(f.dias));
  if (f.unidade) p.set("unidade", f.unidade);
  if (f.examinador) p.set("examinador", f.examinador);
  if (f.resultado) p.set("resultado", f.resultado);
  if (f.categoria) p.set("categoria", f.categoria);
  return p.toString();
}

interface RelatoriosPage {
  items: ResultadoRow[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

async function fetchResultados(
  f: Filtros,
  page: number,
  pageSize: number,
): Promise<RelatoriosPage> {
  const qs = `${buildQuery(f)}&page=${page}&page_size=${pageSize}`;
  const r = await fetch(`/api/relatorios/resultados?${qs}`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const data = await r.json();
  const items = (Array.isArray(data)
    ? data
    : (data?.items ?? [])) as ResultadoRow[];
  return {
    items,
    total: typeof data?.total === "number" ? data.total : items.length,
    page: typeof data?.page === "number" ? data.page : page,
    page_size: typeof data?.page_size === "number" ? data.page_size : pageSize,
    pages: typeof data?.pages === "number" ? data.pages : 1,
  };
}

async function fetchLaudo(hash: string): Promise<LaudoJson> {
  const r = await fetch(`/api/exams/${encodeURIComponent(hash)}/laudo-json`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<LaudoJson>;
}

// Abre uma URL em nova aba (PDF). Mantém credentials via cookie do browser.
function abrirNovaAba(url: string) {
  window.open(url, "_blank", "noopener,noreferrer");
}

// ---------------------------------------------------------------------------

function CampoFiltro({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="filtro-campo">
      <span className="filtro-label">{label}</span>
      {children}
    </label>
  );
}

// Modal de laudo detalhado — renderiza os blocos do laudo-json de forma genérica
// (tolerante a estrutura variável). Cabeçalho fixo + ação de PDF.
function LaudoModal({
  hash,
  onClose,
}: {
  hash: string;
  onClose: () => void;
}) {
  const [verJson, setVerJson] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["laudo", hash],
    queryFn: () => fetchLaudo(hash),
    retry: false,
  });

  const candidato = (data?.blocos?.["2_candidato"] ?? {}) as Record<string, unknown>;
  const nome = (candidato.nome as string) || "Laudo do exame";
  const renach = (candidato.renach as string) || "—";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <FileText size={18} />
            <div>
              <div className="modal-title-main">{nome}</div>
              <div className="modal-title-sub mono">
                RENACH {renach} · {hash.slice(0, 12)}
                {data?.fonte ? ` · fonte ${data.fonte}` : ""}
              </div>
            </div>
          </div>
          <div className="modal-header-actions">
            <button
              className="btn btn-ghost"
              onClick={() => setVerJson((v) => !v)}
              title={verJson ? "Ver formatado" : "Ver JSON de retorno"}
            >
              <FileText size={15} /> {verJson ? "Formatado" : "JSON"}
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => abrirNovaAba(`/api/exams/${encodeURIComponent(hash)}/laudo-pdf`)}
              title="Imprimir / baixar PDF"
            >
              <Printer size={15} /> PDF
            </button>
            <button className="btn-icon" onClick={onClose} title="Fechar">
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="modal-body">
          {isLoading && <p className="muted">Carregando laudo…</p>}
          {isError && (
            <p className="muted">
              Não foi possível carregar o laudo deste exame.
            </p>
          )}
          {data &&
            (verJson ? (
              <pre className="laudo-raw laudo-json-full">
                {JSON.stringify(data, null, 2)}
              </pre>
            ) : (
              <LaudoBlocos data={data} />
            ))}
        </div>
      </div>
    </div>
  );
}

// Helpers de renderização de um valor de bloco (tolerante a estrutura variável).
function valorVazio(v: unknown): boolean {
  if (v == null || v === "") return true;
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
}
function fmtValor(v: unknown): string {
  if (v == null || v === "") return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// Renderiza o valor de um bloco: objeto → tabela rótulo/valor; lista → tabelas
// empilhadas (uma por item); escalar → texto.
function BlocoValor({ valor }: { valor: unknown }) {
  if (valorVazio(valor)) return <p className="laudo-obs">—</p>;

  if (Array.isArray(valor)) {
    return (
      <>
        {valor.map((item, i) =>
          item && typeof item === "object" ? (
            <table key={i} className="laudo-tabela">
              <tbody>
                {Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                  <tr key={k}>
                    <td className="laudo-rotulo">{k}</td>
                    <td className="laudo-valor">{fmtValor(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p key={i} className="laudo-valor">
              {fmtValor(item)}
            </p>
          ),
        )}
      </>
    );
  }

  if (typeof valor === "object") {
    return (
      <table className="laudo-tabela">
        <tbody>
          {Object.entries(valor as Record<string, unknown>).map(([k, v]) => (
            <tr key={k}>
              <td className="laudo-rotulo">{k}</td>
              <td className="laudo-valor">{fmtValor(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return <p className="laudo-valor">{fmtValor(valor)}</p>;
}

// Renderização dos 14 blocos do §14.2 a partir do OBJETO `blocos` do JSON de
// retorno (chaves "1_identificacao" … "14_integridade"). Fallback tolerante
// quando o laudo não traz `blocos` estruturado.
function LaudoBlocos({ data }: { data: LaudoJson }) {
  const blocos = data.blocos;

  if (blocos && typeof blocos === "object" && Object.keys(blocos).length > 0) {
    const chaves = Object.keys(blocos).sort((a, b) => {
      const na = parseInt(a, 10);
      const nb = parseInt(b, 10);
      if (!isNaN(na) && !isNaN(nb)) return na - nb;
      return a.localeCompare(b);
    });
    return (
      <div className="laudo-grid">
        {chaves.map((k) => (
          <section key={k} className="laudo-bloco">
            <h4>{BLOCO_TITULOS[k] ?? k}</h4>
            <BlocoValor valor={(blocos as Record<string, unknown>)[k]} />
          </section>
        ))}
      </div>
    );
  }

  // Fallback: dump das chaves de topo (exceto metadados já no cabeçalho).
  const skip = new Set(["exame_hash", "laudo_versao", "emitido_em", "fonte"]);
  const keys = Object.keys(data).filter((k) => !skip.has(k));
  if (keys.length === 0) {
    return <p className="muted">Laudo sem conteúdo estruturado.</p>;
  }
  return (
    <div className="laudo-grid">
      {keys.map((k) => (
        <section key={k} className="laudo-bloco">
          <h4>{k}</h4>
          <pre className="laudo-raw">
            {JSON.stringify((data as Record<string, unknown>)[k], null, 2)}
          </pre>
        </section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------

export function Relatorios() {
  const [filtros, setFiltros] = useState<Filtros>({
    dias: 30,
    unidade: "",
    examinador: "",
    resultado: "",
    categoria: "",
  });
  // Filtros aplicados (efetivam a query). Separar permite "Aplicar" explícito.
  const [aplicados, setAplicados] = useState<Filtros>(filtros);
  const [selecionados, setSelecionados] = useState<Set<string>>(new Set());
  const [laudoHash, setLaudoHash] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["relatorios-resultados", aplicados, page, pageSize],
    queryFn: () => fetchResultados(aplicados, page, pageSize),
    retry: false,
  });

  const rows = data?.items ?? [];
  const total = data?.total ?? rows.length;
  const pages = data?.pages ?? 1;
  const divergentes = rows.filter((r) => r.tipo_divergencia).length;

  function aplicar() {
    setAplicados(filtros);
    setSelecionados(new Set());
    setPage(1);
  }
  function toggle(hash: string) {
    setSelecionados((prev) => {
      const n = new Set(prev);
      if (n.has(hash)) n.delete(hash);
      else n.add(hash);
      return n;
    });
  }
  function toggleTodos() {
    setSelecionados((prev) =>
      prev.size === rows.length && rows.length > 0
        ? new Set()
        : new Set(rows.map((r) => r.hash)),
    );
  }
  function pdfConsolidado() {
    const hashes = Array.from(selecionados);
    if (hashes.length === 0) return;
    abrirNovaAba(
      `/api/relatorios/consolidado?hashes=${encodeURIComponent(hashes.join(","))}`,
    );
  }
  function exportarCsv() {
    abrirNovaAba(`/api/relatorios/export.csv?${buildQuery(aplicados)}`);
  }

  const todosMarcados = rows.length > 0 && selecionados.size === rows.length;

  return (
    <AppLayout activePage="Relatórios">
      <div className="rel-wrap">
        <h1 className="rel-title">Relatório de resultado</h1>
        <p className="rel-subtitle">
          Confronto entre o resultado oficial e o resultado calculado pelo Val —
          últimos {aplicados.dias} dias.
        </p>

        {/* Filtros */}
        <div className="rel-filtros">
          <CampoFiltro label="Período (dias)">
            <select
              value={filtros.dias}
              onChange={(e) =>
                setFiltros((f) => ({ ...f, dias: Number(e.target.value) }))
              }
            >
              <option value={7}>7 dias</option>
              <option value={15}>15 dias</option>
              <option value={30}>30 dias</option>
              <option value={60}>60 dias</option>
              <option value={90}>90 dias</option>
            </select>
          </CampoFiltro>
          <CampoFiltro label="Unidade">
            <input
              type="text"
              placeholder="Todas"
              value={filtros.unidade}
              onChange={(e) =>
                setFiltros((f) => ({ ...f, unidade: e.target.value }))
              }
            />
          </CampoFiltro>
          <CampoFiltro label="Examinador">
            <input
              type="text"
              placeholder="Todos"
              value={filtros.examinador}
              onChange={(e) =>
                setFiltros((f) => ({ ...f, examinador: e.target.value }))
              }
            />
          </CampoFiltro>
          <CampoFiltro label="Resultado">
            <select
              value={filtros.resultado}
              onChange={(e) =>
                setFiltros((f) => ({ ...f, resultado: e.target.value }))
              }
            >
              <option value="">Todos</option>
              <option value="A">Apto</option>
              <option value="R">Reprovado</option>
              <option value="N">Não realizado</option>
            </select>
          </CampoFiltro>
          <CampoFiltro label="Categoria CNH">
            <select
              value={filtros.categoria}
              onChange={(e) =>
                setFiltros((f) => ({ ...f, categoria: e.target.value }))
              }
            >
              <option value="">Todas</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="AB">AB</option>
              <option value="C">C</option>
              <option value="D">D</option>
              <option value="E">E</option>
            </select>
          </CampoFiltro>
          <button className="btn btn-accent rel-aplicar" onClick={aplicar}>
            <Filter size={15} /> Aplicar
          </button>
        </div>

        {/* Barra de resumo + ações de seleção */}
        <div className="rel-barra">
          <div className="rel-resumo">
            <span>
              <strong>{total}</strong> exame(s)
              {pages > 1 ? ` · pág. ${page}/${pages}` : ""}
            </span>
            {divergentes > 0 && (
              <span className="rel-diverg">
                <AlertTriangle size={14} /> {divergentes} divergência(s)
              </span>
            )}
            {selecionados.size > 0 && (
              <span className="muted">{selecionados.size} selecionado(s)</span>
            )}
          </div>
          <div className="rel-acoes">
            <button
              className="btn btn-ghost"
              onClick={pdfConsolidado}
              disabled={selecionados.size === 0}
              title="PDF consolidado da seleção"
            >
              <FileStack size={15} /> PDF consolidado
            </button>
            <button
              className="btn btn-ghost"
              onClick={exportarCsv}
              title="Exportar CSV com os filtros atuais"
            >
              <Download size={15} /> Exportar CSV
            </button>
          </div>
        </div>

        {/* Tabela */}
        <div className="rel-tabela-wrap">
          {isLoading && <p className="muted pad">Carregando…</p>}
          {isError && (
            <p className="muted pad">
              Não foi possível carregar os resultados. Tente novamente.
            </p>
          )}
          {!isLoading && !isError && (
            <table className="rel-tabela">
              <thead>
                <tr>
                  <th className="col-check">
                    <input
                      type="checkbox"
                      checked={todosMarcados}
                      onChange={toggleTodos}
                      aria-label="Selecionar todos"
                    />
                  </th>
                  <th>RENACH</th>
                  <th>Candidato</th>
                  <th>Data</th>
                  <th>Unidade</th>
                  <th>Examinador</th>
                  <th>Cat.</th>
                  <th>Oficial</th>
                  <th>Val</th>
                  <th>Divergência</th>
                  <th className="col-acoes">Ações</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={11} className="muted pad">
                      Nenhum exame no período/filtros.
                    </td>
                  </tr>
                )}
                {rows.map((r) => {
                  const diverge = !!r.tipo_divergencia;
                  return (
                    <tr key={r.hash} className={diverge ? "row-diverg" : ""}>
                      <td className="col-check">
                        <input
                          type="checkbox"
                          checked={selecionados.has(r.hash)}
                          onChange={() => toggle(r.hash)}
                          aria-label={`Selecionar ${r.renach}`}
                        />
                      </td>
                      <td className="mono">{r.renach}</td>
                      <td>{r.candidato_nome}</td>
                      <td className="nowrap">{fmtData(r.data_hora_exame)}</td>
                      <td>{r.unidade}</td>
                      <td>{r.examinador}</td>
                      <td className="mono">{r.categoria}</td>
                      <td>
                        {resBadge(r.resultado_exame)}
                        <span className="pts mono">
                          {fmtPts(r.pontuacao_oficial)}
                        </span>
                      </td>
                      <td>
                        {resBadge(r.resultado_calculado)}
                        <span className="pts mono">
                          {fmtPts(r.pontuacao_calculada)}
                        </span>
                      </td>
                      <td>
                        {diverge ? (
                          <span className="diverg-tag">
                            <AlertTriangle size={12} /> {r.tipo_divergencia}
                          </span>
                        ) : (
                          <span className="ok-tag">
                            <CheckCircle2 size={12} /> OK
                          </span>
                        )}
                      </td>
                      <td className="col-acoes">
                        <button
                          className="btn-sm"
                          onClick={() => setLaudoHash(r.hash)}
                          title="Ver laudo detalhado"
                        >
                          <FileText size={14} /> Ver laudo
                        </button>
                        <button
                          className="btn-sm"
                          onClick={() =>
                            abrirNovaAba(
                              `/api/exams/${encodeURIComponent(r.hash)}/laudo-pdf`,
                            )
                          }
                          title="Imprimir / baixar PDF"
                        >
                          <Printer size={14} /> PDF
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Paginação */}
        {!isLoading && !isError && rows.length > 0 && (
          <div className="rel-paginacao">
            <button
              className="btn btn-ghost"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              <ChevronLeft size={15} /> Anterior
            </button>
            <span className="muted">
              Página {page} de {pages} · {total} exame(s)
            </span>
            <button
              className="btn btn-ghost"
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages}
            >
              Próxima <ChevronRight size={15} />
            </button>
            <label className="rel-pagesize">
              <span className="muted">por página</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
              </select>
            </label>
          </div>
        )}
      </div>

      {laudoHash && (
        <LaudoModal hash={laudoHash} onClose={() => setLaudoHash(null)} />
      )}
    </AppLayout>
  );
}

export default Relatorios;
