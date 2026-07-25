/**
 * Live2DCanvas - React component wrapping Live2D WebGL canvas.
 * Exposes setEmotion() via ref for synchronous calls (avoids React render cycle delay).
 */

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { useLive2D } from '../hooks/useLive2D';

interface Live2DCanvasProps {
  modelPath: string;
  emotion?: string;
  intensity?: number;
  className?: string;
}

export interface Live2DCanvasHandle {
  setEmotion: (emotion: string, intensity: number) => void;
  resetEmotion: () => void;
  playMotion: (name: string, priority?: number) => boolean;
  stopAllMotions: () => void;
  startIdleMotion: () => void;
  getMotionNames: () => string[];
  /** Start lip-sync with optional audio-aligned start time (performance.now() value). */
  startLipSync: (visemes: Array<{ time_ms: number; A: number; I: number; U: number; E: number; O: number }>, durationMs: number, startTime?: number) => void;
}

export const Live2DCanvas = forwardRef<Live2DCanvasHandle, Live2DCanvasProps>(
  function Live2DCanvas(props, ref) {
    var { modelPath, emotion, intensity, className } = props;
    var canvasRef = useRef<HTMLCanvasElement>(null);
    // Retry key: incrementing triggers useLive2D's useEffect to reload the model
    var [retryKey, setRetryKey] = useState(0);
    var { state, manager } = useLive2D(canvasRef, modelPath, retryKey);

    // Expose synchronous API via ref
    useImperativeHandle(ref, function() {
      return {
        setEmotion: function(e: string, i: number) {
          manager?.emotionDriver.transitionTo(e as any, i);
        },
        resetEmotion: function() {
          manager?.emotionDriver.reset();
        },
        playMotion: function(name: string, priority?: number) {
          return manager ? manager.playMotion(name, priority ?? 1) : false;
        },
        stopAllMotions: function() {
          manager?.stopAllMotions();
        },
        startIdleMotion: function() {
          manager?.startIdleMotion();
        },
        getMotionNames: function() {
          return manager ? manager.getMotionNames() : [];
        },
        startLipSync: function(visemes: Array<{ time_ms: number; A: number; I: number; U: number; E: number; O: number }>, durationMs: number, startTime?: number) {
          manager?.startLipSync(visemes, durationMs, startTime);
        },
      };
    }, [manager]);

    // emotion — props-driven (from App state, e.g. SSE emotion events)
    useEffect(function() {
      if (emotion && manager) {
        manager.emotionDriver.transitionTo(emotion as any, intensity || 0.5);
      }
    }, [emotion, intensity, manager]);

    var isLoading = !state.loaded && !state.error;
    var handleRetry = useCallback(function() {
      setRetryKey(function(k) { return k + 1; });
    }, []);

    return (
      <div className={className} style={{ position: 'relative', width: '100%', height: '100%' }}>
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: '100%', display: state.loaded ? 'block' : 'none' }}
        />

        {/* Loading state */}
        {isLoading && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 12,
            background: 'rgba(0,0,0,0.3)', borderRadius: 16,
          }}>
            <div style={{
              width: 32, height: 32, border: '3px solid rgba(124,92,191,0.2)',
              borderTopColor: 'var(--primary)', borderRadius: '50%',
              animation: 'live2d-spin 0.8s linear infinite',
            }} />
            <span style={{ color: '#fff', fontSize: 13, opacity: 0.8 }}>模型加载中...</span>
          </div>
        )}

        {/* Error state with retry */}
        {state.error && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 10,
            background: 'rgba(0,0,0,0.6)', color: '#ef4444', fontSize: 13,
            borderRadius: 16, padding: 20, textAlign: 'center',
          }}>
            <span>⚠️ {state.error}</span>
            <button
              onClick={handleRetry}
              style={{
                padding: '6px 16px', border: '1px solid rgba(255,255,255,0.3)',
                borderRadius: 6, background: 'rgba(255,255,255,0.1)',
                color: '#fff', cursor: 'pointer', fontSize: 12,
              }}
            >
              重试
            </button>
          </div>
        )}

        <style>{`
          @keyframes live2d-spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    )
  }
);
