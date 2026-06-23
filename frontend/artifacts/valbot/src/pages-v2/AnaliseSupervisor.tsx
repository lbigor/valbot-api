/* ============================================================================
   ValBot — Análise do Supervisor (réplica imersiva da Fila do Auditor)
   O supervisor revê o exame, informa QUAL resultado está correto e finaliza a OS.
   Porte fiel de .design-ref/page-analise-supervisor.jsx

   DADOS REAIS (sem mock):
     GET  /api/os                              → OS por os_id (queryKey v2-os)
     GET  /api/exams/{hash}/laudo-json         → laudo §14.2 (queryKey v2-laudo)
     GET  /api/exams/{hash}/video              → <video src>
     POST /api/os/{os_id}/decisao  {decisao, justificativa}
   hash = os_id (prop `os`).
   ============================================================================ */
import { useState, useEffect, useMemo, useRef } from "react";
import { Link, useLocation } from "wouter";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { I } from "@/system/icons";
import { fmt } from "@/system/ui";
import "@/system/vb.css";

/* ---------------- consts locais (eram VB.*) ---------------- */
const COD_LABEL: Record<string, string> = { A: "Apto", R: "Reprovado", N: "Sem avaliação" };
const COD_CLS: Record<string, string> = { A: "ok", R: "bad", N: "neutral" };

const TIPO_DIV_LABEL: Record<string, string> = {
  resultado: "resultado",
  pontuacao: "pontuação",
  infracao: "infração",
  sem_divergencia: "sem divergência",
};

interface GravMeta {
  label: string;
  pontos: number;
  color: string;
  bg: string;
}
const META_GRAV: Record<string, GravMeta> = {
  gravissima: { label: "Gravíssima", pontos: 6, color: "#BE123C", bg: "#FCEAEF" },
  grave: { label: "Grave", pontos: 4, color: "#B45309", bg: "#FBF1E3" },
  media: { label: "Média", pontos: 2, color: "#1D4ED8", bg: "#E7EEFD" },
  leve: { label: "Leve", pontos: 1, color: "#6B7689", bg: "#F1F4F9" },
};

/* ---------------- contratos ---------------- */
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
  pontuacao_oficial?: number | null;
  pontuacao_calculada?: number | null;
  auditor_email?: string | null;
  aberta_em?: string | null;
  sla_due_at?: string | null;
  conf?: number | null;
}

interface LaudoJson {
  exame_hash?: string;
  blocos?: Record<string, unknown>;
  [k: string]: unknown;
}

interface InfracaoView {
  descricao: string;
  base_legal: string;
  gravidade: string;
  pontos: number;
  timestamp_s: number;
  confianca: number;
}

/* ---------------- helpers ---------------- */
function prioridadeDe(tipo?: string): number {
  const t = (tipo ?? "").toLowerCase();
  if (t.includes("result")) return 1;
  if (t.includes("pont")) return 2;
  return 3;
}
function slaDe(due?: string | null): { horas: number; estourado: boolean } {
  if (!due) return { horas: 0, estourado: false };
  const ms = new Date(due).getTime() - Date.now();
  if (Number.isNaN(ms)) return { horas: 0, estourado: false };
  return { horas: Math.abs(ms) / 3.6e6, estourado: ms < 0 };
}
function asStr(v: unknown): string | null {
  if (v == null || v === "") return null;
  return String(v);
}
function asNum(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return isNaN(n) ? null : n;
}

/* ---------------- fetchers ---------------- */
async function fetchFila(): Promise<OSItem[]> {
  const r = await fetch("/api/os", { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const j = await r.json();
  return Array.isArray(j) ? j : (j?.items ?? []);
}
async function fetchLaudo(hash: string): Promise<LaudoJson> {
  const r = await fetch(`/api/exams/${encodeURIComponent(hash)}/laudo-json`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<LaudoJson>;
}
async function postDecisao(osId: string | number, decisao: string, justificativa: string) {
  const r = await fetch(`/api/os/${encodeURIComponent(String(osId))}/decisao`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decisao, justificativa }),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json().catch(() => ({}));
}

interface AnaliseSupervisorProps {
  os?: string;
}

export default function AnaliseSupervisor({ os: osParam }: AnaliseSupervisorProps = {}) {
  const [, navigate] = useLocation();
  const qc = useQueryClient();

  const { data: fila = [] } = useQuery({
    queryKey: ["v2-os"],
    queryFn: fetchFila,
  });

  const os = useMemo<OSItem | undefined>(
    () => fila.find((o) => String(o.os_id) === String(osParam)) ?? fila[0],
    [osParam, fila]
  );

  // hash = os_id (prop `os`). Cai pra exam_hash da OS se vier diferente.
  const hash = String(osParam ?? os?.exam_hash ?? os?.os_id ?? "");

  const { data: laudo } = useQuery({
    queryKey: ["v2-laudo", hash],
    queryFn: () => fetchLaudo(hash),
    enabled: !!hash,
    retry: false,
  });

  // infrações reais do bloco §14.2 "7_analise_detalhada"
  const infr = useMemo<InfracaoView[]>(() => {
    const analise = laudo?.blocos?.["7_analise_detalhada"];
    let arr: Record<string, unknown>[] = [];
    if (Array.isArray(analise)) arr = analise as Record<string, unknown>[];
    else if (analise && typeof analise === "object") {
      const inf = (analise as Record<string, unknown>).infracoes;
      if (Array.isArray(inf)) arr = inf as Record<string, unknown>[];
    }
    return arr.map((i) => {
      const grav = (asStr(i.gravidade) ?? asStr(i.natureza) ?? "leve").toLowerCase();
      const m = META_GRAV[grav] ?? META_GRAV.leve;
      return {
        descricao: asStr(i.descricao) ?? asStr(i.nome) ?? "Infração",
        base_legal: asStr(i.artigo_ctb) ?? asStr(i.base_legal) ?? asStr(i.regra_aplicada) ?? "—",
        gravidade: META_GRAV[grav] ? grav : "leve",
        pontos: asNum(i.peso) ?? asNum(i.pontos) ?? m.pontos,
        timestamp_s: asNum(i.timestamp_s) ?? asNum(i.timestamp) ?? 0,
        confianca: asNum(i.confianca) ?? 0,
      };
    });
  }, [laudo]);

  // duração: maior timestamp de infração + folga, ou fallback fixo
  const dur = useMemo(() => {
    const maxTs = infr.reduce((mx, i) => Math.max(mx, i.timestamp_s), 0);
    return maxTs > 0 ? Math.ceil(maxTs * 1.15) : 600;
  }, [infr]);

  const videoUrl = hash ? `/api/exams/${encodeURIComponent(hash)}/video` : "";

  const [pos, setPos] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [escolha, setEscolha] = useState<"oficial" | "val" | null>(null);
  const [just, setJust] = useState("");
  const [done, setDone] = useState(false);
  const tlRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // play/pause espelha no <video> real
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    if (playing) v.play().catch(() => {});
    else v.pause();
  }, [playing]);

  // sincroniza pos com o tempo real do vídeo
  const onTimeUpdate = () => {
    const v = videoRef.current;
    if (v && !Number.isNaN(v.currentTime)) setPos(v.currentTime);
  };

  const seekTo = (s: number) => {
    const clamped = Math.max(0, Math.min(dur, s));
    setPos(clamped);
    if (videoRef.current) videoRef.current.currentTime = clamped;
  };

  const seekFromEvent = (ev: React.MouseEvent<HTMLDivElement>) => {
    if (!tlRef.current) return;
    const r = tlRef.current.getBoundingClientRect();
    seekTo(Math.round(((ev.clientX - r.left) / r.width) * dur));
  };

  const decisao = useMutation({
    mutationFn: ({ d, j }: { d: string; j: string }) => postDecisao(os!.os_id, d, j),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["v2-os"] });
      qc.invalidateQueries({ queryKey: ["v2-sup-metrics"] });
      setDone(true);
    },
  });

  const finalizar = () => {
    if (!escolha || !os) return;
    // escolha "oficial" homologa o veredito presencial; "val" reforma para o cálculo da IA.
    decisao.mutate({ d: escolha === "oficial" ? "homologar" : "reformar", j: just.trim() });
  };

  // estado de carregamento / OS inexistente — discreto, preserva layout do erro
  if (!os) {
    return (
      <div className="asup" style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center", maxWidth: 420, padding: 40 }}>
          <p style={{ color: "var(--muted)", fontSize: 14 }}>Carregando ordem de serviço…</p>
          <Link href="/supervisor" className="btn btn-primary" style={{ marginTop: 16 }}>
            <I.fila w={16} />
            Voltar à fila de arbitragem
          </Link>
        </div>
      </div>
    );
  }

  const prio = prioridadeDe(os.tipo_divergencia);
  const sla = slaDe(os.sla_due_at);
  const tipoLabel = os.tipo_label ?? (os.tipo_divergencia && TIPO_DIV_LABEL[os.tipo_divergencia]) ?? os.tipo_divergencia ?? "resultado";

  if (done) {
    const corretoCod = escolha === "oficial" ? os.resultado_oficial : os.resultado_calculado;
    return (
      <div className="asup" style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center", maxWidth: 420, padding: 40 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: "50%",
              background: "var(--ok-bg)",
              color: "var(--ok)",
              display: "grid",
              placeItems: "center",
              margin: "0 auto 18px",
            }}
          >
            <I.check w={32} />
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em", margin: "0 0 8px" }}>
            Análise finalizada
          </h2>
          <p style={{ color: "var(--muted)", fontSize: 14, lineHeight: 1.6, margin: "0 0 22px" }}>
            {os.numero_os ?? os.os_id} encerrada. Resultado homologado:{" "}
            <b style={{ color: "var(--ink)" }}>{COD_LABEL[corretoCod || ""] || "—"}</b> (
            {escolha === "oficial" ? "veredito oficial" : "cálculo do Val"}).
          </p>
          <Link href="/supervisor" className="btn btn-primary">
            <I.fila w={16} />
            Voltar à fila de arbitragem
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="asup">
      <div className="asup-top">
        <a
          href="/supervisor"
          className="asup-back"
          onClick={(e) => {
            e.preventDefault();
            navigate("/supervisor");
          }}
        >
          <I.right w={15} style={{ transform: "rotate(180deg)" }} />
          Fila
        </a>
        <div>
          <div className="asup-title">Análise do Supervisor</div>
          <div className="asup-id">
            {os.numero_os ?? os.os_id} · {os.renach ?? "—"} · {os.candidato_nome ?? "—"}
          </div>
        </div>
        <span className="spacer" />
        <span className={"badge " + (prio === 1 ? "bad" : prio === 2 ? "warn" : "proc")}>
          <span className="bd" />
          Divergência de {tipoLabel}
        </span>
        <span className={"badge " + (sla.estourado ? "bad" : "neutral")}>
          <I.clock w={13} />
          {sla.horas < 24 ? sla.horas.toFixed(0) + "h" : (sla.horas / 24).toFixed(1) + "d"}
        </span>
      </div>

      <div className="asup-body">
        {/* vídeo + timeline */}
        <div>
          <div className="vplayer">
            <div className="vquad">
              {videoUrl ? (
                <video
                  ref={videoRef}
                  src={videoUrl}
                  onTimeUpdate={onTimeUpdate}
                  onPlay={() => setPlaying(true)}
                  onPause={() => setPlaying(false)}
                  onEnded={() => setPlaying(false)}
                  style={{
                    gridColumn: "1 / -1",
                    gridRow: "1 / -1",
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    background: "#0a0f1f",
                  }}
                  playsInline
                />
              ) : (
                ["Frontal", "Lateral dir.", "Interna", "Traseira esq."].map((c) => (
                  <div key={c} className="vcam">
                    <span>{c}</span>
                  </div>
                ))
              )}
              <div className="vplay">
                <button onClick={() => setPlaying((p) => !p)}>
                  {playing ? (
                    <span style={{ fontSize: 22, fontWeight: 800 }}>❚❚</span>
                  ) : (
                    <I.play w={26} />
                  )}
                </button>
              </div>
            </div>
            <div className="vbar">
              <button
                className="icon-btn"
                style={{
                  width: 34,
                  height: 34,
                  background: "transparent",
                  borderColor: "#2a3550",
                  color: "#cbd5e1",
                }}
                onClick={() => setPlaying((p) => !p)}
              >
                {playing ? "❚❚" : <I.play w={15} />}
              </button>
              <span className="vt">{fmt.dur(pos)}</span>
              <div className="vtl" ref={tlRef} onClick={seekFromEvent}>
                <div className="vtl-track" />
                <div className="vtl-fill" style={{ width: (pos / dur) * 100 + "%" }} />
                {infr.map((i, k) => (
                  <div
                    key={k}
                    className="vtl-mk"
                    style={{ left: (i.timestamp_s / dur) * 100 + "%", background: META_GRAV[i.gravidade].color }}
                    title={i.descricao + " · " + fmt.dur(i.timestamp_s)}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      seekTo(i.timestamp_s);
                    }}
                  />
                ))}
                <div className="vtl-head" style={{ left: (pos / dur) * 100 + "%" }} />
              </div>
              <span className="vt">{fmt.dur(dur)}</span>
            </div>
          </div>

          {/* infrações detectadas */}
          <div className="dpanel" style={{ marginTop: 16 }}>
            <div className="panel-h">
              <h2>Infrações detectadas pelo Val</h2>
              <span className="spacer badge neutral">{infr.length}</span>
            </div>
            <div className="panel-b" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {infr.length ? (
                infr.map((i, k) => {
                  const m = META_GRAV[i.gravidade];
                  return (
                    <button
                      key={k}
                      onClick={() => seekTo(i.timestamp_s)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 11,
                        padding: "10px 12px",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--r)",
                        background: "var(--surface)",
                        textAlign: "left",
                        cursor: "pointer",
                      }}
                    >
                      <span
                        style={{
                          display: "inline-grid",
                          placeItems: "center",
                          width: 30,
                          height: 30,
                          borderRadius: 8,
                          fontFamily: "var(--mono)",
                          fontWeight: 700,
                          fontSize: 13,
                          color: m.color,
                          background: m.bg,
                        }}
                      >
                        {i.pontos}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="t-strong" style={{ fontSize: 13 }}>
                          {i.descricao}
                        </div>
                        <div className="mono t-sub">
                          {i.base_legal} · conf. {(i.confianca * 100).toFixed(0)}%
                        </div>
                      </div>
                      <span className="mono t-sub">{fmt.dur(i.timestamp_s)}</span>
                    </button>
                  );
                })
              ) : (
                <div className="t-sub">Nenhuma infração detectada.</div>
              )}
            </div>
          </div>
        </div>

        {/* painel de decisão */}
        <div>
          <div className="dpanel">
            <div className="panel-h">
              <h2>Qual resultado está correto?</h2>
            </div>
            <div className="panel-b" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <DecisaoCard
                tag="Veredito oficial"
                sub="Comissão presencial"
                cod={os.resultado_oficial ?? null}
                pts={os.pontuacao_oficial ?? null}
                on={escolha === "oficial"}
                onClick={() => setEscolha("oficial")}
              />
              <DecisaoCard
                tag="Calculado pelo Val"
                sub={`IA · ${asStr(os.examinador) ? "exam " + os.examinador : "ValBot"}`}
                cod={os.resultado_calculado ?? null}
                pts={os.pontuacao_calculada ?? null}
                on={escolha === "val"}
                onClick={() => setEscolha("val")}
              />
            </div>
          </div>

          <div className="dpanel">
            <div className="panel-b" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div className="fld">
                <label className="fld-l">Justificativa (opcional)</label>
                <textarea
                  rows={3}
                  value={just}
                  onChange={(e) => setJust(e.target.value)}
                  placeholder="Fundamente a decisão final, citando a ficha MBEDV se aplicável…"
                />
              </div>
              <button
                className="btn btn-primary"
                style={{ width: "100%", height: 44, justifyContent: "center", opacity: escolha && !decisao.isPending ? 1 : 0.5 }}
                disabled={!escolha || decisao.isPending}
                onClick={finalizar}
              >
                <I.check w={17} />
                {decisao.isPending ? "Finalizando…" : "Finalizar análise"}
              </button>
              {decisao.isError && (
                <div className="t-sub" style={{ textAlign: "center", color: "var(--bad)" }}>
                  Falha ao registrar a decisão. Tente novamente.
                </div>
              )}
              {!escolha && !decisao.isError && (
                <div className="t-sub" style={{ textAlign: "center" }}>
                  Selecione qual resultado está correto para finalizar.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface DecisaoCardProps {
  tag: string;
  sub: string;
  cod: string | null;
  pts: number | null;
  on: boolean;
  onClick: () => void;
}

function DecisaoCard({ tag, sub, cod, pts, on, onClick }: DecisaoCardProps) {
  const cls = COD_CLS[cod || ""] || "neutral";
  return (
    <div className={"choice" + (on ? " on" : "")} onClick={onClick}>
      <div className="ch-top">
        <span className="ch-rd" />
        <span
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: ".05em",
            fontWeight: 700,
            color: "var(--faint)",
          }}
        >
          {tag}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, paddingLeft: 26 }}>
        <span className={"badge " + cls} style={{ fontSize: 13 }}>
          <span className="bd" />
          {COD_LABEL[cod || ""] || "—"}
        </span>
        <span className="mono t-sub">{pts != null ? pts + " pts" : "—"}</span>
      </div>
      <div className="t-sub" style={{ paddingLeft: 26 }}>
        {sub}
      </div>
    </div>
  );
}
