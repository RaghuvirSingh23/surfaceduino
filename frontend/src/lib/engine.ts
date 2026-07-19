/**
 * Engine mode singleton — tracks whether we're routing API calls to
 * the Arduino UNO Q (port 17000 via ADB tunnel, proxied by vite/the
 * built app) or to the local engine running on this Mac (port 7001,
 * fetched directly with CORS).
 *
 * Persisted to localStorage so the toggle survives page reloads.
 */

export type EngineMode = "arduino" | "local";

const LOCAL_ENGINE_URL = "http://127.0.0.1:7001";
const STORAGE_KEY      = "surfaceos.engine";

let _mode: EngineMode =
  (typeof localStorage !== "undefined"
    ? (localStorage.getItem(STORAGE_KEY) as EngineMode | null)
    : null) ?? "arduino";

const _listeners = new Set<() => void>();

export function getEngineMode(): EngineMode {
  return _mode;
}

/** Returns "" in arduino mode (uses existing proxy) or the local engine URL. */
export function getBaseUrl(): string {
  return _mode === "local" ? LOCAL_ENGINE_URL : "";
}

export function setEngineMode(mode: EngineMode): void {
  if (_mode === mode) return;
  _mode = mode;
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(STORAGE_KEY, mode);
  }
  _listeners.forEach((fn) => fn());
}

export function toggleEngineMode(): void {
  setEngineMode(_mode === "arduino" ? "local" : "arduino");
}

/** Subscribe to mode changes. Returns an unsubscribe function. */
export function subscribeEngineMode(fn: () => void): () => void {
  _listeners.add(fn);
  return () => _listeners.delete(fn);
}
