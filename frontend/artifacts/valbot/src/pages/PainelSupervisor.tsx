import { useState, type ReactNode } from "react";
import { AppLayout } from "../components/AppLayout";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck,
  Scale,
  Clock,
  X,
  ArrowRight,
  User,
  Bot,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import "./PainelSupervisor.css";

// ============================================================================
// Painel do Supervisor (Kanban) — 4º nível de decisão do Valbot.
//
// Fluxo de decisão em camadas:
//   IA (ValBot) → Examinador → Comitê → Auditor → SUPERVISOR (esta tela).
//
// O Supervisor recebe as OS que o Auditor já pareceu e dá a palavra final:
// HOMOLOGAR (mantém o parecer do Auditor) ou REFORMAR (reverte). Tudo em
// Kanban de 3 colunas, com modal de detalhe da OS por cima.
//
// Endpoints consumidos (todos credentials:include, campos opcionais tolerados):
//   GET  /api/os?status=aguardando_supervisor
//   GET  /api/os/{os_id}
//   POST /api/os/{os_id}/decisao   body {decisao, justificativa}
//   GET  /api/dashboard/supervisor-metrics?dias=30
// ============================================================================

// ---- Tipos do contrato (defensivos: quase tudo opcional) -------------------
interface ParecerAuditor {
  decisao?: string;
  justificativa?: string;
  resultado_final?: string;
}
interface OSItem {
  os_id: string | number;
  numero_os?: string;
  exam_hash?: string;
  renach?: string;
  candidato_nome?: string;
  tipo_divergencia?: string;
  resultado_oficial?: string;
  resultado_calculado?: string;
  status?: string;
  parecer_auditor?: ParecerAuditor;
  sla_due_at?: string;
}
interface EventoTrilha {
  ts?: string;
  ator?: string;
  acao?: string;
  detalhe?: string;
}
interface LaudoComite {
  resultado?: string;
  resumo?: string;
  votos?: { membro?: string; voto?: string }[];
}
interface OSDetalhe extends OSItem {
  comite?: LaudoComite;
  parecer?: ParecerAuditor;
  eventos?: EventoTrilha[];
}
interface SupervisorMetrics {
  concordancia_sup_auditor_pct?: number;
  concordancia_sup_ia_pct?: number;
  sla_medio?: string | number;
}

// ---- Helpers ----------------------------------------------------------------
const pct = (n?: number) => (n == null ? "—" : `${Math.round(n)}%`);

// Tempo restante de SLA humanizado + classe de cor (ok / warn / late).
function slaInfo(due?: string): { label: string; cls: string } {
  if (!due) return { label: "—", cls: "" };
  const ms = new Date(due).getTime() - Date.now();
  if (Number.isNaN(ms)) return { label: "—", cls: "" };
  const late = ms < 0;
  const abs = Math.abs(ms);
  const h = Math.floor(abs / 3.6e6);
  const m = Math.floor((abs % 3.6e6) / 6e4);
  const txt = h >= 1 ? `${h}h ${m}m` : `${m}m`;
  if (late) return { label: `atrasada ${txt}`, cls: "late" };
  if (ms < 4 * 3.6e6) return { label: `${txt} restante`, cls: "warn" };
  return { label: `${txt} restante`, cls: "ok" };
}

// Normaliza resultado para rótulo + classe visual.
function resultadoView(v?: string): { label: string; cls: string } {
  const k = (v ?? "").toLowerCase();
  if (k.includes("aprov")) return { label: "Aprovado", cls: "ok" };
  if (k.includes("reprov")) return { label: "Reprovado", cls: "bad" };
  if (!v) return { label: "—", cls: "mut" };
  return { label: v, cls: "mut" };
}

function decisaoAuditorView(v?: string): { label: string; cls: string } {
  const k = (v ?? "").toLowerCase();
  if (k.includes("homolog") || k.includes("mant") || k.includes("concord"))
    return { label: v ?? "Homologar", cls: "ok" };
  if (k.includes("reform") || k.includes("revert") || k.includes("diverg"))
    return { label: v ?? "Reformar", cls: "warn" };
  return { label: v ?? "—", cls: "mut" };
}

// ---- Fetchers (inline, credentials:include) --------------------------------
async function fetchFila(): Promise<OSItem[]> {
  const r = await fetch("/api/os?status=aguardando_supervisor", { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const j = await r.json();
  return Array.isArray(j) ? j : (j?.items ?? []);
}

// Fila do Auditor — exames ainda EM AUDITORIA (mesma fonte da tela do Auditor:
// exames processados com divergência não resolvida pelo Comitê). Informativo
// para o Supervisor: o que está "na mão do auditor" antes de virar OS.
async function fetchAuditorFila(): Promise<OSItem[]> {
  const r = await fetch("/api/videos?only_unresolved=true", { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const j = await r.json();
  const arr: Array<Record<string, unknown>> = Array.isArray(j) ? j : ((j?.items as []) ?? []);
  return arr
    .filter((v) => (v.status ?? "") === "processed" || !!v.has_result)
    .map((v) => ({
      os_id: `exam:${String(v.hash ?? "")}`,
      exam_hash: v.hash as string | undefined,
      renach: (v.renach as string) ?? undefined,
      candidato_nome: ((v.candidato_nome ?? v.candidato) as string) ?? undefined,
      unidade: ((v.local_unidade ?? v.unidade) as string) ?? undefined,
      resultado_oficial: ((v.resultado_exame ?? v.resultado_oficial) as string) ?? undefined,
      resultado_calculado:
        ((v.resultado_calculado as string) ??
          (v.aprovado === true ? "A" : v.aprovado === false ? "R" : undefined)),
      tipo_divergencia: ((v.tipo_divergencia_pos_comite ?? v.tipo_divergencia) as string) ?? undefined,
      status: "em_analise",
    })) as OSItem[];
}
async function fetchDetalhe(osId: string | number): Promise<OSDetalhe> {
  const r = await fetch(`/api/os/${osId}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<OSDetalhe>;
}
async function fetchMetrics(dias: number): Promise<SupervisorMetrics> {
  const r = await fetch(`/api/dashboard/supervisor-metrics?dias=${dias}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<SupervisorMetrics>;
}
async function postDecisao(osId: string | number, decisao: string, justificativa: string) {
  const r = await fetch(`/api/os/${osId}/decisao`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decisao, justificativa }),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json().catch(() => ({}));
}

// ---- Mapeamento de colunas do Kanban ---------------------------------------
// As 3 colunas correspondem a status da OS no funil do Supervisor.
const COLS: { k: string; label: string; color: string; match: (o: OSItem) => boolean }[] = [
  {
    k: "aguardando_supervisor",
    label: "Aguardando Supervisor",
    color: "var(--accent)",
    match: (o) =>
      ["aguardando_supervisor", "em_analise_supervisor", "analise_supervisor"].includes(
        o.status ?? "aguardando_supervisor",
      ),
  },
  {
    k: "encerrada",
    label: "Decisão Final / Encerrada",
    color: "#10B981",
    match: (o) =>
      ["encerrada", "decisao_final", "homologada", "reformada", "finalizada"].includes(o.status ?? ""),
  },
];

// ---- Faixa de métricas ------------------------------------------------------
function MetricPill({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="kan-metric">
      <span className="kan-metric-ico">{icon}</span>
      <div className="kan-metric-txt">
        <span className="kan-metric-val">{value}</span>
        <span className="kan-metric-lbl">{label}</span>
      </div>
    </div>
  );
}

// ---- Card de OS -------------------------------------------------------------
function OSCard({ o, onOpen }: { o: OSItem; onOpen: (o: OSItem) => void }) {
  const oficial = resultadoView(o.resultado_oficial);
  const calc = resultadoView(o.resultado_calculado);
  const par = o.parecer_auditor ?? {};
  const dec = decisaoAuditorView(par.decisao);
  const sla = slaInfo(o.sla_due_at);
  return (
    <button className="kan-card" onClick={() => onOpen(o)}>
      <div className="kan-top">
        <span className="mono kan-renach">{o.renach ?? o.numero_os ?? o.os_id}</span>
        {o.numero_os && <span className="kan-os-num">{o.numero_os}</span>}
      </div>
      {o.candidato_nome && <div className="kan-cand">{o.candidato_nome}</div>}

      {o.tipo_divergencia && (
        <div className="kan-diverg">
          <AlertTriangle size={12} />
          {o.tipo_divergencia}
        </div>
      )}

      {/* Resultado IA (calculado) × Examinador (oficial) */}
      <div className="kan-cmp">
        <div className="kan-cmp-row">
          <span className="kan-cmp-who">Oficial</span>
          <span className={"kan-res " + oficial.cls}>
            <span className="kan-res-dot" />
            {oficial.label}
          </span>
        </div>
        <div className="kan-cmp-row">
          <span className="kan-cmp-who">Calculado (IA)</span>
          <span className={"kan-res " + calc.cls}>
            <span className="kan-res-dot" />
            {calc.label}
          </span>
        </div>
      </div>

      {/* Resumo do parecer do Auditor */}
      {(par.decisao || par.justificativa) && (
        <div className="kan-parecer">
          <div className="kan-parecer-head">
            <User size={11} />
            <span>Auditor</span>
            <span className={"kan-tag " + dec.cls}>{dec.label}</span>
          </div>
          {par.justificativa && <p className="kan-parecer-txt">{par.justificativa}</p>}
        </div>
      )}

      <div className={"kan-foot " + sla.cls}>
        <Clock size={12} />
        <span className="kan-foot-k">SLA</span>
        <b>{sla.label}</b>
        <ArrowRight size={13} style={{ marginLeft: "auto" }} />
      </div>
    </button>
  );
}

// ---- Card informativo da fila do Auditor (read-only) ------------------------
function AuditorCard({ o }: { o: OSItem }) {
  const oficial = resultadoView(o.resultado_oficial);
  const calc = resultadoView(o.resultado_calculado);
  return (
    <div className="kan-card kan-card-ro">
      <div className="kan-top">
        <span className="mono kan-renach">{o.renach ?? o.exam_hash}</span>
      </div>
      {o.candidato_nome && <div className="kan-cand">{o.candidato_nome}</div>}
      {o.tipo_divergencia && (
        <div className="kan-diverg">
          <AlertTriangle size={12} />
          {o.tipo_divergencia}
        </div>
      )}
      <div className="kan-cmp">
        <div className="kan-cmp-row">
          <span className="kan-cmp-who">Oficial</span>
          <span className={"kan-res " + oficial.cls}>
            <span className="kan-res-dot" />
            {oficial.label}
          </span>
        </div>
        <div className="kan-cmp-row">
          <span className="kan-cmp-who">Calculado (IA)</span>
          <span className={"kan-res " + calc.cls}>
            <span className="kan-res-dot" />
            {calc.label}
          </span>
        </div>
      </div>
      <div className="kan-foot mut">
        <User size={12} />
        <span className="kan-foot-k">Em auditoria</span>
      </div>
    </div>
  );
}

// ---- Kanban -----------------------------------------------------------------
function Kanban({
  auditorRows,
  osRows,
  onOpen,
}: {
  auditorRows: OSItem[];
  osRows: OSItem[];
  onOpen: (o: OSItem) => void;
}) {
  return (
    <div className="kanban">
      {/* Coluna informativa: exames ainda na mão do auditor (fila do auditor). */}
      <div className="kan-col">
        <div className="kan-head">
          <span className="kan-dot" style={{ background: "#A78BFA" }} />
          <span className="kan-head-l">Com o Auditor</span>
          <span className="mono kan-count">{auditorRows.length}</span>
        </div>
        <div className="kan-body">
          {auditorRows.slice(0, 50).map((o) => (
            <AuditorCard key={String(o.os_id)} o={o} />
          ))}
          {auditorRows.length > 50 && (
            <div className="kan-empty">
              + {auditorRows.length - 50} exames — veja todos na Fila do Auditor.
            </div>
          )}
          {!auditorRows.length && (
            <div className="kan-empty">Nenhum exame em auditoria.</div>
          )}
        </div>
      </div>
      {COLS.map((c) => {
        const items = osRows.filter(c.match);
        return (
          <div key={c.k} className="kan-col">
            <div className="kan-head">
              <span className="kan-dot" style={{ background: c.color }} />
              <span className="kan-head-l">{c.label}</span>
              <span className="mono kan-count">{items.length}</span>
            </div>
            <div className="kan-body">
              {items.map((o) => (
                <OSCard key={String(o.os_id)} o={o} onOpen={onOpen} />
              ))}
              {!items.length && <div className="kan-empty">Sem OS nesta coluna.</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---- Modal de detalhe da OS -------------------------------------------------
function OSDrawer({ os, onClose }: { os: OSItem; onClose: () => void }) {
  const qc = useQueryClient();
  const [decisao, setDecisao] = useState<"homologar" | "reformar" | null>(null);
  const [justificativa, setJustificativa] = useState("");

  const { data: d, isLoading } = useQuery({
    queryKey: ["os-detalhe", os.os_id],
    queryFn: () => fetchDetalhe(os.os_id),
  });

  const mut = useMutation({
    mutationFn: () => postDecisao(os.os_id, decisao!, justificativa.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["os-fila"] });
      qc.invalidateQueries({ queryKey: ["supervisor-metrics"] });
      onClose();
    },
  });

  // Merge: detalhe quando carregado, senão o item da lista (fallback).
  const v: OSDetalhe = d ?? os;
  const oficial = resultadoView(v.resultado_oficial);
  const calc = resultadoView(v.resultado_calculado);
  const par = v.parecer ?? v.parecer_auditor ?? {};
  const dec = decisaoAuditorView(par.decisao);
  const comite = v.comite;
  const eventos = v.eventos ?? [];
  const canSubmit = !!decisao && justificativa.trim().length > 0 && !mut.isPending;

  return (
    <div className="kan-scrim" onClick={onClose}>
      <div className="kan-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="kan-drawer-head">
          <div className="kan-drawer-title">
            <span className="mono kan-drawer-renach">{v.renach ?? v.numero_os ?? v.os_id}</span>
            {v.numero_os && <span className="kan-os-num">{v.numero_os}</span>}
            {v.tipo_divergencia && (
              <span className="kan-tag warn">
                <AlertTriangle size={11} style={{ verticalAlign: "-1px" }} /> {v.tipo_divergencia}
              </span>
            )}
          </div>
          <button className="kan-icon-btn" onClick={onClose} aria-label="Fechar">
            <X size={18} />
          </button>
        </div>

        <div className="kan-drawer-body">
          {isLoading && <p className="kan-muted">Carregando detalhe da OS…</p>}

          {/* O caso: oficial × calculado */}
          <section className="kan-sec">
            <h4 className="kan-sec-t">O caso</h4>
            {v.candidato_nome && <div className="kan-kv"><span>Candidato</span><b>{v.candidato_nome}</b></div>}
            <div className="kan-compare">
              <div className="kan-compare-box">
                <span className="kan-compare-l">Resultado oficial (examinador)</span>
                <span className={"kan-res lg " + oficial.cls}><span className="kan-res-dot" />{oficial.label}</span>
              </div>
              <div className="kan-compare-vs">×</div>
              <div className="kan-compare-box">
                <span className="kan-compare-l">Resultado calculado (IA)</span>
                <span className={"kan-res lg " + calc.cls}><span className="kan-res-dot" />{calc.label}</span>
              </div>
            </div>
          </section>

          {/* Laudo do Comitê */}
          {comite && (comite.resultado || comite.resumo || comite.votos?.length) && (
            <section className="kan-sec">
              <h4 className="kan-sec-t"><Scale size={13} /> Laudo do Comitê</h4>
              {comite.resultado && (
                <div className="kan-kv">
                  <span>Resultado</span>
                  <span className={"kan-res " + resultadoView(comite.resultado).cls}>
                    <span className="kan-res-dot" />{resultadoView(comite.resultado).label}
                  </span>
                </div>
              )}
              {comite.resumo && <p className="kan-prose">{comite.resumo}</p>}
              {!!comite.votos?.length && (
                <div className="kan-votos">
                  {comite.votos.map((vo, i) => (
                    <span key={i} className="kan-voto">
                      {vo.membro ?? "Membro"}: <b>{vo.voto ?? "—"}</b>
                    </span>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Parecer do Auditor */}
          <section className="kan-sec">
            <h4 className="kan-sec-t"><User size={13} /> Parecer do Auditor</h4>
            <div className="kan-kv">
              <span>Decisão</span>
              <span className={"kan-tag " + dec.cls}>{dec.label}</span>
            </div>
            {par.resultado_final && (
              <div className="kan-kv">
                <span>Resultado final</span>
                <span className={"kan-res " + resultadoView(par.resultado_final).cls}>
                  <span className="kan-res-dot" />{resultadoView(par.resultado_final).label}
                </span>
              </div>
            )}
            {par.justificativa ? (
              <p className="kan-prose">{par.justificativa}</p>
            ) : (
              <p className="kan-muted">Sem justificativa registrada.</p>
            )}
          </section>

          {/* Trilha de eventos */}
          {!!eventos.length && (
            <section className="kan-sec">
              <h4 className="kan-sec-t">Trilha</h4>
              <ul className="kan-trail">
                {eventos.map((e, i) => (
                  <li key={i} className="kan-trail-item">
                    <span className="kan-trail-dot" />
                    <div className="kan-trail-body">
                      <div className="kan-trail-top">
                        <b>{e.acao ?? "evento"}</b>
                        {e.ator && <span className="kan-trail-ator">· {e.ator}</span>}
                        {e.ts && <span className="kan-trail-ts mono">{e.ts}</span>}
                      </div>
                      {e.detalhe && <span className="kan-trail-det">{e.detalhe}</span>}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Decisão do Supervisor */}
          <section className="kan-sec kan-decisao">
            <h4 className="kan-sec-t"><ShieldCheck size={13} /> Decisão do Supervisor</h4>
            <div className="kan-choice">
              <button
                className={"kan-choice-btn ok" + (decisao === "homologar" ? " on" : "")}
                onClick={() => setDecisao("homologar")}
              >
                <CheckCircle2 size={15} /> Homologar
              </button>
              <button
                className={"kan-choice-btn warn" + (decisao === "reformar" ? " on" : "")}
                onClick={() => setDecisao("reformar")}
              >
                <Scale size={15} /> Reformar
              </button>
            </div>
            <textarea
              className="kan-note"
              rows={3}
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              placeholder="Justifique a decisão final (obrigatório)…"
            />
            {mut.isError && <p className="kan-err">Falha ao registrar a decisão. Tente novamente.</p>}
          </section>
        </div>

        <div className="kan-drawer-foot">
          <span className="kan-foot-note">
            {decisao
              ? `Você vai ${decisao === "homologar" ? "homologar" : "reformar"} o parecer do Auditor.`
              : "Selecione Homologar ou Reformar e justifique."}
          </span>
          <button className="kan-btn ghost" onClick={onClose} disabled={mut.isPending}>
            Cancelar
          </button>
          <button className="kan-btn primary" disabled={!canSubmit} onClick={() => mut.mutate()}>
            {mut.isPending ? "Registrando…" : "Confirmar decisão"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Página -----------------------------------------------------------------
export function PainelSupervisor() {
  const [sel, setSel] = useState<OSItem | null>(null);

  const { data: rows, isLoading } = useQuery({
    queryKey: ["os-fila"],
    queryFn: fetchFila,
    refetchInterval: 30000,
  });
  const { data: auditorRows } = useQuery({
    queryKey: ["auditor-fila"],
    queryFn: fetchAuditorFila,
    refetchInterval: 30000,
  });
  const { data: m } = useQuery({
    queryKey: ["supervisor-metrics", 30],
    queryFn: () => fetchMetrics(30),
  });

  const list = rows ?? [];
  const auditorList = auditorRows ?? [];

  return (
    <AppLayout activePage="Supervisor">
      <div className="kan-page">
        <div className="kan-page-head">
          <div>
            <h1 className="kan-h1">Painel do Supervisor</h1>
            <p className="kan-sub">
              4º nível de decisão. A coluna "Com o Auditor" mostra os exames ainda em
              auditoria; homologue ou reforme o parecer do Auditor quando a OS subir.
            </p>
          </div>
        </div>

        {/* Faixa de métricas */}
        <div className="kan-metrics">
          <MetricPill
            icon={<User size={16} />}
            label="Concordância Supervisor × Auditor"
            value={pct(m?.concordancia_sup_auditor_pct)}
          />
          <MetricPill
            icon={<Bot size={16} />}
            label="Concordância Supervisor × IA"
            value={pct(m?.concordancia_sup_ia_pct)}
          />
          <MetricPill
            icon={<Clock size={16} />}
            label="SLA médio"
            value={m?.sla_medio != null ? String(m.sla_medio) : "—"}
          />
        </div>

        {isLoading && <p className="kan-muted">Carregando fila do supervisor…</p>}
        {!isLoading && (
          <Kanban auditorRows={auditorList} osRows={list} onOpen={setSel} />
        )}

        {sel && <OSDrawer os={sel} onClose={() => setSel(null)} />}
      </div>
    </AppLayout>
  );
}

export default PainelSupervisor;
