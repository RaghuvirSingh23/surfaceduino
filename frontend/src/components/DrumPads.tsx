import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";
import type { Zone } from "@/types";

interface Props {
  pads: Zone[];
  onPreview: (zone: Zone) => void;
}

const PAD_ACCENT: Record<string, string> = {
  drum_kick: "var(--primary)",
  drum_snare: "oklch(0.62 0.2 20)",
  drum_hat: "oklch(0.85 0.16 90)",
  drum_tom: "oklch(0.7 0.19 320)",
};

export function DrumPads({ pads, onPreview }: Props) {
  return (
    <div className="grid h-full w-full grid-cols-2 gap-4">
      {pads.map((zone) => {
        const accent = PAD_ACCENT[zone.id] ?? "var(--primary)";
        return (
          <button
            key={zone.id}
            type="button"
            onPointerDown={() => onPreview(zone)}
            style={
              {
                "--pad": accent,
              } as CSSProperties
            }
            className={cn(
              "group relative flex select-none items-center justify-center rounded-full border-2 transition-all duration-75 active:scale-95",
              "border-[color:var(--pad)]",
              zone.occupied
                ? "scale-100 bg-[color:var(--pad)]/30 shadow-[0_0_40px_var(--pad)]"
                : "bg-[color:var(--pad)]/8 hover:bg-[color:var(--pad)]/16"
            )}
          >
            <span
              className={cn(
                "absolute inset-3 rounded-full border border-dashed opacity-30",
                "border-[color:var(--pad)]"
              )}
            />
            <div className="z-10 flex flex-col items-center">
              <span className="text-xl font-bold tracking-tight text-[color:var(--pad)]">
                {zone.label}
              </span>
              <span className="mt-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {Math.round((zone.occupancy || 0) * 100)}%
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
