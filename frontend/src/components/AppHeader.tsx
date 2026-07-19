import { Cpu, Drum, Home, LayoutGrid, Laptop, Music2, Volume2, VolumeX } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatusPills } from "@/components/StatusPills";
import { useEngineMode } from "@/hooks/useEngineMode";
import { cn } from "@/lib/utils";
import type { Screen } from "@/App";
import type { SurfaceState } from "@/types";

interface Props {
  screen: Screen;
  onNavigate: (screen: Screen) => void;
  soundEnabled: boolean;
  onEnableSound: () => void;
  state: SurfaceState | null;
  connected: boolean;
}

const NAV: { id: Screen; label: string; icon: typeof Home }[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "piano", label: "Piano", icon: Music2 },
  { id: "drums", label: "Drums", icon: Drum },
  { id: "console", label: "Console", icon: LayoutGrid },
];

export function AppHeader({
  screen,
  onNavigate,
  soundEnabled,
  onEnableSound,
  state,
  connected,
}: Props) {
  const { mode, isLocal, toggle } = useEngineMode();

  return (
    <header className="flex flex-col gap-4 border-b border-border/60 pb-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => onNavigate("home")}
          className="flex items-center gap-3 text-left"
        >
          <div className="grid size-10 place-items-center rounded-xl border border-primary/30 bg-primary/10 text-lg">
            🔲
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">
              Arduino UNO Q · on-device
            </p>
            <h1 className="text-2xl font-bold tracking-tight">
              Surface<span className="text-[color:var(--primary)]">OS</span>
            </h1>
          </div>
        </button>

        <StatusPills state={state} connected={connected} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav className="flex items-center gap-1 rounded-xl border border-border/60 bg-card/50 p-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = screen === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground shadow"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          {/* Engine mode toggle */}
          <button
            type="button"
            onClick={toggle}
            title={isLocal ? "Running locally — click to switch to Arduino" : "Running on Arduino — click to switch to local Mac engine"}
            className={cn(
              "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-all duration-200",
              isLocal
                ? "border-green-500/50 bg-green-500/10 text-green-400 hover:bg-green-500/15"
                : "border-border bg-card/50 text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            {isLocal ? (
              <>
                <span className="relative flex size-2">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex size-2 rounded-full bg-green-500" />
                </span>
                <Laptop className="size-3.5" />
                Local
              </>
            ) : (
              <>
                <Cpu className="size-3.5" />
                Arduino
              </>
            )}
          </button>

          <Button
            variant={soundEnabled ? "outline" : "default"}
            onClick={onEnableSound}
            className={cn(soundEnabled && "border-success/50 text-[color:var(--success)]")}
          >
            {soundEnabled ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
            {soundEnabled ? "Sound on" : "Enable sound"}
          </Button>
        </div>
      </div>
    </header>
  );
}
