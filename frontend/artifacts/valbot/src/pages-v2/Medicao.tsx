/* ============================================================================
   ValBot — Medição & Cobrança
   Mede o volume faturável do período (exams com resultado terminal) e gera a
   cobrança: demonstrativo por unidade × preço unitário → total da competência.
   ============================================================================ */
import { useState } from "react";
import type { ReactNode, CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/system/Shell";
import { Kpi, fmt } from "@/system/ui";
import { I } from "@/system/icons";

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/* ---- Parâmetros de configuração (NÃO são dados de negócio — não vivem no banco) ---- */
const USD_BRL = 5.42;
const VM_USD_MES = 1500; // 1x H100 24/7 (PLANILHA_CUSTOS §7 self-host)
const PRECO_PADRAO = 4.9; // R$ por vídeo — parâmetro comercial, editável na tela

declare global {
  interface Window {
    __t?: ReturnType<typeof setTimeout>;
  }
}

interface ItemCobranca {
  unidade: string;
  qtd: number;
  subtotal: number;
}

/* ---- Contrato GET /api/v2/dashboard (subconjunto usado nesta tela) ---- */
interface DashboardResponse {
  operacionais: {
    total_recebidos: number;
    por_status: Record<string, number>;
    taxa_erro: number;
    tempo_medio_analise_s: number;
  };
  regulatorios: {
    concordancia_resultado_pct: number;
    taxa_interrupcao_pct: number;
    taxa_evidencia_insuficiente_pct: number;
  };
}

/* ---- Contrato GET /api/dashboard/custos (subconjunto usado nesta tela) ---- */
interface CustoUnidade { rotulo: string; custo_usd: number; num_exames: number; }
interface CustosResponse {
  custo_total_usd: number;
  num_exames_cobrados: number;
  por_unidade: CustoUnidade[];
}

async function fetchDashboard(dias: number): Promise<DashboardResponse> {
  const r = await fetch(`/api/v2/dashboard?dias=${dias}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<DashboardResponse>;
}

async function fetchCustos(dias: number): Promise<CustosResponse> {
  const r = await fetch(`/api/dashboard/custos?dias=${dias}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<CustosResponse>;
}

const EMPTY_DASH: DashboardResponse = {
  operacionais: { total_recebidos: 0, por_status: {}, taxa_erro: 0, tempo_medio_analise_s: 0 },
  regulatorios: {
    concordancia_resultado_pct: 0,
    taxa_interrupcao_pct: 0,
    taxa_evidencia_insuficiente_pct: 0,
  },
};
const EMPTY_CUSTOS: CustosResponse = {
  custo_total_usd: 0,
  num_exames_cobrados: 0,
  por_unidade: [],
};

export default function Medicao() {
  const [dias, setDias] = useState(30);
  const [preco, setPreco] = useState(PRECO_PADRAO); // R$ por vídeo (parâmetro comercial)
  const [emitir, setEmitir] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => {
    setToast(m);
    clearTimeout(window.__t);
    window.__t = setTimeout(() => setToast(null), 2200);
  };

  const dash = useQuery({ queryKey: ["v2-medicao", dias], queryFn: () => fetchDashboard(dias) });
  const custosQ = useQuery({ queryKey: ["v2-custos", dias], queryFn: () => fetchCustos(dias) });
  const isLoading = dash.isLoading || custosQ.isLoading;
  const { operacionais: op, regulatorios: reg } = dash.data ?? EMPTY_DASH;
  const cu = custosQ.data ?? EMPTY_CUSTOS;

  // volume faturável = exames com resultado terminal (cobrados); não-faturável = falhas de pipeline
  const itens: ItemCobranca[] = cu.por_unidade
    .map((u) => ({ unidade: u.rotulo, qtd: u.num_exames, subtotal: u.num_exames * preco }))
    .sort((a, b) => b.qtd - a.qtd);
  const totalQtd = itens.reduce((s, i) => s + i.qtd, 0);
  const faturavel = totalQtd || cu.num_exames_cobrados || op.total_recebidos;
  // não faturável = falhas do pipeline (status FALHOU ou, na ausência, total × taxa_erro)
  const naoFaturavel =
    op.por_status["FALHOU"] ?? Math.max(0, Math.round(op.total_recebidos * op.taxa_erro));
  const total = totalQtd * preco;
  const cmvBRL = (cu.custo_total_usd + VM_USD_MES * (dias / 30)) * USD_BRL;
  const margem = total - cmvBRL;

  const hoje = new Date();
  const competencia = `${MESES[hoje.getMonth()]}/${hoje.getFullYear()}`;
  const numCobranca = `COB-${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}${String(hoje.getDate()).padStart(2, "0")}`;

  const actions = (
    <>
      <div className="seg">
        {[7, 30, 90].map((d) => (
          <button key={d} className={dias === d ? "on" : ""} onClick={() => setDias(d)}>
            {d}d
          </button>
        ))}
      </div>
      <button className="btn btn-primary" onClick={() => setEmitir(true)}>
        <I.custos w={16} />
        Gerar cobrança
      </button>
    </>
  );

  return (
    <Shell
      active="medicao"
      title="Medição & Cobrança"
      sub={`Volume faturável e emissão da cobrança · competência ${competencia}${isLoading ? " · carregando…" : ""}`}
      actions={actions}
    >
      <div className="grid g-4">
        <Kpi
          icon={I.video}
          label="Volume faturável"
          value={fmt.int(faturavel)}
          foot={<span>vídeos processados (resultado terminal)</span>}
          iconColor="var(--proc)"
          iconBg="var(--proc-bg)"
        />
        <Kpi
          icon={I.custos}
          label="Preço unitário"
          value={fmt.brl(preco)}
          foot={<span>por vídeo medido</span>}
          iconColor="var(--brand)"
          iconBg="var(--brand-tint)"
        />
        <Kpi
          icon={I.relatorios}
          label="Valor da cobrança"
          value={fmt.brl(total)}
          foot={
            <span>
              {fmt.int(totalQtd)} vídeos × {fmt.brl(preco)}
            </span>
          }
          iconColor="var(--ok)"
          iconBg="var(--ok-bg)"
        />
        <Kpi
          icon={I.alert}
          label="Não faturável"
          value={fmt.int(naoFaturavel)}
          foot={<span>falhas de pipeline (não cobram)</span>}
          iconColor="var(--warn)"
          iconBg="var(--warn-bg)"
        />
      </div>

      <div
        className="grid g-2"
        style={{ marginTop: 16, gridTemplateColumns: "1.5fr 1fr", alignItems: "start" }}
      >
        {/* demonstrativo */}
        <div className="tbl-wrap">
          <div className="panel-h">
            <h2>Demonstrativo de cobrança</h2>
            <span className="ph-sub">por unidade · {competencia}</span>
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Unidade</th>
                <th>Vídeos medidos</th>
                <th>Preço unit.</th>
                <th>Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((it, i) => (
                <tr key={i}>
                  <td className="t-strong">{it.unidade}</td>
                  <td className="num">{fmt.int(it.qtd)}</td>
                  <td className="num t-sub">{fmt.brl(preco)}</td>
                  <td className="num t-strong">{fmt.brl(it.subtotal)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="tbl-foot" style={{ fontSize: 14 }}>
            <span className="t-strong" style={{ color: "var(--ink)" }}>
              Total da competência
            </span>
            <span className="spacer" />
            <span className="mono" style={{ fontSize: 16, fontWeight: 800, color: "var(--ink)" }}>
              {fmt.brl(total)}
            </span>
          </div>
        </div>

        {/* resumo / parâmetros */}
        <div>
          <div className="panel">
            <div className="panel-h">
              <h2>Resumo da medição</h2>
            </div>
            <div className="panel-b" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div className="fld">
                <label className="fld-l">Preço por vídeo (R$)</label>
                <input
                  className="mono"
                  type="number"
                  step="0.10"
                  min="0"
                  value={preco}
                  onChange={(e) => setPreco(Math.max(0, +e.target.value))}
                />
                <span className="t-sub">Parâmetro comercial — define o valor da cobrança.</span>
              </div>
              <RLine k="Competência" v={competencia} />
              <RLine k="Volume faturável" v={fmt.int(faturavel) + " vídeos"} />
              <RLine k="Não faturável (falhas)" v={fmt.int(naoFaturavel) + " vídeos"} />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  paddingTop: 12,
                  borderTop: "1px solid var(--border)",
                }}
              >
                <span style={{ fontWeight: 700 }}>Total a cobrar</span>
                <span className="mono" style={{ fontSize: 19, fontWeight: 800 }}>
                  {fmt.brl(total)}
                </span>
              </div>
              <button
                className="btn btn-primary"
                style={{ width: "100%", height: 44, justifyContent: "center" }}
                onClick={() => setEmitir(true)}
              >
                <I.custos w={16} />
                Gerar cobrança
              </button>
            </div>
          </div>
          <div className="panel" style={{ marginTop: 16 }}>
            <div className="panel-h">
              <h2>Conciliação</h2>
            </div>
            <div className="panel-b" style={{ display: "flex", flexDirection: "column", gap: 11 }}>
              <RLine k="Receita (cobrança)" v={fmt.brl(total)} strong />
              <RLine k="CMV do período" v={fmt.brl(cmvBRL)} />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  paddingTop: 11,
                  borderTop: "1px solid var(--border)",
                }}
              >
                <span style={{ fontWeight: 700 }}>Margem bruta</span>
                <span
                  className="mono"
                  style={{
                    fontSize: 16,
                    fontWeight: 800,
                    color: margem >= 0 ? "var(--ok)" : "var(--bad)",
                  }}
                >
                  {fmt.brl(margem)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* indicadores de apoio (qualidade regulatória da janela) */}
      <div className="section-title" style={{ marginTop: 24 }}>
        <I.medicao w={14} />
        Indicadores do período (apoio à cobrança)
      </div>
      <div className="grid g-4">
        <Kpi
          icon={I.bolt}
          label="Tempo médio de análise"
          value={op.tempo_medio_analise_s ? op.tempo_medio_analise_s.toFixed(0) + " s" : "—"}
          iconColor="var(--proc)"
          iconBg="var(--proc-bg)"
        />
        <Kpi
          icon={I.target}
          label="Concordância da IA"
          value={fmt.pct(reg.concordancia_resultado_pct)}
          iconColor="var(--ok)"
          iconBg="var(--ok-bg)"
        />
        <Kpi
          icon={I.clock}
          label="Taxa de interrupção"
          value={fmt.pct(reg.taxa_interrupcao_pct)}
          foot={<span>exames com interrupção</span>}
          iconColor="var(--warn)"
          iconBg="var(--warn-bg)"
        />
        <Kpi
          icon={I.alert}
          label="Evidência insuficiente"
          value={fmt.pct(reg.taxa_evidencia_insuficiente_pct)}
          foot={<span>divergências sem evidência</span>}
          iconColor="var(--brand)"
          iconBg="var(--brand-tint)"
        />
      </div>

      {emitir && (
        <EmitirModal
          num={numCobranca}
          competencia={competencia}
          qtd={totalQtd}
          total={total}
          preco={preco}
          onClose={() => setEmitir(false)}
          onEmit={() => {
            setEmitir(false);
            flash(`Cobrança ${numCobranca} gerada · ${fmt.brl(total)}`);
          }}
        />
      )}
      {toast && <div className="toast">{toast}</div>}
    </Shell>
  );
}

interface RLineProps {
  k: ReactNode;
  v: ReactNode;
  strong?: boolean;
}

function RLine({ k, v, strong }: RLineProps) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        fontSize: 13,
        paddingBottom: 9,
        borderBottom: "1px solid var(--border)",
      }}
    >
      <span className="muted">{k}</span>
      <span
        className="mono"
        style={{ fontWeight: strong ? 800 : 600, fontSize: strong ? 15 : 13 }}
      >
        {v}
      </span>
    </div>
  );
}

interface EmitirModalProps {
  num: string;
  competencia: string;
  qtd: number;
  total: number;
  preco: number;
  onClose: () => void;
  onEmit: () => void;
}

function EmitirModal({ num, competencia, qtd, total, preco, onClose, onEmit }: EmitirModalProps) {
  const [cliente, setCliente] = useState("DETRAN-SE");
  const [venc, setVenc] = useState("");
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="modal" style={{ width: 480 }}>
        <div style={{ padding: "20px 22px 0" }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: ".08em",
              textTransform: "uppercase" as CSSProperties["textTransform"],
              color: "var(--brand)",
              fontWeight: 700,
            }}
          >
            Gerar cobrança
          </div>
          <div style={{ fontSize: 18, fontWeight: 800, marginTop: 3 }}>{num}</div>
          <div className="t-sub">Competência {competencia}</div>
        </div>
        <div style={{ padding: "18px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="fld">
            <label className="fld-l">Cliente / órgão</label>
            <input value={cliente} onChange={(e) => setCliente(e.target.value)} />
          </div>
          <div className="fld">
            <label className="fld-l">Vencimento</label>
            <input
              value={venc}
              onChange={(e) => setVenc(e.target.value)}
              placeholder="dd/mm/aaaa"
            />
          </div>
          <div
            style={{
              background: "var(--surface-2)",
              borderRadius: "var(--r)",
              padding: "14px 16px",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <RLine k="Vídeos medidos" v={fmt.int(qtd)} />
            <RLine k="Preço unitário" v={fmt.brl(preco)} />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                paddingTop: 8,
                borderTop: "1px solid var(--border)",
              }}
            >
              <span style={{ fontWeight: 700 }}>Total</span>
              <span className="mono" style={{ fontSize: 18, fontWeight: 800 }}>
                {fmt.brl(total)}
              </span>
            </div>
          </div>
        </div>
        <div className="drawer-f" style={{ borderRadius: "0 0 var(--r-xl) var(--r-xl)" }}>
          <button className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" onClick={onEmit}>
            <I.check w={15} />
            Emitir cobrança
          </button>
        </div>
      </div>
    </>
  );
}
