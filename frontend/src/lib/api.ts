import type { AgentPresetsFile, AgentTileResult, SurfaceState } from "@/types";

export async function fetchState(signal?: AbortSignal): Promise<SurfaceState> {
  const response = await fetch("/state", { cache: "no-store", signal });
  if (!response.ok) throw new Error(`/state returned ${response.status}`);
  return (await response.json()) as SurfaceState;
}

export async function sendCommand(path: "/confirm" | "/calibrate"): Promise<void> {
  const response = await fetch(path, { method: "POST" });
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
}

export async function fetchAgentPresets(): Promise<AgentPresetsFile> {
  const response = await fetch("/api/agent-presets", { cache: "no-store" });
  if (!response.ok) throw new Error(`/api/agent-presets returned ${response.status}`);
  return (await response.json()) as AgentPresetsFile;
}

export async function runAgentTile(presetId: string, tileId: string): Promise<AgentTileResult> {
  const response = await fetch("/api/agent/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preset_id: presetId, tile_id: tileId }),
  });
  if (!response.ok) throw new Error(`/api/agent/run returned ${response.status}`);
  return (await response.json()) as AgentTileResult;
}
