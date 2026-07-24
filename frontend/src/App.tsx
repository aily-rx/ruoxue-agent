/**
 * Root application component.
 *
 * Phase 3: Live2D canvas + chat panel layout.
 */

import { useCallback, useEffect, useRef, useState } from "react";
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
  const [motionNames, setMotionNames] = useState<string[]>([]);

  const onUpdate = useCallback((d: Live2DData) => {
    setData((prev) => ({ ...prev, ...d }));
  }, []);

  useEffect(function() {
    var timer = setInterval(function() {
      var names = live2dRef.current?.getMotionNames();
      if (names && names.length > 0) { setMotionNames(names); clearInterval(timer); }
    }, 500);
    return function() { clearInterval(timer); };
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

      {motionNames.length > 0 && (
        <div style={{
          position: 'fixed', bottom: 16, left: 16, zIndex: 9999,
          background: 'rgba(30,30,40,0.92)', borderRadius: 12,
          padding: '12px 16px', maxWidth: 320,
          boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
          border: '1px solid rgba(255,255,255,0.1)',
        }}>
          <div style={{ color: '#aaa', fontSize: 12, marginBottom: 8, fontWeight: 600 }}>
            🎬 Motion Debug ({motionNames.length} loaded)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {motionNames.map(function(name) {
              return (
                <button
                  key={name}
                  onClick={function() { live2dRef.current?.playMotion(name, 2); }}
                  style={{
                    background: 'rgba(124,92,191,0.3)', color: '#ddd',
                    border: '1px solid rgba(124,92,191,0.5)', borderRadius: 6,
                    padding: '4px 10px', fontSize: 12, cursor: 'pointer',
                  }}
                >
                  {name.replace('mtn_', '动作').replace('special_', '特殊')}
                </button>
              );
            })}
          </div>
          <button
            onClick={function() { live2dRef.current?.resetEmotion(); }}
            style={{
              marginTop: 8, width: '100%',
              background: 'rgba(255,255,255,0.08)', color: '#aaa',
              border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6,
              padding: '4px 10px', fontSize: 12, cursor: 'pointer',
            }}
          >
            ↺ Reset
          </button>
        </div>
      )}
    </div>
  );
}
