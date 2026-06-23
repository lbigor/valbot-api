import { type ReactNode, useState } from "react";
import { AppLayout } from "../components/AppLayout";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { Eye, Gauge, CheckCircle2, Scale } from "lucide-react";
import "./Medicao.css";

// Tela de Medição — produtividade e qualidade da auditoria assistida.
// Cruza exames assistidos × resultados (aprovado/reprovado) e concordância auditor×IA.
// Consome GET /api/dashboard/auditor-metrics (agregação por auditor + série temporal).
interface PorAuditor {
  auditor: string;
  exames_assistidos: number;
  pct_assistido_medio: number;
  aprovados: number;
  reprovados: number;
  concordancia_ia_pct: number;
  tempo_medio_s: number;
}
interface SeriePonto {
  dia: string;
  assistidos: number;
  divergencias: number;
}
interface Totais {
  exames_assistidos?: number;
  pct_assistido_medio?: number;
  aprovados?: number;
  reprovados?: number;
  concordancia_ia_pct?: number;
  tempo_medio_s?: number;
}
interface AuditorMetricsResponse {
  periodo_dias: number;
  por_auditor: PorAuditor[];
  serie: SeriePonto[];
  totais: Totais;
}

const int = (n: number) => (n ?? 0).toLocaleString("pt-BR");
const pct = (n: number) =>
  (n ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
const dur = (s: number) => {
  const v = Math.round(s ?? 0);
  const m = Math.floor(v / 60);
  const r = v % 60;
  return m > 0 ? `${m}m ${r}s` : `${r}s`;
};

async function fetchMetrics(auditor: string, dias: number): Promise<AuditorMetricsResponse> {
  const qs = new URLSearchParams();
  if (auditor) qs.set("auditor", auditor);
  qs.set("dias", String(dias));
  const r = await fetch(`/api/dashboard/auditor-metrics?${qs.toString()}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<AuditorMetricsResponse>;
}

function Kpi({ icon, label, value, sub }: { icon: ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="med-kpi">
      <div className="med-kpi-label">{icon}{label}</div>
      <div className="med-kpi-value">{value}</div>
      {sub && <div className="med-kpi-sub">{sub}</div>}
    </div>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="med-card">
      <h3 className="med-card-title">{title}</h3>
      {children}
    </div>
  );
}

export function Medicao() {
  const [dias, setDias] = useState(30);
  const [auditor, setAuditor] = useState("");

  const { data: d, isLoading } = useQuery({
    queryKey: ["auditor-metrics", auditor, dias],
    queryFn: () => fetchMetrics(auditor, dias),
  });

  // Totais com fallback tolerante a vazio (zeros).
  const t = d?.totais ?? {};
  const totalAssistidos = t.exames_assistidos ?? 0;
  const pctAssistido = t.pct_assistido_medio ?? 0;
  const aprovados = t.aprovados ?? 0;
  const reprovados = t.reprovados ?? 0;
  const concordancia = t.concordancia_ia_pct ?? 0;
  const tempoMedio = t.tempo_medio_s ?? 0;

  const porAuditor = d?.por_auditor ?? [];
  const serie = d?.serie ?? [];

  // Opções do filtro de auditor derivadas da resposta (sempre inclui o atual).
  const auditores = Array.from(
    new Set([auditor, ...porAuditor.map((a) => a.auditor)].filter(Boolean)),
  );

  return (
    <AppLayout activePage="Medição">
      <div className="med-root">
        <div className="med-header">
          <div>
            <h1 className="med-title">Medição — assistidos × resultados</h1>
            <p className="med-subtitle">
              Produtividade e qualidade da auditoria assistida nos últimos {d?.periodo_dias ?? dias} dias.
            </p>
          </div>
          <div className="med-filters">
            <label className="med-filter">
              <span>Auditor</span>
              <select value={auditor} onChange={(e) => setAuditor(e.target.value)}>
                <option value="">Todos</option>
                {auditores.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </label>
            <label className="med-filter">
              <span>Período</span>
              <select value={dias} onChange={(e) => setDias(Number(e.target.value))}>
                <option value={7}>7 dias</option>
                <option value={30}>30 dias</option>
                <option value={90}>90 dias</option>
                <option value={180}>180 dias</option>
              </select>
            </label>
          </div>
        </div>

        {isLoading && <p className="med-muted">Carregando…</p>}

        {d && (
          <>
            <div className="med-kpis">
              <Kpi icon={<Eye size={16} />} label="Exames assistidos" value={int(totalAssistidos)} />
              <Kpi icon={<Gauge size={16} />} label="% assistido médio" value={pct(pctAssistido)} />
              <Kpi
                icon={<CheckCircle2 size={16} />}
                label="Aprovados × reprovados"
                value={`${int(aprovados)} × ${int(reprovados)}`}
                sub={dur(tempoMedio) + " · tempo médio"}
              />
              <Kpi icon={<Scale size={16} />} label="Concordância auditor × IA" value={pct(concordancia)} />
            </div>

            <Card title="Por auditor — assistidos vs resultados">
              {porAuditor.length === 0 ? (
                <p className="med-muted">Sem dados no período.</p>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={porAuditor}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                    <XAxis dataKey="auditor" tick={{ fontSize: 11, fill: "var(--muted)" }} />
                    <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="exames_assistidos" name="Assistidos" fill="var(--accent)" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="aprovados" name="Aprovados" fill="#10B981" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="reprovados" name="Reprovados" fill="#EF4444" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card title="Série temporal — assistidos × divergências">
              {serie.length === 0 ? (
                <p className="med-muted">Sem dados no período.</p>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={serie}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                    <XAxis dataKey="dia" tick={{ fontSize: 11, fill: "var(--muted)" }} />
                    <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="assistidos" name="Assistidos" stroke="var(--accent)" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="divergencias" name="Divergências" stroke="#F59E0B" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card title="Detalhe por auditor">
              <table className="med-table">
                <thead>
                  <tr>
                    <th>Auditor</th>
                    <th className="num">Assistidos</th>
                    <th className="num">% assistido médio</th>
                    <th className="num">Aprovados</th>
                    <th className="num">Reprovados</th>
                    <th className="num">Concordância IA</th>
                    <th className="num">Tempo médio</th>
                  </tr>
                </thead>
                <tbody>
                  {porAuditor.length === 0 && (
                    <tr><td colSpan={7} className="med-empty">Sem dados no período.</td></tr>
                  )}
                  {porAuditor.map((a) => (
                    <tr key={a.auditor}>
                      <td>{a.auditor}</td>
                      <td className="num mono">{int(a.exames_assistidos)}</td>
                      <td className="num mono">{pct(a.pct_assistido_medio)}</td>
                      <td className="num mono">{int(a.aprovados)}</td>
                      <td className="num mono">{int(a.reprovados)}</td>
                      <td className="num mono">{pct(a.concordancia_ia_pct)}</td>
                      <td className="num mono">{dur(a.tempo_medio_s)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </>
        )}
      </div>
    </AppLayout>
  );
}

export default Medicao;
