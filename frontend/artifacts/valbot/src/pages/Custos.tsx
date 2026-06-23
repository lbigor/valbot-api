import { type ReactNode } from "react";
import { AppLayout } from "../components/AppLayout";
import { useQuery } from "@tanstack/react-query";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { DollarSign, Cpu, FileCheck, TrendingUp } from "lucide-react";

// Tela de Custos de Processamento (vídeo/tokens) — acompanhamento e cobrança.
// Consome GET /api/dashboard/custos (agregação por dia/unidade/categoria).
interface CustoSerie { dia: string; custo_usd: number; num_exames: number; }
interface CustoRecorte { rotulo: string; custo_usd: number; num_exames: number; }
interface CustosResponse {
  periodo_dias: number;
  custo_total_usd: number;
  num_exames_cobrados: number;
  custo_medio_por_exame_usd: number;
  tokens_in_total: number;
  tokens_out_total: number;
  serie_diaria: CustoSerie[];
  por_unidade: CustoRecorte[];
  por_categoria: CustoRecorte[];
}

const usd = (n: number) => "$" + (n ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int = (n: number) => (n ?? 0).toLocaleString("pt-BR");

async function fetchCustos(dias: number): Promise<CustosResponse> {
  const r = await fetch(`/api/dashboard/custos?dias=${dias}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<CustosResponse>;
}

function Kpi({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 12, padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--muted)", fontSize: 12, marginBottom: 8 }}>{icon}{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 12, padding: 16 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>{title}</h3>
      {children}
    </div>
  );
}
function Recorte({ title, rows }: { title: string; rows: CustoRecorte[] }) {
  return (
    <Card title={title}>
      <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
        <thead><tr style={{ color: "var(--muted)", textAlign: "left", fontSize: 11 }}>
          <th style={{ padding: "6px 8px" }}>Rótulo</th>
          <th style={{ padding: "6px 8px", textAlign: "right" }}>Custo</th>
          <th style={{ padding: "6px 8px", textAlign: "right" }}>Exames</th>
        </tr></thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={3} style={{ padding: 10, color: "var(--muted)" }}>Sem dados no período.</td></tr>}
          {rows.map((r) => (
            <tr key={r.rotulo} style={{ borderTop: "1px solid var(--line)" }}>
              <td style={{ padding: "6px 8px" }}>{r.rotulo}</td>
              <td style={{ padding: "6px 8px", textAlign: "right" }} className="mono">{usd(r.custo_usd)}</td>
              <td style={{ padding: "6px 8px", textAlign: "right" }} className="mono">{int(r.num_exames)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function Custos() {
  const { data: d, isLoading } = useQuery({ queryKey: ["custos", 30], queryFn: () => fetchCustos(30) });
  return (
    <AppLayout activePage="Custos">
      <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Custos de Processamento</h1>
        <p style={{ color: "var(--muted)", marginBottom: 20, fontSize: 13 }}>
          Gasto de IA (vídeo/tokens) nos últimos {d?.periodo_dias ?? 30} dias — base para acompanhamento e cobrança.
        </p>
        {isLoading && <p style={{ color: "var(--muted)" }}>Carregando…</p>}
        {d && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
              <Kpi icon={<DollarSign size={16} />} label="Custo total" value={usd(d.custo_total_usd)} />
              <Kpi icon={<FileCheck size={16} />} label="Exames cobrados" value={int(d.num_exames_cobrados)} />
              <Kpi icon={<TrendingUp size={16} />} label="Custo médio/exame" value={usd(d.custo_medio_por_exame_usd)} />
              <Kpi icon={<Cpu size={16} />} label="Tokens in / out" value={int(d.tokens_in_total) + " / " + int(d.tokens_out_total)} />
            </div>
            <Card title="Custo por dia">
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={d.serie_diaria}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis dataKey="dia" tick={{ fontSize: 11, fill: "var(--muted)" }} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="custo_usd" stroke="var(--accent)" fill="var(--accent-soft)" />
                </AreaChart>
              </ResponsiveContainer>
            </Card>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
              <Recorte title="Por unidade" rows={d.por_unidade} />
              <Recorte title="Por categoria" rows={d.por_categoria} />
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}

export default Custos;
