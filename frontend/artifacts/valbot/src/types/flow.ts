export type FlowId = "qwen3-vl" | "gemini-3.1-pro" | "gpt-5.5";

export interface AnalysisFlow {
  id: FlowId;
  rank: 1 | 2 | 3;
  name: string;
  shortLabel: string;
  provider: string;
  costPerVideoUSD: number;
  latencySeconds: number;
  accuracyEstimate: string;
  description: string;
  type: "vídeo nativo" | "frame-extract" | "ponte texto";
}

export const ANALYSIS_FLOWS: AnalysisFlow[] = [
  {
    id: "qwen3-vl",
    rank: 1,
    name: "Qwen3-VL-235B",
    shortLabel: "Qwen",
    provider: "Alibaba · OpenRouter",
    costPerVideoUSD: 0.025,
    latencySeconds: 45,
    accuracyEstimate: "78–94% (FT)",
    description: "Vídeo nativo · vencedor TCO · MoE 22B ativo",
    type: "vídeo nativo",
  },
  {
    id: "gemini-3.1-pro",
    rank: 2,
    name: "Gemini 3.1 Pro Preview",
    shortLabel: "Gemini",
    provider: "Google · OpenRouter",
    costPerVideoUSD: 0.18,
    latencySeconds: 75,
    accuracyEstimate: "85–96% (FT)",
    description: "Vídeo nativo · líder VideoMME 84.8% · 2M context",
    type: "vídeo nativo",
  },
  {
    id: "gpt-5.5",
    rank: 3,
    name: "GPT-5.5",
    shortLabel: "GPT",
    provider: "OpenAI · OpenRouter",
    costPerVideoUSD: 0.19,
    latencySeconds: 105,
    accuracyEstimate: "82–94% (FT)",
    description: "Frame-extract @1fps · 1M context",
    type: "frame-extract",
  },
];

export const DEFAULT_FLOW: FlowId = "qwen3-vl";

export function getFlow(id: FlowId): AnalysisFlow {
  return ANALYSIS_FLOWS.find((f) => f.id === id) ?? ANALYSIS_FLOWS[0];
}
