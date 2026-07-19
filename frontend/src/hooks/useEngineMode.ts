import { useEffect, useState } from "react";
import {
  getBaseUrl,
  getEngineMode,
  subscribeEngineMode,
  toggleEngineMode,
  type EngineMode,
} from "@/lib/engine";

export type { EngineMode };

export function useEngineMode() {
  const [mode, setMode] = useState<EngineMode>(getEngineMode);

  useEffect(() => subscribeEngineMode(() => setMode(getEngineMode())), []);

  return {
    mode,
    baseUrl: getBaseUrl(),
    isLocal: mode === "local",
    toggle: toggleEngineMode,
  };
}
