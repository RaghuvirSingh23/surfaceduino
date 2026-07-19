import { useEffect, useRef, useState } from "react";

import { fetchState } from "@/lib/api";
import { getEngineMode, subscribeEngineMode } from "@/lib/engine";
import type { SurfaceState } from "@/types";

const POLL_INTERVAL_MS = 80;

/**
 * Guarantee the array fields exist even if the board runs an older app
 * revision that omits them (e.g. no `fingertips` before fingertip tracking).
 * Keeps the UI from crashing on a partial payload.
 */
function normalize(raw: SurfaceState): SurfaceState {
  return {
    ...raw,
    zones: Array.isArray(raw.zones) ? raw.zones : [],
    fingertips: Array.isArray(raw.fingertips) ? raw.fingertips : [],
    hands: Array.isArray(raw.hands) ? raw.hands : [],
    events: Array.isArray(raw.events) ? raw.events : [],
  };
}

export function useSurfaceState() {
  const [state, setState] = useState<SurfaceState | null>(null);
  const [connected, setConnected] = useState(false);
  const [engineMode, setEngineMode] = useState(getEngineMode);
  const timer = useRef<number | undefined>(undefined);

  // Re-render (and restart the poll loop) whenever engine mode toggles.
  useEffect(() => subscribeEngineMode(() => {
    setState(null);
    setConnected(false);
    setEngineMode(getEngineMode());
  }), []);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    const poll = async () => {
      try {
        const next = await fetchState(controller.signal);
        if (cancelled) return;
        setState(normalize(next));
        setConnected(true);
      } catch {
        if (!cancelled) setConnected(false);
      } finally {
        if (!cancelled) {
          timer.current = window.setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    };

    poll();
    return () => {
      cancelled = true;
      controller.abort();
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [engineMode]); // restart loop when backend switches

  return { state, connected };
}
