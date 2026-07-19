import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";

import { cn } from "@/lib/utils";
import type { AgentAccent, AgentData, AgentTileConfig, AgentTileResult } from "@/types";

// ── accent palette ─────────────────────────────────────────────────────────

const ACCENT: Record<AgentAccent, { border: string; glow: string; badge: string }> = {
  blue:    { border: "border-l-blue-500",    glow: "shadow-blue-500/10",    badge: "bg-blue-500/15 text-blue-300" },
  green:   { border: "border-l-green-500",   glow: "shadow-green-500/10",   badge: "bg-green-500/15 text-green-300" },
  amber:   { border: "border-l-amber-500",   glow: "shadow-amber-500/10",   badge: "bg-amber-500/15 text-amber-300" },
  red:     { border: "border-l-red-500",     glow: "shadow-red-500/10",     badge: "bg-red-500/15 text-red-300" },
  purple:  { border: "border-l-purple-500",  glow: "shadow-purple-500/10",  badge: "bg-purple-500/15 text-purple-300" },
  cyan:    { border: "border-l-cyan-500",    glow: "shadow-cyan-500/10",    badge: "bg-cyan-500/15 text-cyan-300" },
  default: { border: "border-l-border",      glow: "",                       badge: "bg-muted text-muted-foreground" },
};

// ── data renderers ──────────────────────────────────────────────────────────

function ClockDisplay({ data }: { data: Extract<AgentData, { kind: "clock" }> }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  const dateStr = now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

  void tick; // consumed only to trigger re-render each second
  return (
    <div className="flex flex-col items-center justify-center h-full gap-1">
      <span className="text-3xl font-mono font-bold tracking-tight tabular-nums">{timeStr}</span>
      <span className="text-xs text-muted-foreground">{dateStr}</span>
    </div>
  );
}

function TextDisplay({ data }: { data: Extract<AgentData, { kind: "text" }> }) {
  return (
    <p className="text-sm leading-relaxed text-foreground/90 overflow-auto h-full whitespace-pre-wrap">
      {data.text}
    </p>
  );
}

function ListDisplay({ data }: { data: Extract<AgentData, { kind: "list" }> }) {
  return (
    <ul className="space-y-1.5 overflow-auto h-full">
      {data.items.map((item, i) => (
        <li key={i} className="text-xs text-foreground/85 leading-snug flex gap-2">
          <span className="text-muted-foreground shrink-0 tabular-nums">{i + 1}.</span>
          <span>{item}</span>
        </li>
      ))}
      {data.note && <li className="text-[10px] text-muted-foreground/60 italic">{data.note}</li>}
    </ul>
  );
}

function StocksDisplay({ data }: { data: Extract<AgentData, { kind: "stocks" }> }) {
  return (
    <div className="flex flex-col gap-1.5 overflow-auto h-full">
      {data.entries.map((e) => (
        <div key={e.ticker} className="flex items-center justify-between gap-2 text-sm">
          <span className="font-mono font-semibold text-xs">{e.ticker}</span>
          <span className="tabular-nums font-medium">${e.price.toFixed(2)}</span>
          <span className={cn("text-xs tabular-nums font-medium", e.change_pct >= 0 ? "text-green-400" : "text-red-400")}>
            {e.change_pct >= 0 ? "+" : ""}{e.change_pct.toFixed(2)}%
          </span>
          {e.signal && <span className="text-[10px] text-muted-foreground truncate">{e.signal}</span>}
        </div>
      ))}
      {data.note && <span className="text-[10px] text-muted-foreground/60 italic">{data.note}</span>}
    </div>
  );
}

function MetricDisplay({ data }: { data: Extract<AgentData, { kind: "metric" }> }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-1">
      <span className="text-3xl font-mono font-bold tabular-nums">
        {data.value ?? "—"}
        {data.unit && <span className="text-base text-muted-foreground ml-1">{data.unit}</span>}
      </span>
      {data.label && <span className="text-xs text-muted-foreground">{data.label}</span>}
    </div>
  );
}

function ErrorDisplay({ data }: { data: Extract<AgentData, { kind: "error" }> }) {
  return (
    <p className="text-xs text-red-400 leading-relaxed">{data.message}</p>
  );
}

function DataView({ data }: { data: AgentData }) {
  if (data.kind === "clock")  return <ClockDisplay data={data} />;
  if (data.kind === "text")   return <TextDisplay data={data} />;
  if (data.kind === "list")   return <ListDisplay data={data} />;
  if (data.kind === "stocks") return <StocksDisplay data={data} />;
  if (data.kind === "metric") return <MetricDisplay data={data} />;
  if (data.kind === "error")  return <ErrorDisplay data={data} />;
  return null;
}

// ── skeleton ────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="flex flex-col gap-2 h-full animate-pulse">
      <div className="h-3 rounded bg-muted w-3/4" />
      <div className="h-3 rounded bg-muted w-1/2" />
      <div className="h-3 rounded bg-muted w-2/3" />
    </div>
  );
}

// ── tile ─────────────────────────────────────────────────────────────────────

export interface AgentTileProps {
  tile: AgentTileConfig;
  presetId: string;
  result: AgentTileResult | null;
  loading: boolean;
  onRefresh: () => void;
}

export function AgentTile({ tile, result, loading, onRefresh }: AgentTileProps) {
  const accent = ACCENT[tile.accent ?? "default"];
  const [flash, setFlash] = useState(false);
  const prevResultRef = useRef<AgentTileResult | null>(null);
  const isClockAgent = tile.agent.type === "clock";

  useEffect(() => {
    if (result && result !== prevResultRef.current) {
      prevResultRef.current = result;
      if (!isClockAgent) {
        setFlash(true);
        const t = setTimeout(() => setFlash(false), 300);
        return () => clearTimeout(t);
      }
    }
  }, [result, isClockAgent]);

  const position = tile.position;
  const gridStyle: React.CSSProperties = position
    ? {
        gridColumn: `${position.col} / span ${position.col_span ?? 1}`,
        gridRow: `${position.row} / span ${position.row_span ?? 1}`,
      }
    : {};

  const updatedAt = result?.updated_at
    ? new Date(result.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : null;

  return (
    <div
      style={gridStyle}
      className={cn(
        "flex flex-col rounded-xl border border-border border-l-4 bg-card p-4 gap-3 min-h-[160px] transition-all duration-150",
        accent.border,
        accent.glow && `shadow-lg ${accent.glow}`,
        flash && "ring-1 ring-primary/40 bg-primary/5",
      )}
    >
      {/* header */}
      <div className="flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
            {tile.label ?? tile.id}
          </span>
          {tile.zone_id && (
            <span className={cn("text-[9px] px-1.5 py-0.5 rounded font-mono", accent.badge)}>
              {tile.zone_id.replace(/_/g, " ")}
            </span>
          )}
        </div>
        {!isClockAgent && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
            title="Refresh tile"
          >
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
          </button>
        )}
      </div>

      {/* content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {loading && !result ? (
          <Skeleton />
        ) : result ? (
          <DataView data={result.data} />
        ) : (
          <div className="flex h-full items-center justify-center">
            <button
              type="button"
              onClick={onRefresh}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Click to load
            </button>
          </div>
        )}
      </div>

      {/* footer */}
      {updatedAt && !isClockAgent && (
        <p className="text-[9px] text-muted-foreground/60 shrink-0 tabular-nums">
          updated {updatedAt}
        </p>
      )}
    </div>
  );
}
