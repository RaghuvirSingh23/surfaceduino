export type InstrumentGroup = "piano" | "drum" | string;

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
