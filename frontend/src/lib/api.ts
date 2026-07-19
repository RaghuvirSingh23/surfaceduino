import type { SurfaceState } from "@/types";

export async function fetchState(signal?: AbortSignal): Promise<SurfaceState> {
  const response = await fetch("/state", { cache: "no-store", signal });
  if (!response.ok) throw new Error(`/state returned ${response.status}`);
  return (await response.json()) as SurfaceState;
}

export async function sendCommand(path: "/confirm" | "/calibrate"): Promise<void> {
  const response = await fetch(path, { method: "POST" });
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
}
