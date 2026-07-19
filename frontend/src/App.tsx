import { useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/AppHeader";
import { AgentConsoleScreen } from "@/screens/AgentConsoleScreen";
import { HomeScreen } from "@/screens/HomeScreen";
import { InstrumentScreen } from "@/screens/InstrumentScreen";
import { useEventAudio } from "@/hooks/useEventAudio";
import { useSurfaceState } from "@/hooks/useSurfaceState";
import { sendCommand } from "@/lib/api";
import { audioEngine } from "@/lib/audio";
import type { Zone } from "@/types";

export type Screen = "home" | "piano" | "drums" | "console";

const SCREENS: Screen[] = ["home", "piano", "drums", "console"];

function screenFromHash(): Screen {
  const hash = window.location.hash.replace("#/", "").replace("#", "");
  return (SCREENS as string[]).includes(hash) ? (hash as Screen) : "home";
}

export default function App() {
  const { state, connected } = useSurfaceState();
  const [screen, setScreen] = useState<Screen>(screenFromHash);
  const [soundEnabled, setSoundEnabled] = useState(false);

  const activeGroup = screen === "drums" ? "drum" : "piano";
  useEventAudio(state?.events ?? [], activeGroup);

  useEffect(() => {
    const onHashChange = () => setScreen(screenFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = useCallback((next: Screen) => {
    setScreen(next);
    window.location.hash = next === "home" ? "" : `/${next}`;
  }, []);

  const enableSound = useCallback(async () => {
    await audioEngine.enable();
    setSoundEnabled(audioEngine.enabled);
  }, []);

  const previewZone = useCallback(
    async (zone: Zone) => {
      await enableSound();
      audioEngine.play(zone.group, zone.sound);
    },
    [enableSound]
  );

  const calibrate = useCallback(() => {
    void sendCommand("/calibrate");
  }, []);

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-4 py-6 sm:px-6">
      <AppHeader
        screen={screen}
        onNavigate={navigate}
        soundEnabled={soundEnabled}
        onEnableSound={enableSound}
        state={state}
        connected={connected}
      />

      <main className="flex-1">
        {screen === "home" && <HomeScreen onNavigate={navigate} state={state} />}
        {screen === "piano" && (
          <InstrumentScreen
            group="piano"
            state={state}
            onPreview={previewZone}
            onCalibrate={calibrate}
          />
        )}
        {screen === "drums" && (
          <InstrumentScreen
            group="drum"
            state={state}
            onPreview={previewZone}
            onCalibrate={calibrate}
          />
        )}
        {screen === "console" && <AgentConsoleScreen events={state?.events ?? []} />}
      </main>

      <footer className="mt-8 border-t border-border/60 pt-4 text-center text-xs text-muted-foreground">
        SurfaceOS · fingertip vision + surfaceos.event.v1 · running on Arduino UNO Q
      </footer>
    </div>
  );
}
