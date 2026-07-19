import { useEffect, useRef } from "react";

import { audioEngine } from "@/lib/audio";
import type { InstrumentGroup, SurfaceEvent } from "@/types";

function groupOf(event: SurfaceEvent): string {
  if (event.metadata?.group) return event.metadata.group;
  if (event.control_id?.startsWith("piano_")) return "piano";
  if (event.control_id?.startsWith("drum_")) return "drum";
  return "control";
}

function soundOf(event: SurfaceEvent): string {
  if (event.metadata?.sound) return event.metadata.sound;
  return (event.control_id ?? "")
    .replace("piano_", "")
    .replace("drum_", "");
}

/**
 * Plays newly-arrived activation events that belong to the active instrument.
 * Sequence numbers are global and monotonic, so the high-water mark advances
 * across every event; switching screens never replays already-consumed audio.
 */
export function useEventAudio(events: SurfaceEvent[], activeGroup: InstrumentGroup) {
  const lastSequence = useRef<number | null>(null);

  useEffect(() => {
    const sequences = events
      .map((event) => event.sequence)
      .filter((value) => Number.isFinite(value));
    if (lastSequence.current === null) {
      lastSequence.current = sequences.length ? Math.max(...sequences) : 0;
      return;
    }

    const previous = lastSequence.current;
    events
      .filter(
        (event) =>
          event.sequence > previous &&
          event.kind === "control.activate" &&
          groupOf(event) === activeGroup
      )
      .sort((a, b) => a.sequence - b.sequence)
      .forEach((event) => audioEngine.play(groupOf(event), soundOf(event)));

    if (sequences.length) {
      lastSequence.current = Math.max(previous, ...sequences);
    }
  }, [events, activeGroup]);
}
