import { type ReactNode, useEffect, useMemo, useState } from "react";
import { AppLayout } from "../components/AppLayout";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Clock, Play, RefreshCw, Save, Calendar, AlertTriangle, CheckCircle2, Zap } from "lucide-react";
import "./Agendamento.css";

// Tela de Agendamento — scheduler de batch Gemini.
// Configura a cron que dispara o envio de vídeos pendentes ao Gemini em lote.
// Contrato (todos os fetchers inline, credentials:include; tolera vazio/erro):
//   GET   /api/admin/cron-jobs            -> CronJob[]
//   POST  /api/admin/cron-jobs           (criar/salvar config)
//   PATCH /api/admin/cron-jobs/{id}      (salvar config)
//   POST  /api/admin/cron-jobs/{id}/trigger   (disparar agora)
//   GET   /api/admin/cron-jobs/{id}/runs -> CronRun[]

type ScheduleKind = "diario" | "cada_n_horas" | "semanal" | "cron";
type Escopo = "queued" | "failed";

interface CronJob {
  id: string;
  nome: string;
  enabled: boolean;
  schedule_kind: ScheduleKind;
  horario: string; // "HH:MM" (diario/semanal) ou "N" (cada_n_horas, qtd de horas)
  cron_expr: string;
  batch_limit: number;
  retry: number;
  escopo: Escopo;
  proxima_execucao: string | null;
}

interface CronRun {
  iniciado_em: string;
  finalizado_em: string | null;
  n_processados: number;
  n_falhas: number;
  custo_usd: number;
  status: string;
}

const usd = (n: number) => "$" + (n ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int = (n: number) => (n ?? 0).toLocaleString("pt-BR");
const dt = (s: string | null) =>
  s ? new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—";

const DEFAULT_JOB: CronJob = {
  id: "",
  nome: "Batch Gemini",
  enabled: false,
  schedule_kind: "diario",
  horario: "03:00",
  cron_expr: "0 3 * * *",
  batch_limit: 20,
  retry: 1,
  escopo: "queued",
  proxima_execucao: null,
};

// ---- fetchers inline ----
async function fetchJobs(): Promise<CronJob[]> {
  try {
    const r = await fetch("/api/admin/cron-jobs", { credentials: "include" });
    if (!r.ok) return [];
    const j = await r.json();
    return (Array.isArray(j) ? j : (j?.items ?? [])) as CronJob[];
  } catch {
    return [];
  }
}
async function fetchRuns(id: string): Promise<CronRun[]> {
  if (!id) return [];
  try {
    const r = await fetch(`/api/admin/cron-jobs/${encodeURIComponent(id)}/runs`, { credentials: "include" });
    if (!r.ok) return [];
    const j = await r.json();
    return (Array.isArray(j) ? j : (j?.runs ?? j?.items ?? [])) as CronRun[];
  } catch {
    return [];
  }
}
async function saveJob(job: CronJob): Promise<CronJob> {
  const isUpdate = !!job.id;
  const url = isUpdate ? `/api/admin/cron-jobs/${encodeURIComponent(job.id)}` : "/api/admin/cron-jobs";
  const r = await fetch(url, {
    method: isUpdate ? "PATCH" : "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(job),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return (await r.json()) as CronJob;
}
async function triggerJob(id: string): Promise<void> {
  const r = await fetch(`/api/admin/cron-jobs/${encodeURIComponent(id)}/trigger`, {
    method: "POST",
    credentials: "include",
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
}

// Deriva uma expressão cron a partir da frequência amigável.
function deriveCron(kind: ScheduleKind, horario: string, current: string): string {
  if (kind === "cron") return current;
  if (kind === "cada_n_horas") {
    const n = Math.max(1, Math.min(23, parseInt(horario || "1", 10) || 1));
    return `0 */${n} * * *`;
  }
  const [hh, mm] = (horario || "00:00").split(":");
  const h = parseInt(hh || "0", 10) || 0;
  const m = parseInt(mm || "0", 10) || 0;
  if (kind === "semanal") return `${m} ${h} * * 1`; // segunda-feira
  return `${m} ${h} * * *`; // diário
}

// ---- UI helpers (CSS-vars, mesmo padrão de Custos.tsx) ----
function Card({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="ag-card">
      <div className="ag-card-head">
        <h3>{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="ag-field">
      <span className="ag-field-label">{label}</span>
      {children}
    </label>
  );
}

export function Agendamento() {
  const qc = useQueryClient();
  const { data: jobs, isLoading } = useQuery({ queryKey: ["cron-jobs"], queryFn: fetchJobs });

  const [draft, setDraft] = useState<CronJob>(DEFAULT_JOB);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  // Sincroniza o form com o primeiro job retornado (config única do batch).
  useEffect(() => {
    if (jobs && jobs.length > 0) setDraft({ ...DEFAULT_JOB, ...jobs[0] });
  }, [jobs]);

  const jobId = draft.id;
  const { data: runs } = useQuery({
    queryKey: ["cron-runs", jobId],
    queryFn: () => fetchRuns(jobId),
    enabled: !!jobId,
  });

  const set = <K extends keyof CronJob>(k: K, v: CronJob[K]) =>
    setDraft((d) => {
      const next = { ...d, [k]: v };
      // Mantém cron_expr coerente quando edita a frequência amigável.
      if (k === "schedule_kind" || k === "horario") {
        next.cron_expr = deriveCron(next.schedule_kind, next.horario, d.cron_expr);
      }
      return next;
    });

  const saveMut = useMutation({
    mutationFn: () => saveJob({ ...draft, cron_expr: deriveCron(draft.schedule_kind, draft.horario, draft.cron_expr) }),
    onSuccess: (saved) => {
      setDraft({ ...DEFAULT_JOB, ...saved });
      setMsg({ kind: "ok", text: "Configuração salva." });
      qc.invalidateQueries({ queryKey: ["cron-jobs"] });
    },
    onError: () => setMsg({ kind: "err", text: "Falha ao salvar a configuração." }),
  });

  const triggerMut = useMutation({
    mutationFn: () => triggerJob(jobId),
    onSuccess: () => {
      setMsg({ kind: "ok", text: "Disparo manual enviado." });
      qc.invalidateQueries({ queryKey: ["cron-runs", jobId] });
    },
    onError: () => setMsg({ kind: "err", text: "Falha ao disparar agora." }),
  });

  const proxima = useMemo(() => dt(draft.proxima_execucao), [draft.proxima_execucao]);

  return (
    <AppLayout activePage="Agendamento">
      <div className="ag-wrap">
        <h1 className="ag-title">Agendamento</h1>
        <p className="ag-subtitle">
          Scheduler do batch Gemini — define a cron que dispara o envio de vídeos pendentes ao Gemini em lote.
        </p>

        {msg && (
          <div className={`ag-toast ag-toast-${msg.kind}`}>
            {msg.kind === "ok" ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
            {msg.text}
          </div>
        )}

        {isLoading && <p className="ag-muted">Carregando…</p>}

        <div className="ag-grid-2">
          {/* Configuração */}
          <Card
            title="Configuração do batch"
            right={
              <button
                type="button"
                className={`ag-toggle ${draft.enabled ? "on" : ""}`}
                onClick={() => set("enabled", !draft.enabled)}
                title={draft.enabled ? "Ativo" : "Inativo"}
              >
                <span className="ag-toggle-knob" />
                <span className="ag-toggle-text">{draft.enabled ? "Ativo" : "Inativo"}</span>
              </button>
            }
          >
            <div className="ag-form">
              <Field label="Nome">
                <input className="ag-input" value={draft.nome} onChange={(e) => set("nome", e.target.value)} />
              </Field>

              <Field label="Frequência">
                <div className="ag-segment">
                  {([
                    ["diario", "Diário"],
                    ["cada_n_horas", "A cada N horas"],
                    ["semanal", "Semanal"],
                    ["cron", "Expressão cron"],
                  ] as [ScheduleKind, string][]).map(([k, lbl]) => (
                    <button
                      key={k}
                      type="button"
                      className={`ag-seg-btn ${draft.schedule_kind === k ? "active" : ""}`}
                      onClick={() => set("schedule_kind", k)}
                    >
                      {lbl}
                    </button>
                  ))}
                </div>
              </Field>

              {draft.schedule_kind === "diario" && (
                <Field label="Horário (HH:MM)">
                  <input type="time" className="ag-input" value={draft.horario} onChange={(e) => set("horario", e.target.value)} />
                </Field>
              )}
              {draft.schedule_kind === "semanal" && (
                <Field label="Horário (HH:MM) · toda segunda">
                  <input type="time" className="ag-input" value={draft.horario} onChange={(e) => set("horario", e.target.value)} />
                </Field>
              )}
              {draft.schedule_kind === "cada_n_horas" && (
                <Field label="A cada N horas">
                  <input
                    type="number"
                    min={1}
                    max={23}
                    className="ag-input"
                    value={draft.horario}
                    onChange={(e) => set("horario", e.target.value)}
                  />
                </Field>
              )}
              {draft.schedule_kind === "cron" && (
                <Field label="Expressão cron">
                  <input
                    className="ag-input mono"
                    placeholder="0 3 * * *"
                    value={draft.cron_expr}
                    onChange={(e) => set("cron_expr", e.target.value)}
                  />
                </Field>
              )}

              <div className="ag-cron-preview">
                <Clock size={13} />
                <span>cron resultante:</span>
                <code className="mono">{deriveCron(draft.schedule_kind, draft.horario, draft.cron_expr) || "—"}</code>
              </div>

              <div className="ag-form-row">
                <Field label="Vídeos por batch">
                  <input
                    type="number"
                    min={1}
                    className="ag-input"
                    value={draft.batch_limit}
                    onChange={(e) => set("batch_limit", Math.max(1, parseInt(e.target.value || "1", 10) || 1))}
                  />
                </Field>
                <Field label="Retry (tentativas)">
                  <input
                    type="number"
                    min={0}
                    className="ag-input"
                    value={draft.retry}
                    onChange={(e) => set("retry", Math.max(0, parseInt(e.target.value || "0", 10) || 0))}
                  />
                </Field>
              </div>

              <Field label="Escopo">
                <div className="ag-segment">
                  <button
                    type="button"
                    className={`ag-seg-btn ${draft.escopo === "queued" ? "active" : ""}`}
                    onClick={() => set("escopo", "queued")}
                  >
                    Pendentes (queued)
                  </button>
                  <button
                    type="button"
                    className={`ag-seg-btn ${draft.escopo === "failed" ? "active" : ""}`}
                    onClick={() => set("escopo", "failed")}
                  >
                    Reprocessar (failed)
                  </button>
                </div>
              </Field>

              <div className="ag-actions">
                <button className="ag-btn ag-btn-primary" disabled={saveMut.isPending} onClick={() => saveMut.mutate()}>
                  <Save size={15} />
                  {saveMut.isPending ? "Salvando…" : "Salvar configuração"}
                </button>
                <button
                  className="ag-btn ag-btn-accent"
                  disabled={!jobId || triggerMut.isPending}
                  onClick={() => triggerMut.mutate()}
                  title={!jobId ? "Salve a configuração antes de disparar" : "Disparar batch agora"}
                >
                  <Zap size={15} />
                  {triggerMut.isPending ? "Disparando…" : "Disparar agora"}
                </button>
              </div>
            </div>
          </Card>

          {/* Status / próxima execução */}
          <div className="ag-side">
            <Card title="Próxima execução">
              <div className="ag-next">
                <Calendar size={18} className="ag-next-icon" />
                <div>
                  <div className="ag-next-value">{draft.enabled ? proxima : "Desativado"}</div>
                  <div className="ag-muted ag-next-sub">
                    {draft.enabled ? "agendamento ativo" : "ative o agendamento para programar"}
                  </div>
                </div>
              </div>
            </Card>
            <Card title="Resumo">
              <ul className="ag-summary">
                <li><span>Escopo</span><b>{draft.escopo === "queued" ? "Pendentes" : "Reprocessar falhas"}</b></li>
                <li><span>Vídeos / batch</span><b>{int(draft.batch_limit)}</b></li>
                <li><span>Tentativas</span><b>{int(draft.retry)}</b></li>
                <li><span>Status</span><b className={draft.enabled ? "ag-on" : "ag-off"}>{draft.enabled ? "Ativo" : "Inativo"}</b></li>
              </ul>
            </Card>
          </div>
        </div>

        {/* Histórico de execuções */}
        <Card
          title="Histórico de execuções"
          right={
            <button
              className="ag-btn ag-btn-ghost"
              onClick={() => qc.invalidateQueries({ queryKey: ["cron-runs", jobId] })}
              disabled={!jobId}
            >
              <RefreshCw size={14} /> Atualizar
            </button>
          }
        >
          <table className="ag-table">
            <thead>
              <tr>
                <th>Início</th>
                <th>Fim</th>
                <th className="r">Processados</th>
                <th className="r">Falhas</th>
                <th className="r">Custo USD</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(!runs || runs.length === 0) && (
                <tr>
                  <td colSpan={6} className="ag-empty">Nenhuma execução registrada.</td>
                </tr>
              )}
              {(runs ?? []).map((r, i) => {
                const st = (r.status || "").toLowerCase();
                const cls = st.includes("ok") || st.includes("success") || st.includes("conclu")
                  ? "ok"
                  : st.includes("fail") || st.includes("err") || st.includes("falh")
                  ? "err"
                  : "run";
                return (
                  <tr key={r.iniciado_em + "-" + i}>
                    <td>{dt(r.iniciado_em)}</td>
                    <td>{dt(r.finalizado_em)}</td>
                    <td className="r mono">{int(r.n_processados)}</td>
                    <td className="r mono">{int(r.n_falhas)}</td>
                    <td className="r mono">{usd(r.custo_usd)}</td>
                    <td><span className={`ag-badge ag-badge-${cls}`}>{r.status || "—"}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>

        {(!jobs || jobs.length === 0) && !isLoading && (
          <p className="ag-muted ag-hint">
            Nenhum agendamento configurado ainda — preencha o formulário e salve para criar o primeiro.
          </p>
        )}
      </div>
    </AppLayout>
  );
}

export default Agendamento;
