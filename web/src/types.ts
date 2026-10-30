export type EpisodeStatus =
  | "DRAFT"
  | "TOPIC_CONFIRMED"
  | "SCRIPTING"
  | "SCRIPT_REVIEW"
  | "STORYBOARDING"
  | "VOICING"
  | "ALIGNING"
  | "RENDERING"
  | "QC"
  | "READY"
  | "PUBLISHED"
  | "CANCELLED";

export interface Series {
  id: string;
  name: string;
  voice_profile: Record<string, unknown>;
  section_labels: string[];
  character_pack_id: string;
  watermark: string;
  template_version: string;
  non_commercial: boolean;
  created_at: string;
}

export interface Episode {
  id: string;
  series_id: string;
  title: string;
  topic: string;
  target_duration_s: number;
  status: EpisodeStatus;
  health: string;
  current_node: string | null;
  output_path: string | null;
  render_spec: Record<string, unknown> | null;
  script_meta: Record<string, any> | null;
  storyboard_meta: Record<string, any> | null;
  audio_path: string | null;
  audio_meta: Record<string, any> | null;
  qc_meta: Record<string, any> | null;
  output_meta: Record<string, any> | null;
  remotion_meta: Record<string, any> | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ScriptLine {
  id: string;
  episode_id: string;
  seq: number;
  speaker: string;
  section: string;
  text: string;
  char_count: number;
  version: number;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings?: string[];
  stats?: Record<string, unknown>;
}

export interface ScriptRead {
  episode_id: string;
  status: EpisodeStatus;
  meta: Record<string, any> | null;
  lines: ScriptLine[];
  validation: ValidationResult;
}

export interface ScriptOptimizeResponse {
  episode_id: string;
  applied: boolean;
  changed_count: number;
  lines: Array<Record<string, any>>;
  validation: ValidationResult;
}

export interface ArticleImportResponse {
  episode_id: string;
  status: EpisodeStatus;
  summary: string;
  outline: Array<Record<string, any>>;
  validation: ValidationResult;
  optimized: boolean;
  optimization_error: string | null;
  lines: ScriptLine[];
}

export interface Shot {
  id: string;
  episode_id: string;
  script_line_id: string;
  seq: number;
  duration_ms: number;
  card_type: string;
  card_payload: Record<string, any>;
  character_image: string | null;
  character_position: string;
  bg: string;
  transition: string;
  cache_key: string | null;
  template_version: string;
}

export interface RhythmReport {
  valid: boolean;
  errors: string[];
  shot_count: number;
  avg_duration_ms: number;
  card_distribution: Record<string, number>;
  character_ratio: number;
  section_last_cards: Record<string, string>;
}

export interface StoryboardRead {
  episode_id: string;
  status: EpisodeStatus;
  meta: Record<string, any> | null;
  shots: Shot[];
  rhythm: RhythmReport;
}

export interface LineAudio {
  id: string;
  script_line_id: string;
  line_version: number;
  speaker: string;
  provider: string;
  model: string;
  path: string;
  duration_ms: number;
  sample_rate: number;
  checksum: string;
  created_at: string;
  seq: number | null;
}

export interface EpisodeAudioRead {
  episode_id: string;
  status: EpisodeStatus;
  audio_path: string | null;
  meta: Record<string, any> | null;
  lines: LineAudio[];
}

export interface Review {
  id: string;
  episode_id: string;
  check_item: string;
  level: "PASS" | "WARNING" | "ERROR" | "MANUAL";
  detail: Record<string, any>;
  evidence_path: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface QcReport {
  episode_id: string;
  status: EpisodeStatus;
  health: string;
  meta: Record<string, any> | null;
  reviews: Review[];
}

export interface Asset {
  id: string;
  type: string;
  name: string;
  reuse_key: string;
  path: string;
  checksum: string;
  width: number;
  height: number;
  mime: string;
  source: string;
  provider: string | null;
  model: string | null;
  prompt: string | null;
  seed: string | null;
  reference: string | null;
  tags: string[];
  meta: Record<string, any>;
  status: "CANDIDATE" | "APPROVED" | "REJECTED";
  created_at: string;
}

export interface AssetAgentItem {
  status: "reused" | "existing_candidate" | "generated";
  asset: Asset;
}

export interface AssetGenerateResponse {
  text: string;
  episode_id?: string | null;
  items: AssetAgentItem[];
  plans: Record<string, any>[];
}

export interface EpisodeActionAccepted {
  episode_id: string;
  status: EpisodeStatus;
  node_key: string;
  operation_id: string;
}


export interface RemotionShot {
  id: string;
  episode_id: string;
  shot_id: string;
  seq: number;
  composition_id: string;
  code_hash: string;
  code_path: string;
  status: string;
  error: string | null;
  attempts: number;
  prompt_hash: string | null;
  model: string | null;
  image_digest: string | null;
}

export interface RemotionEpisode {
  episode_id: string;
  status: EpisodeStatus;
  health: string;
  meta: Record<string, any> | null;
  shots: RemotionShot[];
}

export interface RemotionCode {
  shot: RemotionShot;
  code: string;
}
