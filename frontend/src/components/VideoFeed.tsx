import { useRef, useState } from "react";
import { Fingerprint, Hand, Maximize2, Minimize2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useEngineMode } from "@/hooks/useEngineMode";

interface Props {
  fingertipCount: number;
  handCount?: number;
}

export function VideoFeed({ fingertipCount, handCount = 0 }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const { baseUrl } = useEngineMode();

  const toggleFullscreen = async () => {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      setIsFullscreen(false);
    } else if (wrapRef.current) {
      await wrapRef.current.requestFullscreen();
      setIsFullscreen(true);
    }
  };

  return (
    <div
      ref={wrapRef}
      className="group relative aspect-[4/3] w-full overflow-hidden rounded-xl border border-border bg-black"
    >
      <img
        key={baseUrl}
        src={`${baseUrl}/stream`}
        alt="Live surface with fingertip tracking overlay"
        className="size-full object-contain"
      />
      <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2">
        <span className="flex items-center gap-1.5 rounded-full border border-primary/30 bg-black/60 px-2.5 py-1 text-xs font-medium text-[color:var(--primary)] backdrop-blur">
          <Hand className="size-3.5" />
          {handCount} hand{handCount === 1 ? "" : "s"}
        </span>
        <span className="flex items-center gap-1.5 rounded-full border border-primary/30 bg-black/60 px-2.5 py-1 text-xs font-medium text-[color:var(--primary)] backdrop-blur">
          <Fingerprint className="size-3.5" />
          {fingertipCount} fingertip{fingertipCount === 1 ? "" : "s"}
        </span>
      </div>
      <div className="absolute right-3 top-3">
        <Button size="icon" variant="outline" onClick={toggleFullscreen}>
          {isFullscreen ? (
            <Minimize2 className="size-4" />
          ) : (
            <Maximize2 className="size-4" />
          )}
        </Button>
      </div>
    </div>
  );
}
