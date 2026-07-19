export type InstrumentGroup = "piano" | "drum" | string;

// ── Agent Console ────────────────────────────────────────────────────────────

export type AgentAccent = "blue" | "green" | "amber" | "red" | "purple" | "cyan" | "default";

export interface TilePosition {
  col: number;
  row: number;
  col_span?: number;
  row_span?: number;
}

export type AgentConfig =
  | { type: "clock"; config?: { format?: "12h" | "24h"; show_date?: boolean; show_seconds?: boolean; timezone?: string } }
  | { type: "note"; config: { text: string } }
  | { type: "news"; config?: { source?: "hackernews" | "bbc_tech" | "techcrunch"; max_items?: number } }
  | { type: "stocks"; config: { tickers: string[]; algo?: string; period?: string } }
  | { type: "ai_query"; config: { prompt: string; system?: string; model?: string; max_tokens?: number } }
  | { type: "metric"; config: { url: string; headers?: Record<string, string>; value_path?: string; label_path?: string; unit?: string } }
  | { type: "codex_cli"; config: { prompt: string; model?: string; sandbox?: "read-only" | "workspace-write" | "danger-full-access"; writable_dir?: string; timeout_s?: number } };

export interface AgentTileConfig {
  id: string;
  zone_id?: string;
  position?: TilePosition;
  label?: string;
  accent?: AgentAccent;
  auto_refresh_s?: number;
  agent: AgentConfig;
}

export interface AgentPreset {
  version: "1";
  id: string;
  name: string;
  description?: string;
  layout: { cols: number; rows?: number };
  tiles: AgentTileConfig[];
}

export interface AgentPresetsFile {
  active: string;
  presets: AgentPreset[];
}

export type AgentData =
  | { kind: "clock"; time: string; date?: string }
  | { kind: "text"; text: string }
  | { kind: "list"; items: string[]; note?: string }
  | { kind: "stocks"; entries: { ticker: string; price: number; change_pct: number; signal?: string }[]; note?: string }
  | { kind: "metric"; value: string | number | null; unit?: string; label?: string }
  | { kind: "error"; message: string };

export interface AgentTileResult {
  tile_id: string;
  preset_id: string;
  data: AgentData;
  updated_at: number;
}

export interface AgentTileState {
  result: AgentTileResult | null;
  loading: boolean;
  error: string | null;
}

export interface Zone {
  id: string;
  label: string;
  rect: [number, number, number, number];
  action: string;
  group: InstrumentGroup;
  sound: string;
  occupancy: number;
  occupied: boolean;
}

export interface Fingertip {
  x: number;
  y: number;
}

export interface Hand {
  score: number;
  handedness: "left" | "right" | string;
  points: Fingertip[];
}

export interface SurfaceEvent {
  schema: string;
  sequence: number;
  source: string;
  kind: "control.activate" | "control.rejected" | string;
  control_id: string | null;
  value: number | string | boolean | null;
  timestamp_ms: number;
  confidence: number;
  metadata: Record<string, unknown> & {
    group?: string;
    sound?: string;
    action?: string;
    reason?: string;
    input_mode?: string;
  };
}

export interface SurfaceState {
  input_mode: string;
  activation_mode: string;
  camera: { status: string; details: Record<string, unknown> };
  bridge: { status: string };
  detector: { calibrated: boolean; ambiguous: boolean };
  candidate: string | null;
  fingertips: Fingertip[];
  hands: Hand[];
  zones: Zone[];
  buttons: { confirm: boolean; calibrate: boolean };
  last_event: SurfaceEvent | null;
  events: SurfaceEvent[];
}
