import { cn } from "@/lib/utils";
import type { Zone } from "@/types";

interface Props {
  keys: Zone[];
  onPreview: (zone: Zone) => void;
}

export function PianoKeyboard({ keys, onPreview }: Props) {
  return (
    <div className="flex h-full w-full gap-2">
      {keys.map((zone) => (
        <button
          key={zone.id}
          type="button"
          onPointerDown={() => onPreview(zone)}
          className={cn(
            "relative flex flex-1 select-none flex-col items-center justify-end rounded-b-xl rounded-t-sm border pb-4 pt-8 transition-all duration-75",
            "bg-gradient-to-b from-zinc-100 to-zinc-300 text-zinc-800 shadow-lg shadow-black/40 active:translate-y-0.5",
            zone.occupied
              ? "-translate-y-0 border-[color:var(--success)] from-emerald-200 to-emerald-400 text-emerald-950 shadow-[0_0_28px_var(--success)]"
              : "border-zinc-400/60 hover:from-white hover:to-zinc-200"
          )}
        >
          <span className="text-lg font-bold tracking-tight">{zone.label}</span>
          <span className="mt-1 text-[10px] font-medium uppercase tracking-wider opacity-60">
            {Math.round((zone.occupancy || 0) * 100)}%
          </span>
        </button>
      ))}
    </div>
  );
}
