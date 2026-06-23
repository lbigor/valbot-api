import React, { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  Loader2,
  Send,
  ShieldCheck,
} from "lucide-react";

// ============================================================================
// Tipos compartilhados com Galeria.tsx
// ============================================================================

type VideoMeta = {
  filename: string;
  hash: string;
  duration_s?: number;
};

type CintoFrame = {
  fase: string;
  pos_pct: number;
  timestamp_s: number;
  frame_idx: number;
  image_path: string;
};

export type ParcialCinto = {
  video: VideoMeta;
  id: string;
  descricao: string;
  tier: "A" | "B";
  tipo: "cinto_pendente";
  veredito: string;
  motivo: string;
  frames_extraidos: number;
  frames_paths: string[];
};

type DetectionBox = {
  frame_idx: number;
  timestamp_s: number;
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number];
};

export type ParcialSinal = {
  video: VideoMeta;
  id: string;
  descricao: string;
  tier: "A" | "B";
  tipo: "sinal_vertical";
  veredito: string;
  stats: {
    total_relevantes: number;
    overlay_fp: number;
    confiavel: number;
    suspeito: number;
    descartado: number;
  };
  candidatos_confiavel: DetectionBox[];
  candidatos_suspeito: DetectionBox[];
};

export type ParcialItem = ParcialCinto | ParcialSinal;

// ============================================================================
// Modal: revisão DETRAN inline
// ============================================================================

type Decision = "approved" | "refuted" | null;

export function RevisaoDetranModal({
  parcial,
  open,
  onOpenChange,
}: {
  parcial: ParcialItem | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qc = useQueryClient();
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [evidencia, setEvidencia] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<{ count: number } | null>(null);

  // Reseta quando abre/fecha ou troca de item
  React.useEffect(() => {
    if (open) {
      setDecisions({});
      setEvidencia("");
      setDone(null);
    }
  }, [open, parcial?.video?.hash, parcial?.id]);

  const items = useMemo(() => {
    if (!parcial) return [] as Array<{ key: string; ts: number; img?: string; meta: string }>;
    if (parcial.tipo === "cinto_pendente") {
      return parcial.frames_paths.map((path, i) => ({
        key: `frame-${i}`,
        ts: 0, // cinto sampler não expõe ts diretamente — placeholder
        img: path,
        meta: `Frame ${i + 1}/${parcial.frames_paths.length} · BL`,
      }));
    }
    // sinal_vertical: usa candidatos como itens individuais
    return [...parcial.candidatos_confiavel, ...parcial.candidatos_suspeito].map((c, i) => ({
      key: `cand-${i}-${c.frame_idx}`,
      ts: c.timestamp_s,
      img: undefined,
      meta: `${c.class_name} · conf ${c.confidence.toFixed(2)} · t=${c.timestamp_s.toFixed(1)}s`,
    }));
  }, [parcial]);

  const remaining = items.length - Object.keys(decisions).length;

  const submit = useMutation({
    mutationFn: async () => {
      if (!parcial) throw new Error("sem item");
      const hash = parcial.video.hash;
      const calls = Object.entries(decisions).map(([key, decision]) => {
        const item = items.find((x) => x.key === key);
        if (!item || !decision) return null;
        const vote = decision === "approved" ? "S" : "N";
        const body = {
          infracao_id: parcial.id,
          ts: item.ts,
          decisao: decision,
          evidencia,
          vote,
        };
        return fetch(`/api/analyses/${hash}/training-example`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }).then((r) => r.json());
      });
      const results = await Promise.all(calls.filter(Boolean) as Promise<any>[]);
      return results.length;
    },
    onSuccess: (n) => {
      setDone({ count: n });
      qc.invalidateQueries({ queryKey: ["galeria"] });
      qc.invalidateQueries({ queryKey: ["videos"] });
      qc.invalidateQueries({ queryKey: ["analysis-tier-a"] });
    },
  });

  if (!parcial) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#111827] border-[#1F2937] text-white max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-[#F9FAFB] flex items-center gap-3">
            <ShieldCheck size={20} className="text-[#06B6D4]" />
            Revisão DETRAN — {parcial.id}
            <Badge className="bg-[#EF4444]/10 text-[#F87171] border-[#EF4444]/20 text-[10px] uppercase">
              Tier {parcial.tier}
            </Badge>
          </DialogTitle>
          <DialogDescription className="text-[#9CA3AF]">
            {parcial.video.filename} · {parcial.descricao}. Marque cada
            evidência como <b>presente</b> (S) ou <b>refutada</b> (N). Os votos
            entram no <code className="kbd">examples.jsonl</code> e
            retroalimentam o filtro YOLO da próxima execução.
          </DialogDescription>
        </DialogHeader>

        {!done && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-2">
              {items.map((it) => {
                const d = decisions[it.key];
                return (
                  <div
                    key={it.key}
                    className={`rounded border bg-[#0B1120] overflow-hidden ${
                      d === "approved"
                        ? "border-[#10B981]"
                        : d === "refuted"
                        ? "border-[#EF4444]"
                        : "border-[#1F2937]"
                    }`}
                  >
                    {it.img ? (
                      <img
                        src={it.img}
                        alt={it.key}
                        className="w-full aspect-video object-cover bg-black"
                      />
                    ) : (
                      <div className="w-full aspect-video flex items-center justify-center bg-gradient-to-br from-[#1e293b] to-[#0f172a] text-[10px] text-[#6B7280] font-mono">
                        sinal vertical · sem thumbnail
                      </div>
                    )}
                    <div className="p-2 space-y-2">
                      <div className="text-[11.5px] text-[#9CA3AF]">{it.meta}</div>
                      <div className="grid grid-cols-3 gap-1 text-[11px]">
                        <button
                          onClick={() =>
                            setDecisions({ ...decisions, [it.key]: "approved" })
                          }
                          className={`py-1.5 rounded flex items-center justify-center gap-1 ${
                            d === "approved"
                              ? "bg-[#10B981] text-white"
                              : "bg-[#1F2937] text-[#10B981] hover:bg-[#10B981]/20"
                          }`}
                        >
                          <CheckCircle2 size={12} /> S
                        </button>
                        <button
                          onClick={() =>
                            setDecisions({ ...decisions, [it.key]: "refuted" })
                          }
                          className={`py-1.5 rounded flex items-center justify-center gap-1 ${
                            d === "refuted"
                              ? "bg-[#EF4444] text-white"
                              : "bg-[#1F2937] text-[#EF4444] hover:bg-[#EF4444]/20"
                          }`}
                        >
                          <XCircle size={12} /> N
                        </button>
                        <button
                          onClick={() => {
                            const c = { ...decisions };
                            delete c[it.key];
                            setDecisions(c);
                          }}
                          className="py-1.5 rounded flex items-center justify-center bg-[#1F2937] text-[#9CA3AF] hover:bg-[#374151]"
                        >
                          <HelpCircle size={12} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 space-y-2">
              <label className="text-[12px] text-[#9CA3AF]">
                Evidência / observação (≤15 palavras, opcional)
              </label>
              <input
                type="text"
                value={evidencia}
                onChange={(e) => setEvidencia(e.target.value)}
                placeholder="ex.: jaqueta escura — contraste insuficiente, mas sanity-check passa"
                className="w-full bg-[#0B1120] border border-[#1F2937] rounded px-3 py-2 text-sm focus:outline-none focus:border-[#1D4ED8]"
              />
            </div>

            <div className="mt-4 flex items-center justify-between">
              <div className="text-[12px] text-[#9CA3AF]">
                {Object.keys(decisions).length}/{items.length} marcados ·{" "}
                {remaining > 0 ? `${remaining} restantes` : "tudo decidido"}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  className="bg-[#111827] border-[#1F2937] text-[#9CA3AF]"
                  onClick={() => onOpenChange(false)}
                  disabled={submit.isPending}
                >
                  Cancelar
                </Button>
                <Button
                  className="bg-[#1D4ED8] hover:bg-[#1E40AF] text-white"
                  onClick={() => {
                    setSubmitting(true);
                    submit.mutate();
                  }}
                  disabled={
                    Object.keys(decisions).length === 0 || submit.isPending
                  }
                >
                  {submit.isPending ? (
                    <>
                      <Loader2 size={14} className="mr-2 animate-spin" /> Gravando…
                    </>
                  ) : (
                    <>
                      <Send size={14} className="mr-2" /> Gravar {Object.keys(decisions).length} voto(s)
                    </>
                  )}
                </Button>
              </div>
            </div>
          </>
        )}

        {done && (
          <div className="flex flex-col items-center justify-center py-8 gap-3 text-center">
            <CheckCircle2 size={48} className="text-[#10B981]" />
            <div className="text-lg font-semibold">
              {done.count} voto(s) registrado(s)
            </div>
            <div className="text-[12.5px] text-[#9CA3AF] max-w-md">
              Os votos foram gravados em
              <code className="kbd mx-1">storage/training/examples.jsonl</code>
              e serão aplicados como filtro YOLO no próximo
              <code className="kbd mx-1">tier_a_pipeline --force</code>
              deste vídeo.
            </div>
            <Button
              className="bg-[#1D4ED8] hover:bg-[#1E40AF] text-white mt-2"
              onClick={() => onOpenChange(false)}
            >
              Fechar
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
