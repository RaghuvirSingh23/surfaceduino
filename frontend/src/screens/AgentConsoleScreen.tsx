import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import { AgentTile } from "@/components/AgentTile";
import { fetchAgentPresets, runAgentTile } from "@/lib/api";
import type { AgentPreset, AgentPresetsFile, AgentTileResult, AgentTileState, SurfaceEvent } from "@/types";

// ── hook: manage tile state for the active preset ──────────────────────────

function useAgentConsole(preset: AgentPreset | null) {
  const [states, setStates] = useState<Record<string, AgentTileState>>({});
  const intervalsRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const setTile = useCallback((tileId: string, patch: Partial<AgentTileState>) => {
    setStates((prev) => ({
      ...prev,
      [tileId]: { result: null, loading: false, error: null, ...prev[tileId], ...patch },
    }));
  }, []);

  const refresh = useCallback(
    async (presetId: string, tileId: string) => {
      setTile(tileId, { loading: true, error: null });
      try {
        const result = await runAgentTile(presetId, tileId);
        setTile(tileId, { result, loading: false });
      } catch (e) {
        setTile(tileId, { loading: false, error: String(e) });
      }
    },
    [setTile],
  );

  // Reset state and start auto-refresh whenever the preset changes.
  useEffect(() => {
    if (!preset) return;

    // Clear old intervals.
    Object.values(intervalsRef.current).forEach(clearInterval);
    intervalsRef.current = {};
    setStates({});

    // Load non-clock tiles immediately; schedule auto-refresh.
    for (const tile of preset.tiles) {
      if (tile.agent.type === "clock") continue;
      void refresh(preset.id, tile.id);
      if (tile.auto_refresh_s) {
        intervalsRef.current[tile.id] = setInterval(
          () => void refresh(preset.id, tile.id),
          tile.auto_refresh_s * 1000,
        );
      }
    }

    return () => {
      Object.values(intervalsRef.current).forEach(clearInterval);
      intervalsRef.current = {};
    };
  }, [preset?.id]);  // eslint-disable-line react-hooks/exhaustive-deps

  return { states, refresh };
}

// ── component ──────────────────────────────────────────────────────────────

interface Props {
  events: SurfaceEvent[];
}

export function AgentConsoleScreen({ events }: Props) {
  const [presetsFile, setPresetsFile] = useState<AgentPresetsFile | null>(null);
  const [activeId, setActiveId] = useState<string>("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const lastEventSeqRef = useRef<number | null>(null);

  // Load presets once.
  useEffect(() => {
    fetchAgentPresets()
      .then((file) => {
        setPresetsFile(file);
        setActiveId(file.active || file.presets[0]?.id || "");
      })
      .catch((e) => setLoadError(String(e)));
  }, []);

  const preset = presetsFile?.presets.find((p) => p.id === activeId) ?? null;
  const { states, refresh } = useAgentConsole(preset);

  // Build a zone→tile lookup for the active preset.
  const zoneTileMap = new Map<string, string>();
  if (preset) {
    for (const tile of preset.tiles) {
      if (tile.zone_id) zoneTileMap.set(tile.zone_id, tile.id);
    }
  }

  // Watch surface events and refresh the matching tile when a zone is tapped.
  useEffect(() => {
    if (!preset || events.length === 0) return;
    const seqs = events.map((e) => e.sequence).filter(Number.isFinite);
    if (lastEventSeqRef.current === null) {
      lastEventSeqRef.current = seqs.length ? Math.max(...seqs) : 0;
      return;
    }
    const prev = lastEventSeqRef.current;
    events
      .filter((e) => e.sequence > prev && e.kind === "control.activate" && e.control_id)
      .sort((a, b) => a.sequence - b.sequence)
      .forEach((e) => {
        const tileId = zoneTileMap.get(e.control_id!);
        if (tileId) void refresh(preset.id, tileId);
      });
    if (seqs.length) lastEventSeqRef.current = Math.max(prev, ...seqs);
  }, [events, preset]);

  // ── render ──

  if (loadError) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        Failed to load agent presets: {loadError}
      </div>
    );
  }

  if (!presetsFile) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground animate-pulse">
        Loading agent presets…
      </div>
    );
  }

  const cols = preset?.layout.cols ?? 3;

  return (
    <div className="flex flex-col gap-5 py-4">
      {/* toolbar */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
            Agent Console
          </p>
          <h2 className="text-2xl font-bold tracking-tight">{preset?.name ?? "No preset"}</h2>
          {preset?.description && (
            <p className="text-sm text-muted-foreground mt-0.5">{preset.description}</p>
          )}
        </div>

        {/* preset selector */}
        <div className="relative shrink-0">
          <select
            value={activeId}
            onChange={(e) => setActiveId(e.target.value)}
            className="appearance-none bg-card border border-border rounded-lg px-3 py-2 pr-8 text-sm font-medium cursor-pointer focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {presetsFile.presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
        </div>
      </div>

      {/* zone binding hint */}
      {zoneTileMap.size > 0 && (
        <p className="text-xs text-muted-foreground -mt-2">
          {zoneTileMap.size} tile{zoneTileMap.size !== 1 ? "s" : ""} bound to physical surface zones — tap a zone to refresh its tile.
        </p>
      )}

      {/* grid */}
      {preset ? (
        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
        >
          {preset.tiles.map((tile) => {
            const s = states[tile.id] ?? { result: null, loading: false, error: null };
            return (
              <AgentTile
                key={tile.id}
                tile={tile}
                presetId={preset.id}
                result={s.result}
                loading={s.loading}
                onRefresh={() => void refresh(preset.id, tile.id)}
              />
            );
          })}
        </div>
      ) : (
        <div className="py-12 text-center text-sm text-muted-foreground">
          No preset selected. Edit <code className="font-mono">config/agent_presets.json</code> to add one.
        </div>
      )}

      {/* edit hint */}
      <p className="text-[11px] text-muted-foreground/50 text-center">
        Edit <code className="font-mono">config/agent_presets.json</code> to add tiles · set{" "}
        <code className="font-mono">ANTHROPIC_API_KEY</code> for AI tiles
      </p>
    </div>
  );
}
