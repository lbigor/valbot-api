import { AppLayout } from "../components/AppLayout";
import {
  FileCheck,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Clock,
  TrendingUp,
  ArrowUpRight,
} from "lucide-react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";
import { useQuery } from "@tanstack/react-query";
import { useDemoMode } from "@/contexts/DemoContext";
import { GlassCard, tooltipStyle } from "@/components/ui/glass-card";
import { CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function KpiCard({
  title,
  value,
  sub,
  icon: Icon,
  tone = "cyan",
  critical = false,
}: {
  title: string;
  value: string | number;
  sub?: string;
  icon: any;
  tone?: "cyan" | "emerald" | "amber" | "red" | "blue";
  critical?: boolean;
}) {
  const tones: Record<string, { ring: string; bg: string; text: string; glow: any }> = {
    cyan: { ring: "ring-cyan-500/20", bg: "bg-cyan-500/10", text: "text-cyan-400", glow: "cyan" },
    emerald: { ring: "ring-emerald-500/20", bg: "bg-emerald-500/10", text: "text-emerald-400", glow: "emerald" },
    amber: { ring: "ring-amber-500/20", bg: "bg-amber-500/10", text: "text-amber-400", glow: "amber" },
    red: { ring: "ring-red-500/30", bg: "bg-red-500/10", text: "text-red-400", glow: "red" },
    blue: { ring: "ring-blue-600/20", bg: "bg-blue-600/10", text: "text-blue-400", glow: "blue" },
  };
  const t = tones[tone];
  return (
    <GlassCard glow={critical ? "red" : t.glow} className="overflow-hidden group">
      {critical && (
        <div className="absolute inset-y-0 left-0 w-[3px] bg-gradient-to-b from-red-500 via-red-400 to-red-600" />
      )}
      <CardContent className="p-5 flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
            {title}
          </p>
          <div className="flex items-baseline gap-2">
            <h3
              className={cn(
                "text-3xl font-bold tabular-nums",
                critical ? "text-red-400" : "text-slate-50",
              )}
            >
              {value}
            </h3>
          </div>
          {sub && (
            <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
              {!critical && tone === "emerald" && (
                <ArrowUpRight size={11} className="text-emerald-400" />
              )}
              {sub}
            </p>
          )}
        </div>
        <div
          className={cn(
            "p-2 rounded-lg ring-1 group-hover:scale-105 transition-transform",
            t.bg,
            t.ring,
            t.text,
          )}
        >
          <Icon size={18} strokeWidth={2.2} />
        </div>
      </CardContent>
    </GlassCard>
  );
}

export function Dashboard() {
  const { demoMode } = useDemoMode();
  const { data } = useQuery({
    queryKey: ["dashboard-kpis", demoMode],
    queryFn: async () => {
      const r = await fetch(`/api/dashboard/kpis?demo=${demoMode}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    refetchInterval: demoMode ? false : 15000,
    staleTime: demoMode ? Infinity : 5000,
  });

  // Sem mock: ausência de dados = estrutura vazia (KPIs zeram, não inventam).
  const kpis: any = data ?? { weekly: [], severity: [], units: [], priority_cases: [], totals: {}, insights: [] };
  const weekly = (kpis.weekly ?? []).map((r: any) => ({
    ...r,
    indicio: r.indicio ?? r["indício"] ?? 0,
  }));
  const severity = kpis.severity ?? [];
  const unit = kpis.unit ?? kpis.units ?? [];
  const priority = kpis.priority ?? kpis.priority_cases ?? [];
  const totals = kpis.totals ?? {};
  const severityTotal = severity.reduce(
    (acc: number, entry: { value: number }) => acc + (entry.value ?? 0),
    0,
  );

  return (
    <AppLayout activePage="Dashboard">
      {/* Ambient glow background */}
      <div className="relative h-full">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-32 -left-20 w-[480px] h-[480px] rounded-full bg-cyan-500/5 blur-3xl" />
          <div className="absolute top-1/3 -right-20 w-[420px] h-[420px] rounded-full bg-blue-700/5 blur-3xl" />
          <div className="absolute bottom-0 left-1/3 w-[380px] h-[380px] rounded-full bg-emerald-500/[0.04] blur-3xl" />
        </div>

        <div className="relative flex gap-6 h-full">
          {/* ─────────── MAIN COLUMN ─────────── */}
          <div className="flex-1 flex flex-col gap-5 min-w-0">
            {/* Header */}
            <div className="flex items-end justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-[0.18em] text-cyan-400/80 font-medium">
                  Operações · Tempo real
                </p>
                <h1 className="text-2xl font-semibold text-slate-50 mt-1">
                  Painel executivo
                </h1>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                </span>
                Pipeline ativo · atualiza a cada 15s
              </div>
            </div>

            {/* KPI grid */}
            <div className="grid grid-cols-3 grid-rows-2 gap-4">
              <KpiCard
                title="Exames recebidos hoje"
                value={totals.recebidos_hoje ?? "—"}
                sub={totals.recebidos_sub ?? ""}
                icon={FileCheck}
                tone="cyan"
              />
              <KpiCard
                title="Exames processados"
                value={totals.processados ?? "—"}
                sub={totals.processados_sub ?? ""}
                icon={CheckCircle2}
                tone="emerald"
              />
              <KpiCard
                title="Casos com indício"
                value={totals.indicio ?? "—"}
                sub={totals.indicio_sub ?? ""}
                icon={AlertCircle}
                tone="amber"
              />
              <KpiCard
                title="Casos críticos"
                value={totals.criticos ?? "—"}
                sub={totals.criticos_sub ?? ""}
                icon={AlertTriangle}
                tone="red"
                critical
              />
              <KpiCard
                title="Tempo médio de revisão"
                value={totals.tempo_medio ?? "—"}
                sub={totals.tempo_medio_sub ?? ""}
                icon={Clock}
                tone="blue"
              />
              <KpiCard
                title="SLA dentro do prazo"
                value={totals.sla ?? "—"}
                sub={totals.sla_sub ?? ""}
                icon={TrendingUp}
                tone="emerald"
              />
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-3 gap-4">
              <GlassCard className="col-span-2" glow="blue">
                <CardContent className="p-5 pb-2 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-100">
                      Tendência semanal
                    </h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Volume diário · 7 dias
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-[11px]">
                    <LegendDot color="#1D4ED8" label="Recebidos" />
                    <LegendDot color="#06B6D4" label="Processados" />
                    <LegendDot color="#F59E0B" label="Com indício" />
                  </div>
                </CardContent>
                <div className="h-[220px] p-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={weekly}
                      margin={{ top: 10, right: 20, left: -10, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="gRec" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#1D4ED8" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#1D4ED8" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="gProc" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#06B6D4" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#1E293B"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="name"
                        stroke="#64748B"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis
                        stroke="#64748B"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: "#1E293B" }} />
                      <Area
                        type="monotone"
                        dataKey="recebidos"
                        name="Recebidos"
                        stroke="#1D4ED8"
                        fillOpacity={1}
                        fill="url(#gRec)"
                        strokeWidth={2}
                      />
                      <Area
                        type="monotone"
                        dataKey="processados"
                        name="Processados"
                        stroke="#06B6D4"
                        fillOpacity={1}
                        fill="url(#gProc)"
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="indicio"
                        name="Com indício"
                        stroke="#F59E0B"
                        strokeWidth={2}
                        dot={{ r: 3, fill: "#F59E0B", stroke: "#0B1224", strokeWidth: 2 }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </GlassCard>

              <GlassCard glow="amber">
                <CardContent className="p-5 pb-0">
                  <h3 className="text-sm font-semibold text-slate-100">
                    Distribuição por severidade
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">Mix de gravidade</p>
                </CardContent>
                <div className="h-[200px] flex items-center justify-center relative">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={severity}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={78}
                        paddingAngle={3}
                        dataKey="value"
                        stroke="#0B1224"
                        strokeWidth={2}
                      >
                        {severity.map(
                          (entry: { color: string }, index: number) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ),
                        )}
                      </Pie>
                      <Tooltip contentStyle={tooltipStyle} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-3xl font-bold text-slate-50 tabular-nums">
                      {severityTotal}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-slate-500">
                      Total casos
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 px-5 pb-5 pt-1">
                  {severity.map((s: any) => (
                    <div
                      key={s.name}
                      className="flex items-center justify-between text-[11px]"
                    >
                      <span className="flex items-center gap-1.5 text-slate-400">
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ background: s.color }}
                        />
                        {s.name}
                      </span>
                      <span className="text-slate-200 tabular-nums font-medium">
                        {s.value}
                      </span>
                    </div>
                  ))}
                </div>
              </GlassCard>
            </div>

            {/* Bottom row */}
            <div className="grid grid-cols-2 gap-4 flex-1 min-h-0">
              <GlassCard glow="cyan">
                <CardContent className="p-5 pb-2">
                  <h3 className="text-sm font-semibold text-slate-100">
                    Volume por unidade
                  </h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Exames processados · semana corrente
                  </p>
                </CardContent>
                <div className="h-[220px] px-2 pb-3">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={unit}
                      layout="vertical"
                      margin={{ top: 0, right: 20, left: 0, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="gBar" x1="0" y1="0" x2="1" y2="0">
                          <stop offset="0%" stopColor="#06B6D4" stopOpacity={0.95} />
                          <stop offset="100%" stopColor="#1D4ED8" stopOpacity={0.95} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#1E293B"
                        horizontal={false}
                      />
                      <XAxis
                        type="number"
                        stroke="#64748B"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis
                        dataKey="name"
                        type="category"
                        stroke="#94A3B8"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        width={110}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(30,41,59,0.4)" }}
                        contentStyle={tooltipStyle}
                      />
                      <Bar
                        dataKey="value"
                        fill="url(#gBar)"
                        radius={[0, 6, 6, 0]}
                        barSize={18}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </GlassCard>

              <GlassCard glow="red">
                <CardContent className="p-5 pb-3 border-b border-slate-800/60 flex justify-between items-center">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-100">
                      Casos críticos · SLA ameaçado
                    </h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Top 5 prioritários
                    </p>
                  </div>
                  <Button
                    variant="link"
                    size="sm"
                    className="h-auto p-0 text-[11px] text-cyan-400 hover:text-cyan-300 font-medium"
                  >
                    Ver todos →
                  </Button>
                </CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800/40">
                      <tr>
                        <th className="px-4 py-2.5 text-left font-medium">ID</th>
                        <th className="px-4 py-2.5 text-left font-medium">Candidato</th>
                        <th className="px-4 py-2.5 text-left font-medium">Score</th>
                        <th className="px-4 py-2.5 text-left font-medium">SLA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {priority.map(
                        (row: {
                          id: string;
                          name: string;
                          score: number;
                          sev: string;
                          sla?: string;
                        }) => (
                          <tr
                            key={row.id}
                            className="border-b border-slate-800/30 last:border-0 hover:bg-slate-800/30 transition-colors group cursor-pointer"
                          >
                            <td className="px-4 py-3 font-mono text-[11px] text-slate-300">
                              {row.id}
                            </td>
                            <td className="px-4 py-3 text-slate-200">{row.name}</td>
                            <td className="px-4 py-3">
                              <Badge
                                variant="outline"
                                className={cn(
                                  "px-2 py-0.5 text-[11px] font-semibold tabular-nums border",
                                  row.score >= 90
                                    ? "bg-red-500/10 text-red-400 border-red-500/30"
                                    : row.score >= 80
                                      ? "bg-orange-500/10 text-orange-400 border-orange-500/30"
                                      : "bg-amber-500/10 text-amber-400 border-amber-500/30",
                                )}
                              >
                                {row.score}
                              </Badge>
                            </td>
                            <td className="px-4 py-3 text-[11px] text-slate-400 tabular-nums">
                              {row.sla ?? "—"}
                            </td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            </div>
          </div>

        </div>
      </div>
    </AppLayout>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-slate-400">
      <span
        className="w-2 h-2 rounded-full ring-2 ring-offset-0"
        style={{ background: color, boxShadow: `0 0 6px ${color}` }}
      />
      {label}
    </span>
  );
}
