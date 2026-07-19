import type { CSSProperties } from "react";
import { ArrowRight, Drum, Fingerprint, Music2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Screen } from "@/App";
import type { SurfaceState } from "@/types";

interface Props {
  onNavigate: (screen: Screen) => void;
  state: SurfaceState | null;
}

export function HomeScreen({ onNavigate, state }: Props) {
  const pianoCount = state?.zones?.filter((z) => z.group === "piano").length ?? 6;
  const drumCount = state?.zones?.filter((z) => z.group === "drum").length ?? 4;
  const fingertips = state?.fingertips?.length ?? 0;

  const cards: {
    id: Screen;
    title: string;
    subtitle: string;
    icon: typeof Music2;
    accent: string;
    count: number;
  }[] = [
    {
      id: "piano",
      title: "Piano",
      subtitle: "Play camera-tracked keys with your fingertips",
      icon: Music2,
      accent: "var(--primary)",
      count: pianoCount,
    },
    {
      id: "drums",
      title: "Drums",
      subtitle: "Trigger pads by tapping the tracked surface",
      icon: Drum,
      accent: "oklch(0.62 0.2 20)",
      count: drumCount,
    },
  ];

  return (
    <div className="flex flex-col gap-8 py-4">
      <div className="max-w-2xl">
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-[color:var(--primary)]">
          <Fingerprint className="size-3.5" />
          MediaPipe hand tracking active · {fingertips} fingertips
        </div>
        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Turn any surface into an instrument.
        </h2>
        <p className="mt-3 text-muted-foreground">
          The Logitech C270 relays frames to the UNO Q, which tracks 21 hand
          landmarks per hand on-device with Google's MediaPipe models via LiteRT
          and emits stable{" "}
          <code className="rounded bg-secondary/60 px-1.5 py-0.5 text-xs">
            surfaceos.event.v1
          </code>{" "}
          events. Pick an instrument to begin.
        </p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <Card
              key={card.id}
              onClick={() => onNavigate(card.id)}
              className={cn(
                "group cursor-pointer overflow-hidden border-border/60 transition-all hover:-translate-y-1 hover:border-[color:var(--c)]/60"
              )}
              style={{ ["--c" as string]: card.accent } as CSSProperties}
            >
              <CardContent className="flex items-center gap-5 p-6">
                <div
                  className="grid size-16 shrink-0 place-items-center rounded-2xl border"
                  style={{
                    borderColor: `color-mix(in oklch, ${card.accent} 40%, transparent)`,
                    background: `color-mix(in oklch, ${card.accent} 12%, transparent)`,
                    color: card.accent,
                  }}
                >
                  <Icon className="size-8" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xl font-bold">{card.title}</h3>
                    <span className="rounded-full border border-border/60 px-2 py-0.5 text-[11px] text-muted-foreground">
                      {card.count} zones
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{card.subtitle}</p>
                </div>
                <ArrowRight className="size-5 text-muted-foreground transition-transform group-hover:translate-x-1" />
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
