import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DrumPads } from "@/components/DrumPads";
import { EventLog } from "@/components/EventLog";
import { PianoKeyboard } from "@/components/PianoKeyboard";
import { VideoFeed } from "@/components/VideoFeed";
import type { SurfaceState, Zone } from "@/types";

interface Props {
  group: "piano" | "drum";
  state: SurfaceState | null;
  onPreview: (zone: Zone) => void;
  onCalibrate: () => void;
}

const COPY = {
  piano: {
    title: "Piano",
    hint: "Rest your hand on the surface and press a key with a single fingertip.",
  },
  drum: {
    title: "Drums",
    hint: "Tap a pad zone with a fingertip to trigger the drum voice.",
  },
} as const;

export function InstrumentScreen({ group, state, onPreview, onCalibrate }: Props) {
  const zones = (state?.zones ?? []).filter((zone) => zone.group === group);
  const fingertipCount = state?.fingertips?.length ?? 0;
  const handCount = state?.hands?.length ?? 0;
  const activeLabels = zones.filter((zone) => zone.occupied).map((zone) => zone.label);
  const directMode = state?.input_mode === "direct_buttons";
  const copy = COPY[group];

  return (
    <div className="grid gap-5 py-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="flex flex-col gap-5">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
              Live surface
            </p>
            <h2 className="text-2xl font-bold tracking-tight">
              {activeLabels.length ? `Playing · ${activeLabels.join(" + ")}` : copy.title}
            </h2>
          </div>
          <Button variant="outline" onClick={onCalibrate}>
            <RefreshCw className="size-4" />
            Capture background
          </Button>
        </div>

        <VideoFeed fingertipCount={fingertipCount} handCount={handCount} />

        <p className="text-sm text-muted-foreground">
          {directMode
            ? "Camera offline — D2 tests C4, D3 tests kick. Reconnect the Mac relay to resume tracking."
            : copy.hint}
        </p>
      </div>

      <div className="flex flex-col gap-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
              {copy.title} · tap to preview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-56">
              {group === "piano" ? (
                <PianoKeyboard keys={zones} onPreview={onPreview} />
              ) : (
                <DrumPads pads={zones} onPreview={onPreview} />
              )}
            </div>
          </CardContent>
        </Card>

        <EventLog events={state?.events ?? []} group={group} />
      </div>
    </div>
  );
}
