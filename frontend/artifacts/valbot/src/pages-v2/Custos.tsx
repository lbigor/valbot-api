/* ============================================================================
   ValBot — Custos (cost_usd / cost_tokens · CMV por vídeo com provisão de VM)
   Porte fiel de .design-ref/page-custos.jsx para React + Vite + TS.
   ============================================================================ */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { Shell } from "@/system/Shell";
import { Kpi, Donut, Bars, HBars, fmt } from "@/system/ui";
import { I } from "@/system/icons";

/* ---- Constantes de configuração (parâmetros de CMV — NÃO são dados de negócio) ---- */
/* USD_BRL_FALLBACK: usado só quando o backend não trouxer a provisão de câmbio
   (key `usd_brl` em /api/admin/settings). O valor vivo vem do backend. */
const USD_BRL_FALLBACK = 5.42;
const VM_USD_MES = 1500; // 1x H100 24/7 (PLANILHA_CUSTOS §7 self-host)

interface ModeloCusto {
  nome: string;
  provider: string;
  in_M: number;
  out_M: number;
  video_usd: number;
  tempo_s: number;
  atual?: boolean;
}
// Catálogo de modelos VLM (PLANILHA_CUSTOS.csv §1_Modelo) — custo por vídeo (USD)
const MODELOS_CUSTO: ModeloCusto[] = [
  { nome: "Gemini 2.5 Pro", provider: "Google", in_M: 1.25, out_M: 10.0, video_usd: 0.12, tempo_s: 45, atual: true },
  { nome: "Gemini 3.1 Pro Preview", provider: "Google", in_M: 2.0, out_M: 12.0, video_usd: 0.18, tempo_s: 75 },
  { nome: "GPT-5.5 (low-res)", provider: "OpenAI", in_M: 5.0, out_M: 30.0, video_usd: 0.19, tempo_s: 105 },
  { nome: "Claude Opus 4.7 (low-res)", provider: "Anthropic", in_M: 5.0, out_M: 25.0, video_usd: 0.18, tempo_s: 95 },
  { nome: "Qwen3-VL-235B-A22B", provider: "Alibaba", in_M: 0.2, out_M: 0.88, video_usd: 0.017, tempo_s: 45 },
  { nome: "Nemotron-12B-VL", provider: "NVIDIA", in_M: 0.2, out_M: 0.6, video_usd: 0.017, tempo_s: 35 },
  { nome: "Kimi K2.6", provider: "Moonshot", in_M: 0.74, out_M: 3.49, video_usd: 0.064, tempo_s: 55 },
  { nome: "Ernie 4.5 VL 424B", provider: "Baidu", in_M: 0.42, out_M: 1.25, video_usd: 0.035, tempo_s: 50 },
  { nome: "DeepSeek V3.2 (texto)", provider: "DeepSeek", in_M: 0.25, out_M: 0.38, video_usd: 0.002, tempo_s: 8 },
];

/* ---- Contrato GET /api/dashboard/custos ---- */
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

async function fetchCustos(dias: number): Promise<CustosResponse> {
  const r = await fetch(`/api/dashboard/custos?dias=${dias}`, { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<CustosResponse>;
}

/* ---- Provisão de câmbio (key `usd_brl` em /api/admin/settings) ---- */
interface SettingItem {
  key: string;
  value: string;
  description?: string | null;
  updated_at?: string | null;
  updated_by?: string | null;
}
interface SettingsResponse {
  items: SettingItem[];
}

async function fetchSettings(): Promise<SettingsResponse> {
  const r = await fetch("/api/admin/settings", { credentials: "include" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json() as Promise<SettingsResponse>;
}

async function putUsdBrl(value: string): Promise<void> {
  const r = await fetch("/api/admin/settings/usd_brl", {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (!r.ok) throw new Error((await r.text().catch(() => "")) || "HTTP " + r.status);
}

const EMPTY: CustosResponse = {
  periodo_dias: 0,
  custo_total_usd: 0,
  num_exames_cobrados: 0,
  custo_medio_por_exame_usd: 0,
  tokens_in_total: 0,
  tokens_out_total: 0,
  serie_diaria: [],
  por_unidade: [],
  por_categoria: [],
};

export default function Custos() {
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [dias, setDias] = useState(30);
  const [moeda, setMoeda] = useState("BRL");
  const { data, isLoading } = useQuery({
    queryKey: ["v2-custos", dias],
    queryFn: () => fetchCustos(dias),
  });
  const cu = data ?? EMPTY;

  /* Provisão de câmbio (USD→BRL) — valor vivo do backend, fallback à constante. */
  const { data: settings } = useQuery({
    queryKey: ["v2-admin-settings"],
    queryFn: fetchSettings,
  });
  const usdBrlSetting = settings?.items?.find((s) => s.key === "usd_brl");
  const usdBrlParsed = usdBrlSetting ? Number(usdBrlSetting.value) : NaN;
  const USD_BRL =
    Number.isFinite(usdBrlParsed) && usdBrlParsed > 0 ? usdBrlParsed : USD_BRL_FALLBACK;

  /* edição (admin) */
  const [draft, setDraft] = useState<string>("");
  const [toast, setToast] = useState<string | null>(null);
  const flash = (m: string) => {
    setToast(m);
    clearTimeout((window as any).__custos_t);
    (window as any).__custos_t = setTimeout(() => setToast(null), 1900);
  };
  const mSaveCambio = useMutation({
    mutationFn: (value: string) => putUsdBrl(value),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["v2-admin-settings"] });
      qc.invalidateQueries({ queryKey: ["v2-custos"] });
      setDraft("");
      flash("Provisão de câmbio atualizada");
    },
    onError: (e: Error) => flash("Falha ao salvar: " + e.message),
  });
  const saveCambio = () => {
    const v = draft.trim().replace(",", ".");
    const n = Number(v);
    if (!Number.isFinite(n) || n <= 0) {
      flash("Informe um número maior que zero");
      return;
    }
    mSaveCambio.mutate(v);
  };

  const conv = (usd: number) => (moeda === "BRL" ? usd * USD_BRL : usd);
  const money = (usd: number, dec?: number) =>
    moeda === "BRL" ? fmt.brl(conv(usd)) : dec === 4 ? fmt.usd4(usd) : fmt.usd(usd);

  const num = cu.num_exames_cobrados;
  const iaUsd = cu.custo_total_usd;
  const vmUsd = VM_USD_MES * (dias / 30); // provisão da VM no período
  const cmvUsd = iaUsd + vmUsd; // CMV total
  const den = num || 1; // evita divisão por zero quando não há vídeos no período
  const cmvVideoUsd = cmvUsd / den; // CMV por vídeo
  const iaVideoUsd = iaUsd / den;
  const vmVideoUsd = vmUsd / den;

  // custo de tokens (Gemini 2.5 Pro — modelo atual)
  const mAtual = MODELOS_CUSTO[0];
  const custoIn = (cu.tokens_in_total / 1e6) * mAtual.in_M;
  const custoOut = (cu.tokens_out_total / 1e6) * mAtual.out_M;

  const serieBars = cu.serie_diaria.slice(-14).map((d) => ({
    label: String(new Date(d.dia + "T12:00").getDate()),
    value: +(d.custo_usd * (moeda === "BRL" ? USD_BRL : 1)).toFixed(2),
  }));
  const porUnidade = cu.por_unidade.slice(0, 6).map((u) => ({ label: u.rotulo, value: u.custo_usd }));

  const actions = (
    <>
      <div className="seg">
        {["BRL", "USD"].map((c) => (
          <button key={c} className={moeda === c ? "on" : ""} onClick={() => setMoeda(c)}>
            {c}
          </button>
        ))}
      </div>
      <div className="seg">
        {[7, 30, 90].map((d) => (
          <button key={d} className={dias === d ? "on" : ""} onClick={() => setDias(d)}>
            {d}d
          </button>
        ))}
      </div>
      <button className="btn btn-sm">
        <I.download w={15} />
        CSV
      </button>
    </>
  );

  return (
    <Shell
      active="custos"
      title="Custos"
      sub={`Custo de IA por vídeo e CMV · últimos ${dias} dias${isLoading ? " · carregando…" : ""}`}
      actions={actions}
    >
      {/* KPIs principais */}
      <div className="grid g-4">
        <Kpi
          icon={I.video}
          label="Vídeos processados"
          value={fmt.int(num)}
          foot={<span>no período</span>}
          iconColor="var(--proc)"
          iconBg="var(--proc-bg)"
        />
        <Kpi
          icon={I.bolt}
          label="Custo de IA (tokens)"
          value={money(iaUsd)}
          delta="8,2%"
          deltaDir="down"
          foot={<span>{money(iaVideoUsd, 4)}/vídeo</span>}
          iconColor="var(--brand)"
          iconBg="var(--brand-tint)"
        />
        <Kpi
          icon={I.cpu}
          label="Provisão da VM"
          value={money(vmUsd)}
          foot={
            <span>
              1× H100 24/7 · {money(vmVideoUsd, 4)}/vídeo
            </span>
          }
          iconColor="var(--warn)"
          iconBg="var(--warn-bg)"
        />
        <Kpi
          icon={I.custos}
          label="CMV por vídeo"
          value={money(cmvVideoUsd, 4)}
          foot={<span>IA + infra rateada</span>}
          iconColor="var(--ok)"
          iconBg="var(--ok-bg)"
        />
      </div>

      {/* Provisão de câmbio (USD→BRL) — leitura p/ todos, edição p/ admin */}
      <div className="panel" style={{ marginTop: 16 }}>
        <div className="panel-h">
          <h2>Provisão de câmbio (USD → BRL)</h2>
          <span className="ph-sub">cotação usada para converter os custos em reais</span>
        </div>
        <div
          className="panel-b"
          style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}
        >
          <div>
            <div className="mono" style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-.02em" }}>
              R$ {USD_BRL.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
            </div>
            <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>
              por US$ 1,00
              {!usdBrlSetting && " · valor padrão (backend não retornou)"}
            </div>
          </div>
          <div style={{ fontSize: 12, color: "var(--faint)", lineHeight: 1.5 }}>
            {usdBrlSetting?.updated_at && (
              <div>
                Atualizado {fmt.dmyhm(usdBrlSetting.updated_at)}
              </div>
            )}
            {usdBrlSetting?.updated_by && <div>por {usdBrlSetting.updated_by}</div>}
            {usdBrlSetting?.description && (
              <div style={{ color: "var(--muted)" }}>{usdBrlSetting.description}</div>
            )}
          </div>
          <span className="spacer" />
          {isAdmin ? (
            <div className="fld" style={{ flexDirection: "row", alignItems: "flex-end", gap: 8 }}>
              <input
                type="number"
                step="0.01"
                min="0"
                style={{ width: 120 }}
                placeholder={USD_BRL.toFixed(2)}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveCambio();
                }}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={saveCambio}
                disabled={mSaveCambio.isPending}
              >
                {mSaveCambio.isPending ? "Salvando…" : "Salvar"}
              </button>
            </div>
          ) : (
            <span className="badge neutral">
              <span className="bd" />somente leitura
            </span>
          )}
        </div>
      </div>

      {/* composição do CMV */}
      <div className="grid g-2" style={{ marginTop: 16, gridTemplateColumns: "1fr 1.1fr" }}>
        <div className="panel">
          <div className="panel-h">
            <h2>Composição do CMV por vídeo</h2>
          </div>
          <div className="panel-b">
            <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
              <Donut
                size={140}
                thickness={18}
                segments={[
                  { label: "IA (tokens)", value: iaVideoUsd, color: "var(--brand)" },
                  { label: "VM (infra)", value: vmVideoUsd, color: "var(--warn)" },
                ]}
                center={
                  <div>
                    <div style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.02em" }}>
                      {money(cmvVideoUsd, 4)}
                    </div>
                    <div style={{ fontSize: 10.5, color: "var(--muted)" }}>/ vídeo</div>
                  </div>
                }
              />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 14 }}>
                <CmvRow
                  color="var(--brand)"
                  label="Custo de IA (tokens)"
                  value={money(iaVideoUsd, 4)}
                  pct={iaVideoUsd / cmvVideoUsd}
                />
                <CmvRow
                  color="var(--warn)"
                  label="Provisão de infraestrutura (VM)"
                  value={money(vmVideoUsd, 4)}
                  pct={vmVideoUsd / cmvVideoUsd}
                />
                <div
                  style={{
                    borderTop: "1px solid var(--border)",
                    paddingTop: 12,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "baseline",
                  }}
                >
                  <span style={{ fontSize: 13, fontWeight: 700 }}>CMV unitário</span>
                  <span className="mono" style={{ fontSize: 18, fontWeight: 800 }}>
                    {money(cmvVideoUsd, 4)}
                  </span>
                </div>
              </div>
            </div>
            <div
              style={{
                marginTop: 16,
                padding: "12px 14px",
                background: "var(--surface-2)",
                borderRadius: "var(--r)",
                fontSize: 12.5,
                color: "var(--muted)",
                lineHeight: 1.5,
              }}
            >
              <b style={{ color: "var(--ink-2)" }}>CMV</b> = (custo de tokens do período + provisão
              mensal da VM) ÷ vídeos processados. No período: {money(iaUsd)} (IA) + {money(vmUsd)}{" "}
              (VM) = <b style={{ color: "var(--ink-2)" }}>{money(cmvUsd)}</b> ÷ {fmt.int(num)} vídeos.
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-h">
            <h2>Consumo de tokens</h2>
            <span className="ph-sub">modelo {mAtual.nome}</span>
          </div>
          <div className="panel-b">
            <div className="grid g-2" style={{ gap: 12 }}>
              <TokenCard
                label="Tokens de entrada"
                tokens={cu.tokens_in_total}
                custo={money(custoIn)}
                sub={`$ ${mAtual.in_M.toFixed(2)} / M tokens`}
                color="var(--proc)"
              />
              <TokenCard
                label="Tokens de saída"
                tokens={cu.tokens_out_total}
                custo={money(custoOut)}
                sub={`$ ${mAtual.out_M.toFixed(2)} / M tokens`}
                color="var(--brand)"
              />
            </div>
            <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 9 }}>
              <MiniLine
                label="Média de tokens por vídeo (entrada)"
                value={fmt.tokens(cu.tokens_in_total / den)}
              />
              <MiniLine
                label="Média de tokens por vídeo (saída)"
                value={fmt.tokens(cu.tokens_out_total / den)}
              />
              <MiniLine label="Tempo médio de análise" value="~52 s" />
            </div>
          </div>
        </div>
      </div>

      {/* série diária */}
      <div className="panel" style={{ marginTop: 16 }}>
        <div className="panel-h">
          <h2>Custo diário de IA</h2>
          <span className="ph-sub">últimos 14 dias · {moeda}</span>
          <span className="spacer" />
          <span className="badge neutral">
            <span className="bd" />total {money(iaUsd)}
          </span>
        </div>
        <div className="panel-b">
          <Bars data={serieBars} h={150} color="var(--brand-500)" />
        </div>
      </div>

      {/* modelos + recortes */}
      <div className="grid g-2" style={{ marginTop: 16, gridTemplateColumns: "1.5fr 1fr" }}>
        <div className="panel">
          <div className="panel-h">
            <h2>Custo por modelo VLM</h2>
            <span className="ph-sub">benchmark · 1 vídeo (77k in / 2k out)</span>
          </div>
          <div className="tbl-wrap" style={{ border: "none", borderRadius: 0, boxShadow: "none" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Modelo</th>
                  <th>Provedor</th>
                  <th>Custo/vídeo (USD)</th>
                  <th>Custo/vídeo ({moeda})</th>
                  <th>Tempo</th>
                </tr>
              </thead>
              <tbody>
                {MODELOS_CUSTO.map((md, i) => (
                  <tr key={i} style={md.atual ? { background: "var(--brand-tint)" } : undefined}>
                    <td className="t-strong">
                      {md.nome}{" "}
                      {md.atual && (
                        <span className="badge proc" style={{ marginLeft: 6 }}>
                          <span className="bd" />em uso
                        </span>
                      )}
                    </td>
                    <td className="muted">{md.provider}</td>
                    <td className="num">{fmt.usd4(md.video_usd)}</td>
                    <td className="num t-strong">
                      {moeda === "BRL" ? fmt.brl(md.video_usd * USD_BRL) : fmt.usd4(md.video_usd)}
                    </td>
                    <td className="num muted">{md.tempo_s}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel">
          <div className="panel-h">
            <h2>Custo por unidade</h2>
          </div>
          <div className="panel-b">
            <HBars items={porUnidade} fmt={(v) => money(v)} color="var(--warn)" />
          </div>
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </Shell>
  );
}

interface CmvRowProps {
  color: string;
  label: string;
  value: string;
  pct: number;
}
function CmvRow({ color, label, value, pct }: CmvRowProps) {
  return (
    <div>
      <div
        style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 5 }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--ink-2)" }}>
          <span style={{ width: 9, height: 9, borderRadius: 3, background: color }} />
          {label}
        </span>
        <span className="mono" style={{ fontWeight: 700 }}>
          {value}
        </span>
      </div>
      <div className="bar">
        <i style={{ width: `${(pct * 100).toFixed(0)}%`, background: color }} />
      </div>
    </div>
  );
}

interface TokenCardProps {
  label: string;
  tokens: number;
  custo: string;
  sub: string;
  color: string;
}
function TokenCard({ label, tokens, custo, sub, color }: TokenCardProps) {
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--r)", padding: "13px 14px" }}>
      <div style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>{label}</div>
      <div className="mono" style={{ fontSize: 22, fontWeight: 800, color, margin: "4px 0 1px" }}>
        {fmt.tokens(tokens)}
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11.5,
          color: "var(--faint)",
        }}
      >
        <span>{sub}</span>
        <span className="mono t-strong" style={{ color: "var(--ink-2)" }}>
          {custo}
        </span>
      </div>
    </div>
  );
}

interface MiniLineProps {
  label: string;
  value: string;
}
function MiniLine({ label, value }: MiniLineProps) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        fontSize: 12.5,
        paddingBottom: 9,
        borderBottom: "1px solid var(--border)",
      }}
    >
      <span className="muted">{label}</span>
      <span className="mono t-strong">{value}</span>
    </div>
  );
}
