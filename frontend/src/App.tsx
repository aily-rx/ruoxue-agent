/**
 * Root application component.
 *
 * Phase 3: Live2D canvas + chat panel layout.
 */

import { useCallback, useRef, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { Live2DCanvas, type Live2DCanvasHandle } from "./components/Live2DCanvas";

const MODEL_PATH = "/live2d/mao_zh_Hans/mao_pro.model3.json";

interface Live2DData {
  emotion?: string;
  intensity?: number;
  visemes?: Array<{ time_ms: number; A: number; I: number; U: number; E: number; O: number }>;
  audioDurationMs?: number;
}

export default function App() {
  const [data, setData] = useState<Live2DData>({});
  const live2dRef = useRef<Live2DCanvasHandle>(null);

  const onUpdate = useCallback((d: Live2DData) => {
    setData((prev) => ({ ...prev, ...d }));
  }, []);

  return (
    <div id="app">
      <div id="app-layout">
        <div id="app-chat">
          <ChatPanel onLive2DUpdate={onUpdate} live2dRef={live2dRef} />
        </div>
        <div id="app-live2d">
          <Live2DCanvas
            ref={live2dRef}
            modelPath={MODEL_PATH}
            emotion={data.emotion}
            intensity={data.intensity}
            visemes={data.visemes}
            audioDurationMs={data.audioDurationMs}
          />
        </div>
      </div>

    </div>
  );
}
