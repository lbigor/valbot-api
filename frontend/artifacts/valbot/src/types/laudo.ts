/**
 * Contrato TypeScript do resultado de análise do LaudoAI.
 *
 * Espelha o schema de `storage/analyses/<hash>/result.json` produzido pelo
 * backend Python (`backend/app/workers/pipeline.py`).
 *
 * Fonte de verdade do schema: `result_json` em `process_video()`.
 * Atualizar em conjunto quando novos campos forem adicionados ao backend.
 */

export type Gravidade =
  | "eliminatoria"
  | "gravissima"
  | "grave"
  | "media"
  | "leve"
  | "etica";

export type GravidadeLabel =
  | "ELIMINATÓRIA"
  | "GRAVÍSSIMA"
  | "GRAVE"
  | "MÉDIA"
  | "LEVE"
  | "ÉTICA";

export type Confianca = "ALTA" | "MÉDIA" | "BAIXA";

export type Camera =
  | "interna"
  | "retrovisor_esquerdo"
  | "retrovisor_direito"
  | "traseira";

export type RubricaSlug = "789/2020" | "1020/2025";

/** Uma infração já enriquecida pelo scoring (item de `scored.infracoes`). */
export interface Infracao {
  id: string;                       // ex: "R1020-L-c"
  timestamp_inicio: string;         // "MM:SS"
  timestamp_fim: string;            // "MM:SS"
  duracao_seg: number;
  duracao_fmt: string;              // ex: "1min45s" ou "8s"
  occurrences: number;              // nº de detecções mescladas no cluster
  gravidade: Gravidade;
  gravidade_label: GravidadeLabel;
  pontos: number;
  confianca: Confianca;
  cameras: Camera[];
  cameras_fmt: string;              // ex: "Interna + Retrovisor Esquerdo"
  titulo: string;
  descricao: string;                // descrição curta
  descricao_longa: string;
  evidencia: string;                // texto descritivo da detecção
  base_legal: string;
  /** Path relativo à raiz do projeto (ex: "storage/analyses/<h>/clips/..."). */
  clip_path?: string | null;
  clip_error?: string;
  frame_evidencia_path?: string | null;
  frame_evidencia_error?: string;
  veredito?: Veredito;
  origem?: VeredictoOrigem;
  decisao_evidencia?: string;
  /** v25 — quem proferiu a fala/conduta antiética (apenas para gravidade=etica). */
  ator?: "EXAMINADOR" | "CANDIDATO" | null;
}

export type Veredito =
  | "detectado"
  | "aprovado"
  | "refutado"
  | "inconclusivo"
  | "pendente";

export type VeredictoOrigem =
  | "infracoes_detectadas"
  | "infracoes_avaliadas"
  | "examples_jsonl";

export interface Contagem {
  eliminatoria: number;
  gravissima: number;
  grave: number;
  media: number;
  leve: number;
  etica?: number;  // v25 — conduta ética detectada via áudio
}

export interface TimelineEntry {
  timestamp: string;                // "MM:SS"
  description: string;
  gravidade: Gravidade | null;
  gravidade_label: GravidadeLabel | null;
  pct: number;                      // 0..100 — posição visual na timeline
}

export interface Exame {
  candidato: string;
  cpf: string;
  renach: string;
  processo: string;
  categoria: string;
  veiculo: string;
  local: string;
  examinador: string;
  data_exame: string;
}

/** Campos do summary agregado — base pra cards e métricas do frontend. */
export interface Summary {
  laudo_id: string;
  video_path: string;
  video_hash: string;
  result_hash: string;
  pdf_path: string;
  rubrica: RubricaSlug;
  aprovado: boolean;
  pontuacao_total: number;
  contagem: Contagem;
  duracao_seg: number;
  num_infracoes: number;
  num_frames: number;
  elapsed_sec: number;
  created_at: string;               // ISO
  model_version: string;
  software_version: string;

  // Derivados (pipeline.py → _compute_derivatives)
  score_risco: number;              // 0..100
  confianca_media: number;          // 0..100 (média ponderada)
  cameras_envolvidas: Camera[];
  duracao_total_infracoes_seg: number;
  densidade_infracoes_por_min: number;

  // Profile opcional (presente quando psutil + mlx estão disponíveis)
  profile?: Profile;

  // Qualidade do áudio (transcript Whisper + VAD).
  // - "ok"           → transcript confiável
  // - "degraded"     → sinal fraco / ruído / Whisper com baixa confiança
  // - "hallucinated" → Whisper produziu fala inexistente (detectado por heurística)
  // - "no_speech"    → nenhuma fala detectada pelo VAD
  audio_quality_flag?: "ok" | "degraded" | "hallucinated" | "no_speech";
  audio_quality_reason?: string;
  vad_speech_duration_s?: number;
}

export interface Scored {
  infracoes: Infracao[];
  contagem: Contagem;
  pontuacao_total: number;
  aprovado: boolean;
  motivo_reprovacao: string | null;
}

export interface ProfileStage {
  name: string;
  elapsed_s: number;
  cached?: boolean;
  rss_mb_after?: number;
  rss_delta_mb?: number;
  metal_active_mb?: number;
  metal_peak_mb?: number;
  metal_cache_mb?: number;
  n_frames?: number;
  n_batches?: number;
  batch_size?: number;
  n_infracoes?: number;
  segments?: number;
}

export interface Profile {
  stages: ProfileStage[];
  total_elapsed_s: number;
  rss_peak_mb: number | null;
  has_psutil: boolean;
  has_mlx: boolean;
}

/** Raw do VLM — útil pra debug / auditoria, não pra UI direto. */
export interface VlmRaw {
  events: Array<Record<string, unknown>>;
  timeline: Array<Record<string, unknown>>;
  positive_aspects: string[];
  attention_points: string[];
}

/** Corpo completo do `result.json`. */
export interface LaudoResult {
  summary: Summary;
  scored: Scored;
  vlm: VlmRaw;
  timeline: TimelineEntry[];
  positivos: string[];
  pontos_atencao: string[];
  exame: Exame;
  canonical: Record<string, unknown>;   // hash determinístico (read-only)
  context_keys: string[];
  profile?: Profile;
}

/**
 * Linha da tabela `analyses` (backend/app/db.py). Usada pela lista de análises
 * no frontend. O `result_json` é string JSON; parse para `LaudoResult`.
 */
export interface AnalysisRow {
  id: string;
  video_hash: string;
  video_path: string;
  analysis_version: number;
  rubrica: RubricaSlug;
  model_version: string;
  software_version: string;
  result_hash: string | null;
  result_json: string | null;       // JSON stringify de LaudoResult
  pdf_path: string | null;
  status: "uploaded" | "processing" | "completed" | "failed";
  aprovado: 0 | 1 | null;
  pontuacao_total: number | null;
  num_infracoes: number | null;
  duracao_seg: number | null;
  score_risco: number | null;
  confianca_media: number | null;
  duracao_total_infracoes_seg: number | null;
  densidade_infracoes_por_min: number | null;
  cameras_list: string | null;      // JSON stringify de Camera[]
  candidato_nome: string | null;
  candidato_cpf: string | null;
  needs_review: 0 | 1;
  created_at: string;
  completed_at: string | null;
  error: string | null;
}

/**
 * Tag estruturada de um comentário humano de revisão (source="human_review").
 * - refuto          → revisor discorda da detecção/ausência
 * - faltou_detectar → IA não detectou algo que deveria
 * - reclassifico    → infração existe mas com gravidade/rubrica diferente
 * - observacao      → comentário livre, sem veredito
 */
export type ReviewTag = "refuto" | "faltou_detectar" | "reclassifico" | "observacao";

/** Anotação humana persistida em annotations.json. */
export interface Annotation {
  id: string;
  /**
   * Pode ser null quando `source === "human_review"` — comentário livre não
   * precisa estar atrelado a uma infração específica.
   */
  infraction_id: string | null;
  timestamp_start: string;
  timestamp_end: string;
  confidence: Confianca;
  note: string;
  /**
   * - `"attention"`     → ponto de atenção do VLM; marker roxo.
   * - `"human_review"`  → comentário humano ancorado em range temporal para
   *                       recalibrar o prompt; não pontua no laudo.
   */
  source: "manual" | "vlm_confirmed" | "vlm_refuted" | "attention" | "human_review";
  vlm_response: string | null;
  created_at: string;
  cameras?: Camera[];
  suspected_id?: string;
  /** Tag estruturada, só presente quando source === "human_review". */
  review_tag?: ReviewTag;
  /** Email do revisor que criou o comentário (injetado pelo backend). */
  author_email?: string | null;
}

/**
 * Subset de `Annotation` com `source === "attention"`. Útil pra tipar hidratação
 * em componentes que só se importam com pontos de atenção (markers roxos).
 */
export interface AttentionAnnotation extends Annotation {
  source: "attention";
}

/** Subset de `Annotation` com `source === "human_review"`. */
export interface HumanReviewAnnotation extends Annotation {
  source: "human_review";
  review_tag?: ReviewTag;
}

/** Resposta do /api/analyses/<hash>/analyze-segment. */
export interface SegmentAnalysisResponse {
  verdict: "confirmado" | "refutado" | "outra_infração" | "sem_evidência";
  infraction_id: string | null;
  confidence: Confianca;
  explanation: string;
  evidence: string;
  raw_response: string;
  frame_paths: string[];
  segment_analyzed: {
    start_sec: number;
    end_sec: number;
    focus_start_sec: number;
    focus_end_sec: number;
  };
}

/**
 * Item de vídeo retornado por `GET /api/videos`. Lista vídeos descobertos em
 * storage/videos + metadados de análises já realizadas (quando `has_result`).
 */
export interface VideoItem {
  path: string;
  absolute_path: string;
  filename: string;
  size_mb: number;
  mtime: string;
  in_storage: boolean;
  hash: string;
  has_result: boolean;
  /** Status derivado da tabela `analyses` merged com presença de result.json.
   * Alinhado com `_write_status()` em tooling/api_stub/server.py (queued/running/processed/...)
   * e mantém os legados `pending`/`processing`/`completed` por compatibilidade. */
  status?:
    | "uploading"
    | "queued"
    | "streaming_s3"
    | "running"
    | "processed"
    | "processed_no_pdf"
    | "failed"
    | "pending"
    | "processing"
    | "completed";
  error?: string;
  laudo_id?: string;
  num_infracoes?: number;
  pontuacao_total?: number;
  aprovado?: boolean;
  score_risco?: number;
  pdf_url?: string;
  training_iterations?: number;
  /** Categoria CNH detectada (A, B, AB, ACC, AC, AD, AE). Vem do laudo
   *  (`result.candidato.categoria`) com fallback para o upload. */
  categoria_cnh?: string;
  /** Veredito do gate de admissibilidade (PASSO 0 v25). `true` = rejeitado;
   *  `false` = passou; `null` = ainda não processado. */
  gate_rejected?: boolean | null;
  /** Motivo curto da rejeição (`fabricante_desconhecido`, `duracao_insuficiente`,
   *  `video_sem_metadata`, `nao_e_exame_pratico`). Vazio quando não rejeitado. */
  gate_motivo?: string;
  /** F6 — Resultado calculado pela coluna STORED `exams.resultado` (Postgres).
   *  6 estados: PENDENTE/PROCESSANDO/FALHOU/SEM_AVALIACAO/APROVADO/INAPTO.
   *  Substitui a derivação que era feita no frontend (não considerava gate_rejected). */
  resultado?:
    | "PENDENTE"
    | "PROCESSANDO"
    | "FALHOU"
    | "SEM_AVALIACAO"
    | "APROVADO"
    | "INAPTO"
    | "INDEFINIDO";
  /** Veredito do examinador/preposto DETRAN gravado no init_upload.
   *  A = Aprovado, R = Reprovado, N = Não avaliado, null = sem informação. */
  resultado_exame?: "A" | "R" | "N" | null;
  /** Divergência após o Comitê de IA reavaliar com o prompt MBEDV.
   * "sem_divergencia" = comitê resolveu (não entra na fila); outro/undefined = ainda diverge. */
  tipo_divergencia_pos_comite?: string | null;
  /** URL fonte do vídeo no momento do init_upload (S3 AWS oficial ou outra origem).
   *  Lida do upload.json — não está na view v_exams_overview. Null se o
   *  upload.json não existe ou não tem `video.source_url`. */
  source_url?: string | null;
  /** Classificador binário do backend: true quando `source_url` bate em
   *  amazonaws.com / s3://. Por default `/api/videos` esconde os não-reais;
   *  passar `?include_test=true` traz tudo. */
  is_real?: boolean;
  /** Envio do laudo pra Unidade Gestora (Techpratico). Migration 008. */
  laudo_enviado_em?: string | null;
  laudo_envio_status?: "success" | "failed" | "sending" | null;
  laudo_envio_resultado?: "A" | "R" | "N" | null;
  /** Veredito do validador independente (ground truth Gemini) — HOMO/NAO_HOMO. */
  validator_veredito?: string | null;
  /** Confiança do validador independente (0..1). */
  validator_confianca?: number | null;
  /** Custo da chamada Gemini desse exame (USD). */
  cost_usd?: number | null;
}

/**
 * Envelope de paths do backend anexado a LaudoResult/LaudoResponse via `_paths`.
 * Contém URLs estáticas derivadas para vídeo e PDF, mais o hash da análise.
 */
export interface LaudoPaths {
  video_static: string | null;
  analysis_hash: string;
  base_static: string;
  pdf_url: string | null;
}

/**
 * Resposta completa das rotas `/api/laudo-atual` e `/api/analyses/:hash/result` —
 * um LaudoResult acrescido de `_paths` com URLs prontas para consumo no frontend.
 */
export type LaudoResponse = LaudoResult & {
  _paths?: LaudoPaths;
};

/**
 * Uma infração da rubrica — item estático da Resolução CONTRAN carregado
 * via `GET /api/rubricas/:slug`. Diferente de `Infracao` (que é uma detecção
 * enriquecida pelo scoring), aqui só temos os metadados da regra.
 */
export interface RubricaParam {
  value: number;
  unit: string;
  description: string;
}

export interface RubricaInfracao {
  id: string;                   // ex: "R1020-G-a"
  gravidade: Gravidade;
  gravidade_label: GravidadeLabel;
  pontos: number;
  descricao: string;
  base_legal?: string;
  cameras?: Camera[];
  /** Parâmetros mensuráveis por regra (editáveis pelo admin via UI). */
  parametros?: Record<string, RubricaParam>;
  /** Hint específico que é injetado no prompt do VLM para essa regra. */
  vlm_prompt_hint?: string;
}

/** Rubrica completa retornada por `GET /api/rubricas/:slug`. */
export interface RubricaFull {
  slug: RubricaSlug;
  nome: string;
  limite_pontuacao: number;
  infracoes: RubricaInfracao[];
  total_infracoes: number;
  contagem_por_gravidade: Record<Gravidade, number>;
}

/** Helper: parse seguro de AnalysisRow para LaudoResult + cameras_list. */
export function parseAnalysisRow(row: AnalysisRow): {
  row: AnalysisRow;
  result: LaudoResult | null;
  cameras: Camera[];
} {
  let result: LaudoResult | null = null;
  if (row.result_json) {
    try {
      result = JSON.parse(row.result_json) as LaudoResult;
    } catch {
      result = null;
    }
  }
  let cameras: Camera[] = [];
  if (row.cameras_list) {
    try {
      cameras = JSON.parse(row.cameras_list) as Camera[];
    } catch {
      cameras = [];
    }
  }
  return { row, result, cameras };
}
