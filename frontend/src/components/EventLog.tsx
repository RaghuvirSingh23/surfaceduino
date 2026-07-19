import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { SurfaceEvent } from "@/types";

interface Props {
  events: SurfaceEvent[];
  group: string;
}

function matchesGroup(event: SurfaceEvent, group: string): boolean {
  const eventGroup =
    event.metadata?.group ||
    (event.control_id?.startsWith("piano_")
      ? "piano"
      : event.control_id?.startsWith("drum_")
        ? "drum"
        : "control");
  return eventGroup === group || event.kind === "control.rejected";
}

export function EventLog({ events, group }: Props) {
  const filtered = events.filter((event) => matchesGroup(event, group)).slice(0, 10);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
          Event bus · surfaceos.event.v1
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        {filtered.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Waiting for an activation…
          </p>
        )}
        {filtered.map((event) => {
          const accepted = event.kind === "control.activate";
          return (
            <div
              key={event.sequence}
              className="flex items-center justify-between gap-3 border-b border-border/60 py-2 text-sm last:border-0"
            >
              <span
                className={cn(
                  "w-16 shrink-0 text-[11px] font-bold uppercase tracking-wider",
                  accepted ? "text-[color:var(--success)]" : "text-[color:var(--destructive)]"
                )}
              >
                {accepted ? "play" : "reject"}
              </span>
              <span className="flex-1 truncate font-medium">
                {accepted
                  ? (event.metadata?.sound as string) ?? event.control_id
                  : (event.metadata?.reason as string) ?? "no selection"}
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">{event.source}</span>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
