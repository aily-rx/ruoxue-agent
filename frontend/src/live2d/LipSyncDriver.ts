/**
 * LipSyncDriver — viseme timeline to 5-parameter mouth shape.
 *
 * Drives ParamA (open), ParamI (spread), ParamU (round),
 * ParamE (half-open), ParamO (round-open) simultaneously for
 * natural Chinese phoneme lip-sync on mao_pro model.
 */

import { CubismModel } from './sdk/model/cubismmodel';
import { CubismFramework } from './sdk/live2dcubismframework';

interface VisemeFrame { time_ms: number; A: number; I: number; U: number; E: number; O: number; }

export class LipSyncDriver {
  private _model: CubismModel | null = null;
  private _timeline: VisemeFrame[] = [];
  private _startTime: number = 0;
  private _durationMs: number = 0;
  private _active: boolean = false;
  private _ids: Record<string, any> = {};
  private _prevFrame: VisemeFrame | null = null;
  // EMA smoothing: track current smoothed value for each parameter
  private _smooth: Record<string, number> = {};

  attach(model: CubismModel): void {
    this._model = model;
    var idm = CubismFramework.getIdManager();
    this._ids = {
      A: idm.getId('ParamA'),
      I: idm.getId('ParamI'),
      U: idm.getId('ParamU'),
      E: idm.getId('ParamE'),
      O: idm.getId('ParamO'),
    };
  }
  detach(): void { this.stop(); this._model = null; this._ids = {}; }
  get isActive(): boolean { return this._active; }

  start(timeline: VisemeFrame[], durationMs: number, startTime?: number): void {
    this._timeline = timeline;
    this._durationMs = durationMs || 3000;
    // Use provided startTime (performance.now() captured at audio playback start),
    // otherwise fall back to current time (backward compat for non-audio-driven calls).
    this._startTime = startTime ?? performance.now();
    this._active = true;
    this._prevFrame = null;
    this._smooth = {};  // reset smoothing
  }

  stop(): void {
    this._active = false;
    this._timeline = [];
    this._prevFrame = null;
    // Close mouth
    for (var k in this._ids) {
      try { this._model?.setParameterValueById(this._ids[k], 0); } catch (_) {}
    }
  }

  update(now: number): void {
    if (!this._active || !this._model || this._timeline.length === 0) return;
    var el = now - this._startTime;
    if (el > this._durationMs) { this.stop(); return; }

    // Find current frame by binary search on timeline
    var lo = 0, hi = this._timeline.length - 1;
    while (lo < hi) {
      var mid = Math.ceil((lo + hi) / 2);
      if (this._timeline[mid].time_ms <= el) lo = mid;
      else hi = mid - 1;
    }
    var f = this._timeline[lo];

    // Interpolate between keyframes for target value
    var prev = this._prevFrame || f;
    var prevT = prev.time_ms;
    var nextT = f.time_ms;
    var blend = nextT > prevT ? (el - prevT) / (nextT - prevT) : 0;
    blend = Math.max(0, Math.min(1, blend));

    // EMA smoothing: gradual approach toward target to avoid jitter
    var SMOOTH = 0.2;  // lower = smoother/slower, higher = snappier

    for (var k in this._ids) {
      var target = (prev[k as keyof VisemeFrame] as number)
        + ((f[k as keyof VisemeFrame] as number) - (prev[k as keyof VisemeFrame] as number)) * blend;
      var cur = this._smooth[k] !== undefined ? this._smooth[k] : target;
      var smoothed = cur + (target - cur) * SMOOTH;
      this._smooth[k] = smoothed;
      try { this._model.setParameterValueById(this._ids[k], smoothed); } catch (_) {}
    }

    this._prevFrame = f;
  }
}
