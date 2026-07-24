/**
 * Live2DCanvas - React component wrapping Live2D WebGL canvas.
 * Exposes setEmotion() via ref for synchronous calls (avoids React render cycle delay).
 */

import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { useLive2D } from '../hooks/useLive2D';

interface Live2DCanvasProps {
  modelPath: string;
  emotion?: string;
  intensity?: number;
  visemes?: Array<{ time_ms: number; A: number; I: number; U: number; E: number; O: number }>;
  audioDurationMs?: number;
  className?: string;
}

export interface Live2DCanvasHandle {
  setEmotion: (emotion: string, intensity: number) => void;
  resetEmotion: () => void;
  playMotion: (name: string, priority?: number) => boolean;
  stopAllMotions: () => void;
  startIdleMotion: () => void;
  getMotionNames: () => string[];
}

export const Live2DCanvas = forwardRef<Live2DCanvasHandle, Live2DCanvasProps>(
  function Live2DCanvas(props, ref) {
    var { modelPath, emotion, intensity, visemes, audioDurationMs, className } = props;
    var canvasRef = useRef<HTMLCanvasElement>(null);
    var { state, manager } = useLive2D(canvasRef, modelPath);

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
      };
    }, [manager]);

    // emotion — props-driven (from App state, e.g. SSE emotion events)
    useEffect(function() {
      if (emotion && manager) {
        manager.emotionDriver.transitionTo(emotion as any, intensity || 0.5);
      }
    }, [emotion, intensity, manager]);

    // viseme
    useEffect(function() {
      if (visemes && visemes.length > 0 && manager) {
        manager.startLipSync(visemes, audioDurationMs || 3000);
      }
    }, [visemes, audioDurationMs, manager]);

    return (
      <div className={className} style={{ position: 'relative', width: '100%', height: '100%' }}>
        <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
        {state.error && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.5)', color: '#ef4444', fontSize: 14, borderRadius: 16,
          }}>
            {state.error}
          </div>
        )}
      </div>
    )
  }
);
