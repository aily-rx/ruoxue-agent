/**
 * useLive2D - React hook for Live2D model lifecycle.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { CubismManager, Live2DState } from '../live2d/CubismManager';

export function useLive2D(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  modelPath: string,
  retryKey?: number,
) {
  var ref = useRef<CubismManager | null>(null);
  var ref2 = useRef(modelPath);
  ref2.current = modelPath;
  var [state, setState] = useState<Live2DState>({ loaded: false, error: null });

  useEffect(function() {
    var canvas = canvasRef.current;
    if (!canvas || !ref2.current) return;
    var cancelled = false;
    var mgr = new CubismManager(canvas);
    ref.current = mgr;
    mgr.onStateChange = function(s: Live2DState) { if (!cancelled) setState(s); };
    mgr.loadModelFromUrl(ref2.current).catch(function(err: Error) {
      if (!cancelled) setState({ loaded: false, error: err.message });
    });
    return function() { cancelled = true; mgr.dispose(); ref.current = null; };
  }, [canvasRef, retryKey]);

  return { state, manager: ref.current };
}
