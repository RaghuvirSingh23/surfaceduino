import { Activity, Camera, Cpu, Wifi, WifiOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { SurfaceState } from "@/types";

interface Props {
  state: SurfaceState | null;
  connected: boolean;
}

export function StatusPills({ state, connected }: Props) {
  if (!connected || !state) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="warning">
          <WifiOff className="size-3" /> board offline
        </Badge>
      </div>
    );
  }

  const cameraReady = ["connected", "streaming"].includes(state.camera.status);
  const bridgeReady = state.bridge.status === "ready";
  const directMode = state.input_mode === "direct_buttons";
  const calibrated = directMode || state.detector.calibrated;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant={connected ? "ready" : "warning"}>
        <Wifi className="size-3" /> live
      </Badge>
      <Badge variant={cameraReady ? "ready" : "default"}>
        <Camera className="size-3" /> {state.camera.status}
      </Badge>
      <Badge variant={bridgeReady ? "ready" : "default"}>
        <Cpu className="size-3" /> {state.bridge.status}
      </Badge>
      <Badge variant={calibrated ? "ready" : "warning"}>
        <Activity className="size-3" />
        {directMode ? "direct buttons" : calibrated ? "surface live" : "uncalibrated"}
      </Badge>
    </div>
  );
}
