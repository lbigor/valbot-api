/* ============================================================================
   ValBot — Dashboard (espelha backend/dashboard/metrics.py · §15)
   Porte fiel de .design-ref/page-dashboard.jsx — RELIGADO AOS DADOS REAIS.
   Fonte: GET /api/v2/dashboard?dias= (credentials:"include").
   Shape idêntico ao antigo VB.metrics.resumo(dias).
   ============================================================================ */
import { useState, useMemo } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/system/Shell";
import { Kpi, Donut, Bars, HBars, MiniStat, fmt } from "@/system/ui";
import type { DonutSegment, HBarItem } from "@/system/ui";
import { I } from "@/system/icons";

/* ---- consts locais (copiadas de vb-data.ts; antes VB.*) ---- */
/* fallback: o câmbio vivo vem do backend (res.usd_brl / res.custos.usd_brl);
   só usamos a constante se o backend não trouxer o valor. */
const USD_BRL_FALLBACK = 5.42;

type Gravidade = "gravissima" | "grave" | "media" | "leve";
const META_GRAV: Record<Gravidade, { label: string; pontos: number; color: string; bg: string; ring: string }> = {
  gravissima: { label: "Gravíssima", pontos: 6, color: "#BE123C", bg: "#FCEAEF", ring: "#F3C2CF" },
  grave: { label: "Grave", pontos: 4, color: "#B45309", bg: "#FBF1E3", ring: "#F0D9B3" },
  media: { label: "Média", pontos: 2, color: "#1D4ED8", bg: "#E7EEFD", ring: "#C5D6F8" },
  leve: { label: "Leve", pontos: 1, color: "#6B7689", bg: "#F1F4F9", ring: "#E5E9F0" },
};

const TIPO_DIV_LABEL: Record<string, string> = {
  "1_resultado": "Resultado",
  "2_pontuacao": "Pontuação",
  "3_infracao": "Infração",
  "4_enquadramento": "Enquadramento",
  "5_evidencia_insuficiente": "Evidência insuficiente",
};

/* ---- contrato GET /api/v2/dashboard — shape de VB.metrics.resumo(dias) ---- */
interface OperacionaisMetrics {
  total_recebidos: number;
  total_processados: number;
  por_status: Record<string, number>;
  taxa_erro: number;
  tempo_medio_analise_s: number;
  custo_total_usd: number;
  os_pendentes_por_status: Record<string, number>;
}
interface RegulatoriosMetrics {
  concordancia_resultado_pct: number;
  concordancia_pontuacao_pct: number;
  distribuicao_divergencias: Record<string, number>;
  top_infracoes: Record<string, number>;
  divergencia_por_unidade: Record<string, number>;
  taxa_interrupcao_pct: number;
  taxa_evidencia_insuficiente_pct: number;
  comentarios_inadequados_examinador: number;
}
interface CustoSerieDia {
  dia: string;
  num_exames: number;
  custo_usd: number;
}
interface CustosMetrics {
  serie_diaria: CustoSerieDia[];
  custo_medio_por_exame_usd: number;
  usd_brl?: number;
}
interface SupervisorMetrics {
  concordancia_supervisor_ia_pct: number;
}
interface ResumoMetrics {
  periodo_dias: number;
  operacionais: OperacionaisMetrics;
  regulatorios: RegulatoriosMetrics;
  custos: CustosMetrics;
  supervisor: SupervisorMetrics;
  compliance: Record<string, unknown>;
  usd_brl?: number;
}

const EMPTY: ResumoMetrics = {
  periodo_dias: 0,
  operacionais: {
    total_recebidos: 0,
    total_processados: 0,
    por_status: {},
    taxa_erro: 0,
    tempo_medio_analise_s: 0,
    custo_total_usd: 0,
    os_pendentes_por_status: {},
  },
  regulatorios: {
    concordancia_resultado_pct: 0,
    concordancia_pontuacao_pct: 0,
    distribuicao_divergencias: {},
    top_infracoes: {},
    divergencia_por_unidade: {},
    taxa_interrupcao_pct: 0,
    taxa_evidencia_insuficiente_pct: 0,
    comentarios_inadequados_examinador: 0,
  },
  custos: { serie_diaria: [], custo_medio_por_exame_usd: 0 },
  supervisor: { concordancia_supervisor_ia_pct: 0 },
  compliance: {},
};

async function fetchDashboard(dias: number): Promise<ResumoMetrics> {
  const r = await fetch(`/api/v2/dashboard?dias=${dias}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

/* GET /api/rubricas/1020-2025 → map codigo→{nome,grav} p/ rotular top_infracoes */
interface RuleInfo {
  nome: string;
  grav: Gravidade;
}
function normGrav(g: unknown): Gravidade {
  const s = String(g ?? "").toLowerCase();
  if (s.startsWith("gravi")) return "gravissima";
  if (s.startsWith("grav")) return "grave";
  if (s.startsWith("med")) return "media";
  if (s.startsWith("lev")) return "leve";
  return "media";
}
async function fetchRubricas(slug: string): Promise<Record<string, RuleInfo>> {
  const r = await fetch(`/api/rubricas/${slug}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const d = await r.json();
  const arr: any[] = Array.isArray(d?.infracoes) ? d.infracoes : Array.isArray(d) ? d : [];
  const map: Record<string, RuleInfo> = {};
  for (const inf of arr) {
    const codigo = String(inf.codigo ?? inf.id ?? inf.code ?? "");
    if (!codigo) continue;
    map[codigo] = {
      nome: String(inf.descricao ?? inf.nome ?? inf.desc ?? codigo),
      grav: normGrav(inf.gravidade ?? inf.grav),
    };
  }
  return map;
}

export default function Dashboard() {
  const [dias, setDias] = useState<number>(30);

  const { data } = useQuery({
    queryKey: ["v2-dashboard", dias],
    queryFn: () => fetchDashboard(dias),
  });
  const { data: rulesMap } = useQuery({
    // queryKey PRÓPRIA: o Dashboard cacheia um Record<codigo,RuleInfo> (mapa);
    // a tela Regras usa ["v2-rubricas","1020-2025"] com shape Rule[] (array).
    // Compartilhar a chave envenena o cache cruzado → `i.filter is not a function`.
    queryKey: ["v2-rubricas-map", "1020-2025"],
    queryFn: () => fetchRubricas("1020-2025"),
  });

  const m = data ?? EMPTY;
  const op = m.operacionais,
    reg = m.regulatorios,
    cu = m.custos,
    sup = m.supervisor;

  // câmbio vivo do backend (raiz res.usd_brl, ou res.custos.usd_brl), com fallback à constante
  const usdBrlRaw = m.usd_brl ?? cu.usd_brl;
  const USD_BRL =
    typeof usdBrlRaw === "number" && Number.isFinite(usdBrlRaw) && usdBrlRaw > 0
      ? usdBrlRaw
      : USD_BRL_FALLBACK;
  const custoBRL = op.custo_total_usd * USD_BRL;
  const statusColors: Record<string, string> = {
    APROVADO: "var(--ok)",
    INAPTO: "var(--bad)",
    SEM_AVALIACAO: "var(--faint)",
    PROCESSANDO: "var(--proc)",
    PENDENTE: "var(--warn)",
    FALHOU: "#7c3aed",
  };
  const statusLabel: Record<string, string> = {
    APROVADO: "Aptos",
    INAPTO: "Reprovados",
    SEM_AVALIACAO: "Sem avaliação",
    PROCESSANDO: "Processando",
    PENDENTE: "Pendentes",
    FALHOU: "Falhas",
  };
  const statusSegs: DonutSegment[] = Object.entries(op.por_status).map(([k, v]) => ({
    label: statusLabel[k] || k,
    value: v,
    color: statusColors[k] || "var(--muted)",
  }));

  const divSegs: DonutSegment[] = Object.entries(reg.distribuicao_divergencias).map(([k, v]) => ({
    label: TIPO_DIV_LABEL[k] || k,
    value: v,
    color: (
      {
        "1_resultado": "var(--bad)",
        "2_pontuacao": "var(--warn)",
        "3_infracao": "var(--proc)",
        "4_enquadramento": "var(--brand)",
        "5_evidencia_insuficiente": "var(--faint)",
      } as Record<string, string>
    )[k],
  }));
  const totalDiv = divSegs.reduce((s, x) => s + x.value, 0);

  const topInfra: HBarItem[] = useMemo(
    () =>
      Object.entries(reg.top_infracoes).map(([k, v]) => {
        const rule = rulesMap?.[k];
        return {
          label: rule ? rule.nome : k,
          value: v,
          color: rule ? META_GRAV[rule.grav].color : "var(--brand)",
        };
      }),
    [reg.top_infracoes, rulesMap],
  );
  const porUnidade: HBarItem[] = Object.entries(reg.divergencia_por_unidade)
    .map(([k, v]) => ({ label: k, value: v }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);
  const serieBars = cu.serie_diaria.slice(-14).map((d) => ({
    label: String(new Date(d.dia + "T12:00").getDate()),
    value: d.num_exames,
  }));

  const actions: ReactNode = (
    <div className="seg">
      {[7, 30, 90].map((d) => (
        <button key={d} className={dias === d ? "on" : ""} onClick={() => setDias(d)}>
          {d}d
        </button>
      ))}
    </div>
  );

  return (
    <Shell
      active="dashboard"
      title="Dashboard"
      sub={`Visão geral do processamento · últimos ${dias} dias`}
      actions={actions}
    >
      {/* KPIs */}
      <div className="grid g-4">
        <Kpi
          icon={I.video}
          label="Vídeos recebidos"
          value={fmt.int(op.total_recebidos)}
          delta="12,4%"
          deltaDir="up"
          spark={cu.serie_diaria.slice(-14).map((d) => d.num_exames)}
          sparkColor="var(--proc)"
          iconColor="var(--proc)"
          iconBg="var(--proc-bg)"
        />
        <Kpi
          icon={I.bolt}
          label="Vídeos processados"
          value={fmt.int(op.total_processados)}
          delta="14,1%"
          deltaDir="up"
          foot={
            <span>
              {fmt.pct(op.total_recebidos ? (100 * op.total_processados) / op.total_recebidos : 0)} do
              recebido
            </span>
          }
          iconColor="var(--brand)"
          iconBg="var(--brand-tint)"
        />
        <Kpi
          icon={I.custos}
          label="Custo total (IA)"
          value={fmt.brl(custoBRL)}
          delta="8,2%"
          deltaDir="down"
          foot={
            <span>
              {fmt.usd(op.custo_total_usd)} · {fmt.usd4(cu.custo_medio_por_exame_usd)}/vídeo
            </span>
          }
          iconColor="var(--warn)"
          iconBg="var(--warn-bg)"
        />
        <Kpi
          icon={I.target}
          label="Concordância c/ examinador"
          value={fmt.pct(reg.concordancia_resultado_pct)}
          delta="1,1 p.p."
          deltaDir="up"
          foot={<span>pontuação {fmt.pct(reg.concordancia_pontuacao_pct)}</span>}
          iconColor="var(--ok)"
          iconBg="var(--ok-bg)"
        />
      </div>

      {/* volume + status */}
      <div className="grid g-2" style={{ marginTop: 16, gridTemplateColumns: "1.55fr 1fr" }}>
        <div className="panel">
          <div className="panel-h">
            <h2>Volume de processamento</h2>
            <span className="ph-sub">últimos 14 dias</span>
            <span className="spacer" />
            <span className="badge proc">
              <span className="bd" />~52s/vídeo
            </span>
          </div>
          <div className="panel-b">
            <Bars data={serieBars} h={170} color="var(--brand-500)" />
          </div>
        </div>
        <div className="panel">
          <div className="panel-h">
            <h2>Distribuição por resultado</h2>
          </div>
          <div className="panel-b" style={{ display: "flex", alignItems: "center", gap: 22 }}>
            <Donut
              segments={statusSegs}
              center={
                <div>
                  <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.02em" }}>
                    {fmt.int(op.total_recebidos)}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>exames</div>
                </div>
              }
            />
            <div style={{ display: "flex", flexDirection: "column", gap: 9, flex: 1 }}>
              {statusSegs.map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
                  <span
                    style={{ width: 9, height: 9, borderRadius: 3, background: s.color, flex: "none" }}
                  />
                  <span style={{ color: "var(--ink-2)" }}>{s.label}</span>
                  <span className="mono spacer" style={{ fontWeight: 700 }}>
                    {fmt.int(s.value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* regulatório */}
      <div className="section-title" style={{ marginTop: 24 }}>
        <I.supervisor w={14} />
        Qualidade regulatória
      </div>
      <div className="grid g-3">
        <div className="panel">
          <div className="panel-h">
            <h2>Divergências IA × examinador</h2>
          </div>
          <div className="panel-b" style={{ display: "flex", alignItems: "center", gap: 18 }}>
            <Donut
              size={120}
              segments={divSegs}
              center={
                <div>
                  <div style={{ fontSize: 22, fontWeight: 800 }}>{totalDiv}</div>
                  <div style={{ fontSize: 10.5, color: "var(--muted)" }}>OS abertas</div>
                </div>
              }
            />
            <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
              {divSegs.map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color }} />
                  <span style={{ color: "var(--ink-2)" }}>{s.label}</span>
                  <span className="mono spacer" style={{ fontWeight: 700 }}>
                    {s.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="panel">
          <div className="panel-h">
            <h2>Top infrações detectadas</h2>
          </div>
          <div className="panel-b">
            <HBars items={topInfra.slice(0, 6)} />
          </div>
        </div>
        <div className="panel">
          <div className="panel-h">
            <h2>Indicadores</h2>
          </div>
          <div className="panel-b" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <MiniStat label="Taxa de interrupção" value={fmt.pct(reg.taxa_interrupcao_pct)} />
            <MiniStat
              label="Evidência insuficiente"
              value={fmt.pct(reg.taxa_evidencia_insuficiente_pct)}
            />
            <MiniStat
              label="Comentários inadequados (examinador)"
              value={reg.comentarios_inadequados_examinador}
            />
            <MiniStat
              label="Concordância Supervisor × IA"
              value={fmt.pct(sup.concordancia_supervisor_ia_pct)}
            />
            <MiniStat label="Taxa de erro do pipeline" value={fmt.pct(op.taxa_erro * 100)} />
          </div>
        </div>
      </div>

      {/* OS + unidades */}
      <div className="grid g-2" style={{ marginTop: 16 }}>
        <div className="panel">
          <div className="panel-h">
            <h2>Ordens de Serviço pendentes</h2>
            <span className="spacer" />
            <a className="btn btn-sm" href="Painel do Auditor.html">
              Abrir fila <I.right w={14} />
            </a>
          </div>
          <div className="panel-b" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {Object.entries(op.os_pendentes_por_status).map(([k, v]) => (
              <div
                key={k}
                style={{
                  flex: "1 1 130px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--r)",
                  padding: "12px 14px",
                }}
              >
                <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-.02em" }}>{v}</div>
                <div
                  style={{ fontSize: 11.5, color: "var(--muted)", textTransform: "capitalize" }}
                >
                  {k.replace(/_/g, " ")}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <div className="panel-h">
            <h2>Divergência por unidade</h2>
          </div>
          <div className="panel-b">
            <HBars items={porUnidade} color="var(--warn)" />
          </div>
        </div>
      </div>
    </Shell>
  );
}
