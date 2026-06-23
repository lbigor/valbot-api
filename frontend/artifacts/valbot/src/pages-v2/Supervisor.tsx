/* ============================================================================
   ValBot — Painel do Supervisor (instância final §11.4)
   Fila de divergências para arbitrar + produtividade da equipe.
   Porte fiel de .design-ref/page-supervisor.jsx → React+Vite+TS.

   DADOS REAIS (sem mock):
     GET /api/os                               → fila de arbitragem (queryKey v2-os)
     GET /api/dashboard/supervisor-metrics?dias=30 → KPIs (queryKey v2-sup-metrics)
   Produtividade por auditor não tem endpoint → estado vazio / derivação leve.
   ============================================================================ */
import { useState, useMemo } from "react";
import { useLocation } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/system/Shell";
import { Kpi, fmt } from "@/system/ui";
import { I } from "@/system/icons";

/* ---------------- contrato GET /api/os (item) ---------------- */
interface OSItem {
  os_id: string | number;
  numero_os?: string;
  exam_hash?: string;
  renach?: string;
  candidato_nome?: string;
  categoria?: string;
  unidade?: string;
  examinador?: string;
  tipo_divergencia?: string;
  tipo_label?: string;
  status?: string;
  resultado_oficial?: string | null;
  resultado_calculado?: string | null;
  pontuacao_calculada?: number | null;
  auditor_email?: string | null;
  aberta_em?: string | null;
  sla_due_at?: string | null;
  conf?: number | null;
}

interface SupervisorMetrics {
  total_decisoes?: number;
  homologadas?: number;
  reformadas?: number;
  concordancia_supervisor_auditor_pct?: number;
  concordancia_supervisor_ia_pct?: number;
}

/* ---------------- consts locais (eram VB.*) ---------------- */
const TIPO_DIV_LABEL: Record<string, string> = {
  resultado: "resultado",
  pontuacao: "pontuação",
  infracao: "infração",
  sem_divergencia: "sem divergência",
};

/* prioridade derivada do tipo de divergência (era o.prioridade do mock) */
function prioridadeDe(tipo?: string): number {
  const t = (tipo ?? "").toLowerCase();
  if (t.includes("result")) return 1;
  if (t.includes("pont")) return 2;
  return 3;
}

/* SLA em horas a partir de sla_due_at; estourado quando vencido */
function slaDe(due?: string | null): { horas: number; estourado: boolean } {
  if (!due) return { horas: 0, estourado: false };
  const ms = new Date(due).getTime() - Date.now();
  if (Number.isNaN(ms)) return { horas: 0, estourado: false };
  return { horas: Math.abs(ms) / 3.6e6, estourado: ms < 0 };
}

function labelDivergencia(o: OSItem): string {
  return o.tipo_label ?? (o.tipo_divergencia && TIPO_DIV_LABEL[o.tipo_divergencia]) ?? o.tipo_divergencia ?? "Divergência";
}

/* ---------------- fetchers (credentials:include) ---------------- */
async function fetchFila(): Promise<OSItem[]> {
  const r = await fetch("/api/os", { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const j = await r.json();
  return Array.isArray(j) ? j : (j?.items ?? []);
}
async function fetchMetrics(dias: number): Promise<SupervisorMetrics> {
  const r = await fetch(`/api/dashboard/supervisor-metrics?dias=${dias}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<SupervisorMetrics>;
}

interface EquipeRow {
  auditor: string;
  sessoes: number;
}

export default function Supervisor() {
  const [tab, setTab] = useState<"fila" | "equipe">("fila");
  const [, navigate] = useLocation();

  const { data: fila = [], isLoading: loadingFila, isError: errFila } = useQuery({
    queryKey: ["v2-os"],
    queryFn: fetchFila,
    refetchInterval: 30000,
  });
  const { data: sup, isError: errSup } = useQuery({
    queryKey: ["v2-sup-metrics"],
    queryFn: () => fetchMetrics(30),
  });

  const ordenada = useMemo(
    () =>
      [...fila].sort((a, b) => {
        const pa = prioridadeDe(a.tipo_divergencia);
        const pb = prioridadeDe(b.tipo_divergencia);
        if (pa !== pb) return pa - pb;
        return slaDe(b.sla_due_at).horas - slaDe(a.sla_due_at).horas;
      }),
    [fila]
  );

  const aguardandoSup = useMemo(
    () => fila.filter((o) => o.status === "aguardando_supervisor").length,
    [fila]
  );

  // Produtividade: SEM endpoint próprio. Deriva o que der dos auditores presentes
  // nas OS (auditor_email) — apenas contagem de OS por auditor; sem inventar % de
  // vídeo, tempo ou concordância (que vinham da telemetria mockada).
  const equipe = useMemo<EquipeRow[]>(() => {
    const byA: Record<string, EquipeRow> = {};
    fila.forEach((o) => {
      if (!o.auditor_email) return;
      const a = byA[o.auditor_email] || (byA[o.auditor_email] = { auditor: o.auditor_email, sessoes: 0 });
      a.sessoes++;
    });
    return Object.values(byA).sort((a, b) => b.sessoes - a.sessoes);
  }, [fila]);

  const goAnalise = (o: OSItem) =>
    navigate("/supervisor/analise/" + encodeURIComponent(String(o.os_id)));

  const tabs = (
    <div className="seg">
      <button className={tab === "fila" ? "on" : ""} onClick={() => setTab("fila")}>
        <I.fila w={15} />
        Fila de arbitragem
      </button>
      <button className={tab === "equipe" ? "on" : ""} onClick={() => setTab("equipe")}>
        <I.usuarios w={15} />
        Produtividade
      </button>
    </div>
  );

  return (
    <Shell
      active="supervisor"
      title="Supervisor"
      sub="Instância final · arbitragem de divergências e produtividade da equipe"
      actions={tabs}
    >
      <div className="grid g-4">
        <Kpi
          icon={I.fila}
          label="Aguardando supervisor"
          value={aguardandoSup}
          iconColor="var(--brand)"
          iconBg="var(--brand-tint)"
          foot={<span>na fila de arbitragem</span>}
        />
        <Kpi
          icon={I.supervisor}
          label="Decisões (30d)"
          value={sup?.total_decisoes ?? 0}
          foot={
            <span>
              {sup?.homologadas ?? 0} homologadas · {sup?.reformadas ?? 0} reformadas
            </span>
          }
          iconColor="var(--proc)"
          iconBg="var(--proc-bg)"
        />
        <Kpi
          icon={I.check}
          label="Concordância c/ Auditor"
          value={fmt.pct(sup?.concordancia_supervisor_auditor_pct ?? 0)}
          iconColor="var(--ok)"
          iconBg="var(--ok-bg)"
          foot={<span>homologação do parecer</span>}
        />
        <Kpi
          icon={I.target}
          label="Concordância c/ IA"
          value={fmt.pct(sup?.concordancia_supervisor_ia_pct ?? 0)}
          iconColor="var(--warn)"
          iconBg="var(--warn-bg)"
          foot={<span>decisão final × cálculo</span>}
        />
      </div>

      {tab === "fila" && (
        <div className="tbl-wrap" style={{ marginTop: 18 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>OS</th>
                <th>Candidato</th>
                <th>Divergência</th>
                <th>Oficial × Val</th>
                <th>Auditor</th>
                <th>SLA</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {ordenada.map((o) => {
                const prio = prioridadeDe(o.tipo_divergencia);
                const sla = slaDe(o.sla_due_at);
                return (
                  <tr key={String(o.os_id)} className="clickable" onClick={() => goAnalise(o)}>
                    <td>
                      <div className="mono t-strong">{o.numero_os ?? o.os_id}</div>
                      <div className="t-sub">{o.aberta_em ? fmt.ago(o.aberta_em) : "—"}</div>
                    </td>
                    <td>
                      <div className="t-strong">{o.candidato_nome ?? "—"}</div>
                      <div className="t-sub mono">
                        {o.renach ?? "—"}
                        {o.categoria ? " · Cat " + o.categoria : ""}
                      </div>
                    </td>
                    <td>
                      <span
                        className={
                          "badge " + (prio === 1 ? "bad" : prio === 2 ? "warn" : "proc")
                        }
                      >
                        <span className="bd" />
                        {labelDivergencia(o)}
                      </span>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        <ResChip c={o.resultado_oficial ?? null} />
                        <span className="faint">×</span>
                        <ResChip c={o.resultado_calculado ?? null} val />
                      </div>
                    </td>
                    <td>
                      {o.auditor_email ? (
                        <span className="t-sub">{o.auditor_email.split("@")[0]}</span>
                      ) : (
                        <span className="badge neutral">
                          <span className="bd" />
                          não atribuído
                        </span>
                      )}
                    </td>
                    <td>
                      <SlaPill horas={sla.horas} estourado={sla.estourado} />
                    </td>
                    <td>
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          goAnalise(o);
                        }}
                      >
                        Arbitrar
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="tbl-foot">
            <I.fila w={14} />
            {loadingFila
              ? "Carregando ordens…"
              : errFila
                ? "Não foi possível carregar a fila."
                : `${ordenada.length} ordens na esteira · prioridade 1 = divergência de resultado`}
          </div>
        </div>
      )}

      {tab === "equipe" && (
        <div className="tbl-wrap" style={{ marginTop: 18 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Auditor</th>
                <th>OS na fila</th>
              </tr>
            </thead>
            <tbody>
              {equipe.map((a, i) => (
                <tr key={i}>
                  <td>
                    <div className="row" style={{ gap: 9 }}>
                      <span className="sb-ava" style={{ width: 30, height: 30, fontSize: 11 }}>
                        {a.auditor.slice(0, 2).toUpperCase()}
                      </span>
                      <span className="t-strong">{a.auditor.split("@")[0]}</span>
                    </div>
                  </td>
                  <td className="num t-strong">{a.sessoes}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="tbl-foot">
            <I.medicao w={14} />
            {errSup || equipe.length === 0
              ? "Sem dados de produtividade."
              : "Derivado das OS atribuídas · telemetria de revisão indisponível neste ambiente"}
          </div>
        </div>
      )}
    </Shell>
  );
}

/* ---------------- locais (porte fiel) ---------------- */

function ResChip({ c, val }: { c: string | null; val?: boolean }) {
  const map: Record<string, [string, string]> = {
    A: ["ok", "Apto"],
    R: ["bad", "Reprov."],
    N: ["neutral", "S/ aval."],
  };
  const [cls, label] = (c && map[c]) || ["neutral", "—"];
  return (
    <span
      className={"badge " + cls}
      title={val ? "Calculado pelo Val" : "Resultado oficial"}
    >
      <span className="bd" />
      {label}
    </span>
  );
}

function SlaPill({ horas, estourado }: { horas: number; estourado: boolean }) {
  return (
    <span className={"badge " + (estourado ? "bad" : horas > 36 ? "warn" : "neutral")}>
      <I.clock w={13} />
      {horas < 24 ? horas.toFixed(0) + "h" : (horas / 24).toFixed(1) + "d"}
    </span>
  );
}
