import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppLayout } from "../components/AppLayout";
import { useAuth } from "@/contexts/AuthContext";
import {
  Search,
  ShieldAlert,
  History,
  Sliders,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Camera as CameraIcon,
  Scale,
  Target,
  Plus,
  Trash2,
  Save,
  Sparkles,
  BookOpen,
  Lock,
} from "lucide-react";
import { CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { GlassCard } from "@/components/ui/glass-card";
import { cn } from "@/lib/utils";
import type {
  Gravidade,
  RubricaFull,
  RubricaInfracao,
  RubricaSlug,
} from "@/types/laudo";

type Severidade = "Crítico" | "Alto" | "Médio" | "Baixo";

const RUBRICA_OPTIONS: { slug: RubricaSlug; label: string }[] = [
  { slug: "1020/2025", label: "Res. CONTRAN 1.020/2025" },
  { slug: "789/2020", label: "Res. CONTRAN 789/2020" },
];

// ──────────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────────

function severidadeFromGravidade(g: Gravidade): Severidade {
  if (g === "eliminatoria" || g === "gravissima") return "Crítico";
  if (g === "grave") return "Alto";
  if (g === "media") return "Médio";
  return "Baixo";
}

const SEV_TONE: Record<Severidade, { text: string; bg: string; border: string; dot: string }> = {
  Crítico: {
    text: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/40",
    dot: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.7)]",
  },
  Alto: {
    text: "text-orange-400",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    dot: "bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)]",
  },
  Médio: {
    text: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    dot: "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]",
  },
  Baixo: {
    text: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    dot: "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]",
  },
};

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max - 1) + "…";
}

function formatCameras(cameras?: string[]): string {
  if (!cameras || cameras.length === 0) return "—";
  const map: Record<string, string> = {
    interna: "Interna",
    retrovisor_esquerdo: "Retrov. Esq.",
    retrovisor_direito: "Retrov. Dir.",
    traseira: "Traseira",
  };
  return cameras.map((c) => map[c] ?? c).join(" + ");
}

/**
 * Heuristic de bounds para o slider — sem schema explícito, infere range a partir do nome e valor.
 */
function sliderBounds(key: string, value: number): { min: number; max: number; step: number } {
  const k = key.toLowerCase();
  if (k.includes("confidence") || k.includes("threshold") || k.endsWith("_pct") && value <= 1) {
    return { min: 0, max: 1, step: 0.01 };
  }
  if (k.endsWith("_pct") || k.includes("percent")) {
    return { min: 0, max: 100, step: 1 };
  }
  if (k.endsWith("_s") || k.includes("duracao") || k.includes("tempo")) {
    return { min: 0, max: Math.max(60, value * 3), step: 0.5 };
  }
  if (k.includes("km_h") || k.includes("velocidade")) {
    return { min: 0, max: 120, step: 1 };
  }
  // default heuristic baseado no valor
  if (value <= 1) return { min: 0, max: 1, step: 0.01 };
  if (value <= 60) return { min: 0, max: 60, step: 0.5 };
  return { min: 0, max: value * 3, step: 1 };
}

// ──────────────────────────────────────────────────────────────────────────
// Page
// ──────────────────────────────────────────────────────────────────────────

export function Regras() {
  const [slug, setSlug] = useState<RubricaSlug>("1020/2025");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const encodedSlug = encodeURIComponent(slug);
  const { data, isLoading, error } = useQuery<RubricaFull>({
    queryKey: ["rubrica", slug],
    queryFn: async () => {
      const r = await fetch(`/api/rubricas/${encodedSlug}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return (await r.json()) as RubricaFull;
    },
  });

  const infracoes: RubricaInfracao[] = data?.infracoes ?? [];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return infracoes;
    return infracoes.filter(
      (i) => i.id.toLowerCase().includes(q) || i.descricao.toLowerCase().includes(q),
    );
  }, [infracoes, query]);

  const effectiveSelected = useMemo(() => {
    if (filtered.length === 0) return undefined;
    return filtered.find((i) => i.id === selectedId) ?? filtered[0];
  }, [filtered, selectedId]);

  const sev = effectiveSelected
    ? severidadeFromGravidade(effectiveSelected.gravidade)
    : null;

  const versaoLabel = slug;
  const baseLegalFallback = `CONTRAN Res. ${versaoLabel}`;

  return (
    <AppLayout activePage="Regras">
      <div className="relative h-full">
        {/* Ambient glow */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-32 -left-20 w-[480px] h-[480px] rounded-full bg-cyan-500/[0.04] blur-3xl" />
          <div className="absolute top-1/3 -right-20 w-[420px] h-[420px] rounded-full bg-blue-700/[0.05] blur-3xl" />
          <div className="absolute bottom-0 left-1/3 w-[380px] h-[380px] rounded-full bg-violet-500/[0.035] blur-3xl" />
        </div>

        <div className="relative flex flex-col h-full gap-5">
          {/* Header */}
          <div className="flex items-end justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.18em] text-cyan-400/80 font-medium">
                Manual normativo · CONTRAN
              </p>
              <h1 className="text-2xl font-semibold text-slate-50 mt-1">
                Rubrica de infrações & parâmetros
              </h1>
            </div>
            {data && (
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <BookOpen size={14} className="text-cyan-400" />
                {data.total_infracoes} infrações · limite{" "}
                <span className="text-slate-200 font-semibold">
                  {data.limite_pontuacao} pts
                </span>
              </div>
            )}
          </div>

          {/* Main split */}
          <div className="flex gap-5 flex-1 min-h-0">
            {/* ─────────── LEFT: list + filters ─────────── */}
            <GlassCard className="w-[58%] flex flex-col overflow-hidden flex-shrink-0" glow="cyan">
              <CardContent className="p-4 pb-3 border-b border-slate-800/60 space-y-3">
                <div className="flex justify-between items-center gap-3 flex-wrap">
                  <div className="relative flex-1 min-w-[200px]">
                    <Search
                      size={13}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 z-10"
                    />
                    <Input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Buscar por código ou descrição…"
                      className="h-9 pl-8 bg-slate-900/60 border-slate-700/60 text-sm text-slate-200 placeholder:text-slate-500 focus-visible:ring-cyan-500/50 focus-visible:border-cyan-500/50"
                    />
                  </div>
                  <Select
                    value={slug}
                    onValueChange={(v) => {
                      setSlug(v as RubricaSlug);
                      setSelectedId(null);
                    }}
                  >
                    <SelectTrigger className="h-9 w-[230px] bg-slate-900/60 border-slate-700/60 text-sm text-slate-200 focus:ring-cyan-500/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-900 border-slate-700 text-slate-200">
                      {RUBRICA_OPTIONS.map((opt) => (
                        <SelectItem key={opt.slug} value={opt.slug}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {data && (
                  <div className="flex items-center gap-3 text-[11px] text-slate-500 flex-wrap">
                    {Object.entries(data.contagem_por_gravidade)
                      .filter(([, n]) => n > 0)
                      .map(([g, n]) => {
                        const s = severidadeFromGravidade(g as Gravidade);
                        const tone = SEV_TONE[s];
                        return (
                          <span key={g} className="flex items-center gap-1">
                            <span className={cn("w-1.5 h-1.5 rounded-full", tone.dot)} />
                            <span className="capitalize text-slate-400">{g}:</span>
                            <span className="font-semibold text-slate-200 tabular-nums">{n}</span>
                          </span>
                        );
                      })}
                    {query && (
                      <span className="ml-auto text-slate-500">
                        Filtradas:{" "}
                        <span className="font-semibold text-slate-200">{filtered.length}</span>
                      </span>
                    )}
                  </div>
                )}
              </CardContent>

              {/* List */}
              <div className="flex-1 overflow-auto custom-scrollbar">
                {isLoading && (
                  <div className="flex items-center justify-center p-8 text-slate-400 text-sm gap-2">
                    <Loader2 size={16} className="animate-spin" /> Carregando rubrica…
                  </div>
                )}
                {error && (
                  <div className="flex items-center justify-center p-8 text-red-400 text-sm gap-2">
                    <AlertCircle size={16} /> Falha ao carregar rubrica.
                  </div>
                )}
                {!isLoading && !error && (
                  <table className="w-full text-sm text-left">
                    <thead className="text-[10px] uppercase tracking-wider text-slate-500 bg-slate-900/40 sticky top-0 backdrop-blur-md">
                      <tr>
                        <th className="px-4 py-2.5 font-medium">Código</th>
                        <th className="px-4 py-2.5 font-medium">Descrição</th>
                        <th className="px-4 py-2.5 font-medium">Severidade</th>
                        <th className="px-4 py-2.5 font-medium text-right">Pontos</th>
                        <th className="px-4 py-2.5 font-medium text-center">Ativo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((row) => {
                        const isActive = effectiveSelected?.id === row.id;
                        const s = severidadeFromGravidade(row.gravidade);
                        const tone = SEV_TONE[s];
                        return (
                          <tr
                            key={row.id}
                            onClick={() => setSelectedId(row.id)}
                            className={cn(
                              "cursor-pointer transition-colors border-b border-slate-800/40 last:border-0 relative group",
                              isActive ? "bg-cyan-500/5" : "hover:bg-slate-800/30",
                            )}
                          >
                            {isActive && (
                              <td className="absolute inset-y-0 left-0 w-[3px] bg-gradient-to-b from-cyan-400 via-cyan-500 to-blue-600 shadow-[0_0_12px_rgba(6,182,212,0.7)]" />
                            )}
                            <td className="px-4 py-3 font-mono text-[11px] text-cyan-400 group-hover:text-cyan-300">
                              {row.id}
                            </td>
                            <td
                              className={cn(
                                "px-4 py-3 text-sm",
                                isActive ? "text-slate-50 font-medium" : "text-slate-300",
                              )}
                              title={row.descricao}
                            >
                              {truncate(row.descricao, 60)}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <Badge
                                  variant="outline"
                                  className={cn(
                                    "text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 border",
                                    tone.bg,
                                    tone.text,
                                    tone.border,
                                  )}
                                >
                                  {s}
                                </Badge>
                                <span className="text-[10px] text-slate-500 font-mono">
                                  {row.gravidade_label}
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-right text-slate-200 font-mono text-xs tabular-nums">
                              {row.pontos} pts
                            </td>
                            <td className="px-4 py-3 text-center">
                              <Switch checked disabled className="data-[state=checked]:bg-emerald-500/70" />
                            </td>
                          </tr>
                        );
                      })}
                      {filtered.length === 0 && (
                        <tr>
                          <td
                            colSpan={5}
                            className="px-4 py-12 text-center text-slate-500 text-sm"
                          >
                            Nenhuma infração corresponde à busca.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            </GlassCard>

            {/* ─────────── RIGHT: detail panel ─────────── */}
            <GlassCard
              className="flex-1 flex flex-col overflow-hidden min-w-0"
              glow={sev === "Crítico" ? "red" : sev === "Alto" ? "amber" : "blue"}
            >
              {effectiveSelected && sev ? (
                <>
                  <CardContent className="p-5 pb-4 border-b border-slate-800/60">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <Badge
                        variant="outline"
                        className="bg-cyan-500/10 text-cyan-300 border-cyan-500/40 font-mono"
                      >
                        {effectiveSelected.id}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={cn(
                          "uppercase font-bold tracking-wider border",
                          SEV_TONE[sev].bg,
                          SEV_TONE[sev].text,
                          SEV_TONE[sev].border,
                        )}
                      >
                        {sev}
                      </Badge>
                      <Badge
                        variant="outline"
                        className="bg-slate-800/50 text-slate-300 border-slate-700 font-mono text-[10px]"
                      >
                        {effectiveSelected.gravidade_label}
                      </Badge>
                      <Badge
                        variant="outline"
                        className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      >
                        <CheckCircle2 size={11} className="mr-1" /> Ativo
                      </Badge>
                    </div>
                    <h2 className="text-lg font-bold text-slate-50 leading-tight">
                      {effectiveSelected.descricao}
                    </h2>
                    <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                      Infração oficial prevista na{" "}
                      <span className="text-slate-300">{data?.nome ?? versaoLabel}</span>. Detecção
                      realizada pelo pipeline VLM com base nas câmeras indicadas.
                    </p>
                  </CardContent>

                  <div className="flex-1 overflow-y-auto p-5 space-y-6 custom-scrollbar">
                    {/* Parâmetros estáticos */}
                    <section>
                      <h3 className="text-xs font-semibold text-slate-100 flex items-center gap-2 mb-3 uppercase tracking-wider">
                        <Sliders size={14} className="text-cyan-400" /> Definição
                      </h3>
                      <div className="grid grid-cols-2 gap-3">
                        <ParamStat
                          icon={Target}
                          label="Pontos"
                          value={`${effectiveSelected.pontos}`}
                          suffix="pts"
                          tone="cyan"
                        />
                        <ParamStat
                          icon={ShieldAlert}
                          label="Gravidade"
                          value={effectiveSelected.gravidade_label}
                          tone={sev === "Crítico" ? "red" : sev === "Alto" ? "amber" : "emerald"}
                        />
                        <ParamStat
                          icon={CameraIcon}
                          label="Câmeras"
                          value={formatCameras(effectiveSelected.cameras)}
                          tone="blue"
                          mono
                        />
                        <ParamStat
                          icon={Scale}
                          label="Base Legal"
                          value={effectiveSelected.base_legal ?? baseLegalFallback}
                          tone="violet"
                          mono
                          small
                        />
                      </div>
                    </section>

                    {/* Condição de disparo */}
                    <section>
                      <h3 className="text-xs font-semibold text-slate-100 flex items-center gap-2 mb-3 uppercase tracking-wider">
                        <ShieldAlert size={14} className="text-cyan-400" /> Condição de disparo
                      </h3>
                      <div className="bg-slate-950/60 border border-slate-800 rounded-md p-4 font-mono text-xs leading-relaxed">
                        <div>
                          <span className="text-amber-400">IF</span>{" "}
                          <span className="text-slate-300">vlm_detects(</span>
                          <span className="text-cyan-300">"{effectiveSelected.id}"</span>
                          <span className="text-slate-300">)</span>
                        </div>
                        <div>
                          <span className="text-amber-400">AND</span>{" "}
                          <span className="text-slate-300">confidence ≥</span>{" "}
                          <span className="text-cyan-300">"MÉDIA"</span>
                        </div>
                        <div>
                          <span className="text-amber-400">THEN</span>{" "}
                          <span className="text-slate-300">score +=</span>{" "}
                          <span className="text-cyan-300">{effectiveSelected.pontos}</span>{" "}
                          <span className="text-slate-600">
                            // {effectiveSelected.gravidade_label}
                          </span>
                        </div>
                        <div className="mt-2 pt-2 border-t border-slate-800/60">
                          <span className="text-amber-400">IF</span>{" "}
                          <span className="text-slate-300">score &gt;</span>{" "}
                          <span className="text-cyan-300">{data?.limite_pontuacao ?? 20}</span>{" "}
                          <span className="text-amber-400">THEN</span>{" "}
                          <span className="text-red-400">reprova_candidato()</span>
                        </div>
                      </div>
                    </section>

                    {/* Editor de parâmetros mensuráveis */}
                    <ParametrosMensuraveisEditor
                      slug={data?.slug ?? "1020/2025"}
                      infracao={effectiveSelected}
                    />

                    {/* Base legal completa */}
                    <section>
                      <h3 className="text-xs font-semibold text-slate-100 flex items-center gap-2 mb-3 uppercase tracking-wider">
                        <History size={14} className="text-cyan-400" /> Base legal
                      </h3>
                      <div className="bg-slate-950/60 border border-slate-800 rounded-md p-4">
                        <p className="text-sm text-slate-200 leading-relaxed font-mono">
                          {effectiveSelected.base_legal ?? `${baseLegalFallback}, Art. 22`}
                        </p>
                        <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
                          Esta infração é parte da rubrica oficial{" "}
                          <span className="text-slate-300">{data?.nome ?? versaoLabel}</span>. O
                          VALBOT aplica a classificação exatamente como publicada no DOU;
                          alterações na legislação exigem atualização da rubrica no backend.
                        </p>
                      </div>
                    </section>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                  {isLoading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin" /> Carregando…
                    </span>
                  ) : (
                    "Selecione uma infração à esquerda."
                  )}
                </div>
              )}
            </GlassCard>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// ParamStat — bloco de parâmetro estático
// ──────────────────────────────────────────────────────────────────────────

function ParamStat({
  icon: Icon,
  label,
  value,
  suffix,
  tone,
  mono,
  small,
}: {
  icon: any;
  label: string;
  value: string | number;
  suffix?: string;
  tone: "cyan" | "blue" | "emerald" | "amber" | "red" | "violet";
  mono?: boolean;
  small?: boolean;
}) {
  const tones = {
    cyan: "text-cyan-400",
    blue: "text-blue-400",
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    red: "text-red-400",
    violet: "text-violet-400",
  };
  return (
    <div className="bg-slate-950/40 border border-slate-800/80 rounded-md p-3 hover:border-slate-700 transition-colors">
      <p
        className={cn(
          "text-[10px] uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1.5 font-medium",
        )}
      >
        <Icon size={11} className={tones[tone]} /> {label}
      </p>
      <p
        className={cn(
          mono ? "font-mono" : "font-sans",
          small ? "text-[11px] leading-snug" : "text-base font-semibold",
          "text-slate-100",
        )}
      >
        {value}
        {suffix && (
          <span className="text-[11px] text-slate-500 font-normal ml-1">{suffix}</span>
        )}
      </p>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// ParametrosMensuraveisEditor — slider elegante por parâmetro
// ──────────────────────────────────────────────────────────────────────────

type ParamRow = {
  key: string;
  value: string;
  unit: string;
  description: string;
};

function ParametrosMensuraveisEditor({
  slug,
  infracao,
}: {
  slug: string;
  infracao: RubricaInfracao;
}) {
  const { isAdmin } = useAuth();
  const qc = useQueryClient();
  const [rows, setRows] = useState<ParamRow[]>([]);
  const [hint, setHint] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ text: string; tone: "ok" | "ai" | "error" } | null>(null);

  useEffect(() => {
    const src = infracao.parametros ?? {};
    setRows(
      Object.entries(src).map(([k, v]) => ({
        key: k,
        value: String(v.value),
        unit: v.unit ?? "",
        description: v.description ?? "",
      })),
    );
    setHint(infracao.vlm_prompt_hint ?? "");
    setMsg(null);
  }, [infracao.id]);

  const addRow = () =>
    setRows((r) => [...r, { key: "", value: "0", unit: "", description: "" }]);
  const delRow = (idx: number) => setRows((r) => r.filter((_, i) => i !== idx));
  const updRow = (idx: number, patch: Partial<ParamRow>) =>
    setRows((r) => r.map((row, i) => (i === idx ? { ...row, ...patch } : row)));

  async function handleSave() {
    setSaving(true);
    setMsg(null);
    const parametros: Record<string, { value: number; unit: string; description: string }> = {};
    for (const r of rows) {
      if (!r.key.trim()) continue;
      const num = parseFloat(r.value.replace(",", "."));
      if (Number.isNaN(num)) {
        setMsg({ text: `Valor inválido em "${r.key}"`, tone: "error" });
        setSaving(false);
        return;
      }
      parametros[r.key.trim()] = {
        value: num,
        unit: r.unit.trim(),
        description: r.description.trim(),
      };
    }
    try {
      const r = await fetch(
        `/v2/rubricas/${encodeURIComponent(slug)}/infracao/${infracao.id}/parametros`,
        {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ parametros, vlm_prompt_hint: hint }),
        },
      );
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      setMsg({ text: "✓ Salvo. Próximo upload usará esses valores.", tone: "ok" });
      qc.invalidateQueries({ queryKey: ["rubrica"] });
    } catch (e) {
      setMsg({ text: `Erro: ${(e as Error).message}`, tone: "error" });
    } finally {
      setSaving(false);
    }
  }

  async function handleSuggest() {
    setSaving(true);
    setMsg({ text: "Consultando Qwen (30s–1min)…", tone: "ai" });
    try {
      const r = await fetch(
        `/v2/rubricas/${encodeURIComponent(slug)}/infracao/${infracao.id}/suggest-params`,
        { method: "POST", credentials: "include" },
      );
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      const sug = data.suggestion || {};
      const newRows: ParamRow[] = Object.entries(sug.parametros || {}).map(
        ([k, v]: [string, any]) => ({
          key: k,
          value: String(v.value ?? 0),
          unit: v.unit ?? "",
          description: v.description ?? "",
        }),
      );
      setRows(newRows);
      if (sug.vlm_prompt_hint) setHint(sug.vlm_prompt_hint);
      setMsg({ text: "✨ Sugestão do Qwen carregada — revise e salve.", tone: "ai" });
    } catch (e) {
      setMsg({ text: `Erro: ${(e as Error).message}`, tone: "error" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-slate-100 flex items-center gap-2 uppercase tracking-wider">
          <Target size={14} className="text-violet-400" /> Parâmetros mensuráveis
        </h3>
        {!isAdmin && (
          <Badge
            variant="outline"
            className="text-[10px] bg-slate-800/40 text-slate-400 border-slate-700"
          >
            <Lock size={10} className="mr-1" /> Somente leitura
          </Badge>
        )}
      </div>

      {/* Prompt hint */}
      <div className="bg-slate-950/40 border border-slate-800/80 rounded-md p-3 mb-3 space-y-2">
        <Label className="text-[10px] text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <Sparkles size={11} className="text-violet-400" /> Prompt hint injetado no VLM
        </Label>
        <Textarea
          value={hint}
          disabled={!isAdmin}
          onChange={(e) => setHint(e.target.value)}
          placeholder="Ex: Procure placa PARE. Se veículo cruzou a linha sem parar ≥ min_parada_s segundos, é infração."
          className="bg-slate-950/60 border-slate-800 text-xs text-slate-200 placeholder:text-slate-600 font-mono min-h-[80px] focus-visible:ring-violet-500/40 focus-visible:border-violet-500/50 resize-y"
        />
      </div>

      {/* Param sliders */}
      {rows.length === 0 && (
        <div className="text-xs text-slate-500 italic mb-3 p-4 bg-slate-950/30 rounded-md border border-dashed border-slate-800">
          Nenhum parâmetro definido ainda.
        </div>
      )}

      <div className="space-y-2.5 mb-3">
        {rows.map((row, idx) => (
          <ParamSliderRow
            key={idx}
            row={row}
            disabled={!isAdmin}
            onChange={(patch) => updRow(idx, patch)}
            onDelete={() => delRow(idx)}
            canDelete={isAdmin}
          />
        ))}
      </div>

      {/* Actions */}
      {isAdmin && (
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={addRow}
            className="h-8 text-xs bg-slate-800/40 border-slate-700 text-slate-300 hover:bg-slate-700/60 hover:border-cyan-500/40 hover:text-cyan-300"
          >
            <Plus size={13} className="mr-1" /> Adicionar parâmetro
          </Button>
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={handleSuggest}
            disabled={saving}
            className="h-8 text-xs bg-violet-500/10 border-violet-500/40 text-violet-300 hover:bg-violet-500/20 shadow-[0_0_12px_-4px_rgba(139,92,246,0.5)]"
          >
            <Sparkles size={13} className="mr-1" /> Sugerir via IA
          </Button>
          <Button
            size="sm"
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="h-8 text-xs bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-700 hover:to-cyan-600 text-white border-cyan-500/40 shadow-[0_0_16px_-6px_rgba(6,182,212,0.7)]"
          >
            {saving ? (
              <Loader2 size={13} className="mr-1 animate-spin" />
            ) : (
              <Save size={13} className="mr-1" />
            )}
            {saving ? "Salvando…" : "Salvar"}
          </Button>
          {msg && (
            <span
              className={cn(
                "text-[11px] font-medium ml-1",
                msg.tone === "ok" && "text-emerald-400",
                msg.tone === "ai" && "text-violet-400",
                msg.tone === "error" && "text-red-400",
              )}
            >
              {msg.text}
            </span>
          )}
        </div>
      )}
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// ParamSliderRow — slider + input numérico sincronizados
// ──────────────────────────────────────────────────────────────────────────

function ParamSliderRow({
  row,
  disabled,
  canDelete,
  onChange,
  onDelete,
}: {
  row: ParamRow;
  disabled: boolean;
  canDelete: boolean;
  onChange: (patch: Partial<ParamRow>) => void;
  onDelete: () => void;
}) {
  const numericValue = parseFloat(row.value.replace(",", ".")) || 0;
  const bounds = useMemo(() => sliderBounds(row.key, numericValue), [row.key, numericValue]);

  const clamped = Math.min(Math.max(numericValue, bounds.min), bounds.max);
  const percent = ((clamped - bounds.min) / (bounds.max - bounds.min)) * 100;

  return (
    <div className="bg-slate-950/40 border border-slate-800/80 rounded-md p-3 hover:border-slate-700 transition-colors">
      <div className="grid grid-cols-12 gap-2 mb-2">
        <Input
          value={row.key}
          disabled={disabled}
          onChange={(e) => onChange({ key: e.target.value })}
          placeholder="chave (ex: min_parada_s)"
          className="col-span-5 h-8 bg-slate-950/60 border-slate-800 text-xs text-cyan-300 font-mono placeholder:text-slate-600 focus-visible:ring-cyan-500/50"
        />
        <Input
          value={row.unit}
          disabled={disabled}
          onChange={(e) => onChange({ unit: e.target.value })}
          placeholder="unidade"
          className="col-span-2 h-8 bg-slate-950/60 border-slate-800 text-xs text-slate-300 placeholder:text-slate-600 focus-visible:ring-cyan-500/50"
        />
        <Input
          value={row.description}
          disabled={disabled}
          onChange={(e) => onChange({ description: e.target.value })}
          placeholder="descrição"
          className={cn(
            "h-8 bg-slate-950/60 border-slate-800 text-xs text-slate-400 placeholder:text-slate-600 focus-visible:ring-cyan-500/50",
            canDelete ? "col-span-4" : "col-span-5",
          )}
        />
        {canDelete && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onDelete}
            className="col-span-1 h-8 w-8 text-slate-500 hover:text-red-400 hover:bg-red-500/10"
          >
            <Trash2 size={13} />
          </Button>
        )}
      </div>
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Slider
            value={[clamped]}
            min={bounds.min}
            max={bounds.max}
            step={bounds.step}
            disabled={disabled}
            onValueChange={(v) => onChange({ value: String(v[0]) })}
            className="[&_[role=slider]]:bg-cyan-400 [&_[role=slider]]:border-cyan-300 [&_[role=slider]]:shadow-[0_0_8px_rgba(6,182,212,0.6)] [&_.bg-primary]:bg-gradient-to-r [&_.bg-primary]:from-cyan-500 [&_.bg-primary]:to-blue-600"
          />
          <div className="flex justify-between mt-1 text-[9px] text-slate-600 font-mono tabular-nums">
            <span>{bounds.min}</span>
            <span className="text-slate-500">{percent.toFixed(0)}%</span>
            <span>{bounds.max}</span>
          </div>
        </div>
        <Input
          type="number"
          step={bounds.step}
          value={row.value}
          disabled={disabled}
          onChange={(e) => onChange({ value: e.target.value })}
          className="w-24 h-8 bg-slate-950/60 border-slate-800 text-xs text-slate-100 font-mono text-right tabular-nums focus-visible:ring-cyan-500/50"
        />
        {row.unit && (
          <span className="text-[11px] text-slate-500 font-mono w-10">{row.unit}</span>
        )}
      </div>
    </div>
  );
}
