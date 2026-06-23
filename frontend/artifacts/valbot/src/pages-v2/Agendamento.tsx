/* ============================================================================
   ValBot — Agendamento · cron_jobs + cron_job_runs (migration 021)
   Cria/edita agendamentos de processamento em lote de exames pendentes.
   Religado a /api/admin/cron-jobs (dados reais). Layout idêntico ao porte fiel.
   ----------------------------------------------------------------------------
   Contrato (credentials:"include"):
     GET   /api/admin/cron-jobs            -> { count, items:[CronJob], runs:[CronRun],
                                                scheduler:{disponivel,rodando,jobs_registrados}, source }
     POST  /api/admin/cron-jobs           (criar) · body do job
     PATCH /api/admin/cron-jobs/{id}      (atualizar)
     POST  /api/admin/cron-jobs/{id}/trigger   (disparar agora)
     GET   /api/admin/cron-jobs/{id}/runs -> { runs:[CronRun] }
   Datas chegam como string ISO → convertidas p/ Date (a tela faz aritmética .getTime()).
   ============================================================================ */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Shell } from "@/system/Shell";
import { Kpi, fmt } from "@/system/ui";
import { I } from "@/system/icons";

const USD_BRL = 5.42;

/* ---- shapes consumidos pela tela (datas como Date após mapeamento) ---- */
interface CronJob {
  id: string;
  nome: string;
  enabled: boolean;
  schedule_kind: "daily" | "hourly" | "interval" | "cron";
  horario: string | null;
  cron_expr: string | null;
  batch_limit: number;
  retry: number;
  escopo: string;
  categoria: string; // "" = todas | ACC | A | B | C | D | E
}

interface CronRun {
  id: string;
  cron_job_id: string;
  nome: string;
  iniciado_em: Date;
  finalizado_em: Date | null;
  n_processados: number;
  n_falhas: number;
  custo_usd: number;
  status: "running" | "failed" | "success";
}

/* ---- shapes crus do endpoint (datas string ISO) ---- */
interface RawCronJob {
  id: string;
  nome: string;
  enabled: boolean;
  schedule_kind: CronJob["schedule_kind"];
  horario: string | null;
  cron_expr: string | null;
  batch_limit: number;
  retry: number;
  escopo: string;
  categoria?: string | null;
  proxima_execucao?: string | null;
}
interface RawCronRun {
  id?: string;
  cron_job_id?: string;
  nome?: string;
  iniciado_em: string;
  finalizado_em: string | null;
  n_processados: number;
  n_falhas: number;
  custo_usd: number;
  status: string;
}
interface CronBundle {
  jobs: CronJob[];
  runs: CronRun[];
}

const KIND_LABEL: Record<CronJob["schedule_kind"], string> = {
  daily: "Diário",
  hourly: "De hora em hora",
  interval: "Intervalo",
  cron: "Cron",
};
const ESCOPO_LABEL: Record<string, string> = {
  pending: "Pendentes",
  queued: "Na fila",
  failed: "Falhas",
  all: "Todos",
};
/* categoria CNH a processar no batch. "" = todas as categorias. */
const CATEGORIA_LABEL: Record<string, string> = {
  "": "Todas",
  ACC: "ACC",
  A: "A",
  B: "B",
  C: "C",
  D: "D",
  E: "E",
};

const normStatus = (s: string): CronRun["status"] => {
  const t = (s || "").toLowerCase();
  if (t.includes("run") || t.includes("exec")) return "running";
  if (t.includes("fail") || t.includes("err") || t.includes("falh")) return "failed";
  return "success";
};

const mapRun = (r: RawCronRun, i: number): CronRun => ({
  id: r.id ?? r.iniciado_em + "_" + i,
  cron_job_id: r.cron_job_id ?? "",
  nome: r.nome ?? "",
  iniciado_em: new Date(r.iniciado_em),
  finalizado_em: r.finalizado_em ? new Date(r.finalizado_em) : null,
  n_processados: r.n_processados ?? 0,
  n_falhas: r.n_falhas ?? 0,
  custo_usd: r.custo_usd ?? 0,
  status: normStatus(r.status),
});

/* ---- fetcher: bundle único de /api/admin/cron-jobs ---- */
async function fetchCronJobs(): Promise<CronBundle> {
  const r = await fetch("/api/admin/cron-jobs", { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const j = await r.json();
  const rawJobs: RawCronJob[] = Array.isArray(j) ? j : (j?.items ?? []);
  const rawRuns: RawCronRun[] = Array.isArray(j) ? [] : (j?.runs ?? []);
  return {
    jobs: rawJobs.map((x) => ({
      id: x.id,
      nome: x.nome,
      enabled: x.enabled,
      schedule_kind: x.schedule_kind,
      horario: x.horario ?? null,
      cron_expr: x.cron_expr ?? null,
      batch_limit: x.batch_limit,
      retry: x.retry,
      escopo: x.escopo,
      categoria: (x.categoria ?? "") || "",
    })),
    runs: rawRuns.map(mapRun),
  };
}

/* ---- payload enviado ao backend (id fora do body em update) ---- */
function jobBody(j: CronJob): Record<string, unknown> {
  return {
    nome: j.nome,
    enabled: j.enabled,
    schedule_kind: j.schedule_kind,
    horario: j.horario,
    cron_expr: j.cron_expr,
    batch_limit: j.batch_limit,
    retry: j.retry,
    escopo: j.escopo,
    categoria: j.categoria || "", // "" => backend trata como "todas"
  };
}
async function createJob(j: CronJob): Promise<void> {
  const r = await fetch("/api/admin/cron-jobs", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(jobBody(j)),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
}
async function updateJob(j: CronJob): Promise<void> {
  const r = await fetch(`/api/admin/cron-jobs/${encodeURIComponent(j.id)}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(jobBody(j)),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
}
async function triggerJob(id: string, categoria?: string): Promise<void> {
  const r = await fetch(`/api/admin/cron-jobs/${encodeURIComponent(id)}/trigger`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    // "" => backend processa todas as categorias
    body: JSON.stringify({ categoria: categoria || "" }),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
}

interface EditState {
  mode: "new" | "edit";
  job: CronJob;
}

let _t: ReturnType<typeof setTimeout> | undefined;

export default function Agendamento() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["v2-cron-jobs"],
    queryFn: fetchCronJobs,
  });
  const jobs = data?.jobs ?? [];
  const runs = data?.runs ?? [];

  const [edit, setEdit] = useState<EditState | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => {
    setToast(m);
    clearTimeout(_t);
    _t = setTimeout(() => setToast(null), 1900);
  };
  const invalidate = () => qc.invalidateQueries({ queryKey: ["v2-cron-jobs"] });

  const toggleMut = useMutation({
    mutationFn: (j: CronJob) => updateJob({ ...j, enabled: !j.enabled }),
    onSuccess: invalidate,
    onError: () => flash("Falha ao atualizar"),
  });
  const saveMut = useMutation({
    mutationFn: (p: { mode: "new" | "edit"; job: CronJob }) =>
      p.mode === "new" ? createJob(p.job) : updateJob(p.job),
    onSuccess: (_d, p) => {
      setEdit(null);
      flash(p.mode === "new" ? "Agendamento criado" : "Agendamento salvo");
      invalidate();
    },
    onError: () => flash("Falha ao salvar"),
  });
  const triggerMut = useMutation({
    mutationFn: (j: CronJob) => triggerJob(j.id, j.categoria),
    onSuccess: (_d, j) => {
      const cat = j.categoria ? `categoria ${j.categoria}` : "todas as categorias";
      flash(`Disparado: ${j.nome} · ${cat}`);
      invalidate();
    },
    onError: () => flash("Falha ao disparar"),
  });

  const NOW = new Date();
  const ativos = jobs.filter((j) => j.enabled).length;
  const last24 = runs.filter((r) => NOW.getTime() - r.iniciado_em.getTime() < 86400000);
  const proc24 = last24.reduce((s, r) => s + r.n_processados, 0);
  const fail24 = last24.reduce((s, r) => s + r.n_falhas, 0);

  const desc = (j: CronJob): string =>
    j.schedule_kind === "daily"
      ? `Diariamente às ${j.horario}`
      : j.schedule_kind === "hourly"
        ? "A cada hora"
        : j.schedule_kind === "interval"
          ? `A cada ${(j.horario || "*/15").replace("*/", "")} min`
          : `cron: ${j.cron_expr}`;
  const toggle = (j: CronJob) => toggleMut.mutate(j);
  const save = (mode: "new" | "edit", j: CronJob) => saveMut.mutate({ mode, job: j });

  const actions = (
    <button
      className="btn btn-primary"
      onClick={() =>
        setEdit({
          mode: "new",
          job: {
            id: "cj" + Date.now(),
            nome: "",
            enabled: true,
            schedule_kind: "daily",
            horario: "02:00",
            cron_expr: "",
            batch_limit: 50,
            retry: 1,
            escopo: "pending",
            categoria: "",
          },
        })
      }
    >
      <I.plus w={16} />
      Novo agendamento
    </button>
  );

  return (
    <Shell
      active="agendamento"
      title="Agendamento"
      sub="Processamento em lote de exames pendentes · cron jobs"
      actions={actions}
    >
      <div className="grid g-4">
        <Kpi
          icon={I.agendamento}
          label="Agendamentos ativos"
          value={ativos}
          foot={<span>de {jobs.length} cadastrados</span>}
          iconColor="var(--brand)"
          iconBg="var(--brand-tint)"
        />
        <Kpi
          icon={I.bolt}
          label="Processados (24h)"
          value={fmt.int(proc24)}
          iconColor="var(--ok)"
          iconBg="var(--ok-bg)"
        />
        <Kpi
          icon={I.alert}
          label="Falhas (24h)"
          value={fail24}
          deltaDir={fail24 > 5 ? "down" : "flat"}
          iconColor="var(--bad)"
          iconBg="var(--bad-bg)"
        />
        <Kpi
          icon={I.custos}
          label="Custo (24h)"
          value={fmt.brl(last24.reduce((s, r) => s + r.custo_usd, 0) * USD_BRL)}
          iconColor="var(--warn)"
          iconBg="var(--warn-bg)"
        />
      </div>

      {(isLoading || isError) && (
        <div className="t-sub" style={{ marginTop: 16 }}>
          {isLoading ? "Carregando agendamentos…" : "Não foi possível carregar os agendamentos."}
        </div>
      )}

      {/* jobs */}
      <div className="section-title" style={{ marginTop: 24 }}>
        <I.agendamento w={14} />
        Agendamentos
      </div>
      <div className="grid g-2">
        {jobs.map((j) => (
          <div key={j.id} className="panel">
            <div className="panel-b" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div className="row">
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: "-.01em" }}>
                    {j.nome}
                  </div>
                  <div className="t-sub" style={{ marginTop: 2 }}>
                    {desc(j)} · {KIND_LABEL[j.schedule_kind]}
                  </div>
                </div>
                <span className="spacer" />
                <Toggle on={j.enabled} onToggle={() => toggle(j)} />
              </div>
              <div className="row wrap" style={{ gap: 8 }}>
                <span className="badge neutral">
                  <I.video w={13} />
                  {ESCOPO_LABEL[j.escopo] ?? j.escopo}
                </span>
                <span className="badge neutral">
                  cat {j.categoria ? j.categoria : "todas"}
                </span>
                <span className="badge neutral">lote {j.batch_limit}</span>
                <span className="badge neutral">retry {j.retry}</span>
                {j.enabled ? (
                  <span className="badge ok">
                    <span className="bd" />
                    ativo
                  </span>
                ) : (
                  <span className="badge neutral">
                    <span className="bd" />
                    pausado
                  </span>
                )}
              </div>
              <div
                className="row"
                style={{ gap: 8, borderTop: "1px solid var(--border)", paddingTop: 12 }}
              >
                <button className="btn btn-sm" onClick={() => triggerMut.mutate(j)}>
                  <I.play w={14} />
                  Rodar agora
                </button>
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={() => setEdit({ mode: "edit", job: { ...j } })}
                >
                  <I.edit w={14} />
                  Editar
                </button>
                <span className="spacer t-sub">
                  {(() => {
                    const lr = runs.find((r) => r.cron_job_id === j.id);
                    return lr ? "último: " + fmt.ago(lr.iniciado_em) : "—";
                  })()}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* histórico de execuções */}
      <div className="panel" style={{ marginTop: 24 }}>
        <div className="panel-h">
          <h2>Histórico de execuções</h2>
          <span className="ph-sub">cron_job_runs</span>
        </div>
        <div className="tbl-wrap" style={{ border: "none", boxShadow: "none", borderRadius: 0 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Agendamento</th>
                <th>Início</th>
                <th>Duração</th>
                <th>Processados</th>
                <th>Falhas</th>
                <th>Custo</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 && (
                <tr>
                  <td colSpan={7} className="t-sub" style={{ textAlign: "center", padding: 24 }}>
                    Nenhuma execução registrada.
                  </td>
                </tr>
              )}
              {runs.slice(0, 14).map((r) => {
                const dur = r.finalizado_em
                  ? (r.finalizado_em.getTime() - r.iniciado_em.getTime()) / 1000
                  : null;
                return (
                  <tr key={r.id}>
                    <td className="t-strong">{r.nome}</td>
                    <td className="t-sub mono">{fmt.dmyhm(r.iniciado_em)}</td>
                    <td className="num t-sub">{dur != null ? fmt.dur(dur) : "—"}</td>
                    <td className="num t-strong">{r.n_processados}</td>
                    <td className="num">
                      {r.n_falhas > 0 ? (
                        <span style={{ color: "var(--bad)" }}>{r.n_falhas}</span>
                      ) : (
                        <span className="faint">0</span>
                      )}
                    </td>
                    <td className="num t-sub">{fmt.brl(r.custo_usd * USD_BRL)}</td>
                    <td>
                      <span
                        className={
                          "badge " +
                          (r.status === "success" ? "ok" : r.status === "running" ? "proc" : "bad")
                        }
                      >
                        <span className="bd" />
                        {r.status === "success"
                          ? "concluído"
                          : r.status === "running"
                            ? "executando"
                            : "falhou"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {edit && (
        <JobModal
          mode={edit.mode}
          job={edit.job}
          saving={saveMut.isPending}
          onSave={(j) => save(edit.mode, j)}
          onClose={() => setEdit(null)}
        />
      )}
      {toast && <div className="toast">{toast}</div>}
    </Shell>
  );
}

interface ToggleProps {
  on: boolean;
  onToggle: () => void;
}

function Toggle({ on, onToggle }: ToggleProps) {
  return (
    <button
      onClick={onToggle}
      style={{
        width: 42,
        height: 24,
        borderRadius: 20,
        border: "none",
        padding: 0,
        background: on ? "var(--brand)" : "var(--surface-3)",
        position: "relative",
        transition: "background .15s",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 3,
          left: on ? 21 : 3,
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: "#fff",
          boxShadow: "0 1px 3px rgba(0,0,0,.2)",
          transition: "left .15s",
        }}
      />
    </button>
  );
}

interface JobModalProps {
  mode: "new" | "edit";
  job: CronJob;
  saving?: boolean;
  onSave: (j: CronJob) => void;
  onClose: () => void;
}

function JobModal({ mode, job, saving, onSave, onClose }: JobModalProps) {
  const [j, setJ] = useState<CronJob>(job);
  const set = <K extends keyof CronJob>(k: K, v: CronJob[K]) =>
    setJ((x) => ({ ...x, [k]: v }));
  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div className="modal" style={{ width: 520 }}>
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
            {mode === "new" ? "Novo agendamento" : "Editar agendamento"}
          </div>
          <div style={{ fontSize: 18, fontWeight: 800, marginTop: 3 }}>{j.nome || "Cron job"}</div>
        </div>
        <div style={{ padding: "18px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="fld">
            <label className="fld-l">Nome</label>
            <input
              value={j.nome}
              onChange={(e) => set("nome", e.target.value)}
              placeholder="Ex.: Lote noturno — pendentes"
            />
          </div>
          <div className="fld-row">
            <div className="fld">
              <label className="fld-l">Frequência</label>
              <select
                value={j.schedule_kind}
                onChange={(e) => set("schedule_kind", e.target.value as CronJob["schedule_kind"])}
              >
                {Object.entries(KIND_LABEL).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div className="fld">
              <label className="fld-l">
                {j.schedule_kind === "cron"
                  ? "Expressão cron"
                  : j.schedule_kind === "interval"
                    ? "Intervalo (min)"
                    : "Horário"}
              </label>
              {j.schedule_kind === "cron" ? (
                <input
                  className="mono"
                  value={j.cron_expr || ""}
                  onChange={(e) => set("cron_expr", e.target.value)}
                  placeholder="0 3 * * 0"
                />
              ) : j.schedule_kind === "hourly" ? (
                <input value="—" disabled />
              ) : (
                <input
                  className="mono"
                  value={j.horario || ""}
                  onChange={(e) => set("horario", e.target.value)}
                  placeholder={j.schedule_kind === "interval" ? "*/15" : "02:00"}
                />
              )}
            </div>
          </div>
          <div className="fld-row">
            <div className="fld">
              <label className="fld-l">Escopo</label>
              <select value={j.escopo} onChange={(e) => set("escopo", e.target.value)}>
                {Object.entries(ESCOPO_LABEL).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div className="fld">
              <label className="fld-l">Lote máx.</label>
              <input
                className="mono"
                type="number"
                value={j.batch_limit}
                onChange={(e) => set("batch_limit", +e.target.value)}
              />
            </div>
          </div>
          <div className="fld-row">
            <div className="fld">
              <label className="fld-l">Categoria</label>
              <select
                value={j.categoria || ""}
                onChange={(e) => set("categoria", e.target.value)}
              >
                {Object.entries(CATEGORIA_LABEL).map(([k, l]) => (
                  <option key={k || "todas"} value={k}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div className="fld">
              <label className="fld-l">Retentativas</label>
              <input
                className="mono"
                type="number"
                value={j.retry}
                onChange={(e) => set("retry", +e.target.value)}
              />
            </div>
          </div>
        </div>
        <div className="drawer-f" style={{ borderRadius: "0 0 var(--r-xl) var(--r-xl)" }}>
          <button className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" onClick={() => onSave(j)} disabled={!j.nome || saving}>
            {mode === "new" ? "Criar agendamento" : "Salvar"}
          </button>
        </div>
      </div>
    </>
  );
}
