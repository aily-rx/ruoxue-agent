/**
 * IdleMotionDriver — natural random idle motion for Live2D model.
 *
 * Uses random-walk targets + smooth lerp interpolation instead of
 * mechanical sine waves. Each parameter independently picks a random
 * target every few seconds and smoothly transitions to it.
 */

import { CubismModel } from './sdk/model/cubismmodel';
import { CubismFramework } from './sdk/live2dcubismframework';

interface MotionParam {
  id: any;              // CubismIdHandle
  min: number;          // minimum value
  max: number;          // maximum value
  speed: number;        // lerp speed per second (higher = faster)
  interval: number;     // seconds between target changes (will be randomized ±50%)
}

export class IdleMotionDriver {
  private _model: CubismModel | null = null;
  private _params: MotionParam[] = [];
  private _states: Array<{ current: number; target: number; nextChange: number }> = [];
  private _time = 0;

  attach(model: CubismModel): void {
    this._model = model;
    var idm = CubismFramework.getIdManager();

    // Define which parameters to animate with natural random motion
    this._params = [
      { id: idm.getId('ParamAngleX'),  min: -2.0, max: 2.0,  speed: 0.3, interval: 3.0 },
      { id: idm.getId('ParamAngleY'),  min: -1.5, max: 1.5,  speed: 0.4, interval: 2.5 },
      { id: idm.getId('ParamAngleZ'),  min: -1.0, max: 1.0,  speed: 0.5, interval: 2.0 },
      { id: idm.getId('ParamBodyAngleX'), min: -3.0, max: 3.0, speed: 0.2, interval: 4.0 },
      { id: idm.getId('ParamBodyAngleY'), min: -2.0, max: 2.0, speed: 0.25, interval: 3.5 },
    ];

    // Initialize random states
    this._states = [];
    this._time = 0;
    for (var i = 0; i < this._params.length; i++) {
      this._states.push({
        current: 0,
        target: this._randomTarget(this._params[i]),
        nextChange: this._randomInterval(this._params[i]),
      });
    }
  }

  detach(): void {
    this._model = null;
    this._params = [];
    this._states = [];
  }

  update(deltaSeconds: number): void {
    if (!this._model || this._params.length === 0) return;
    this._time += deltaSeconds;

    for (var i = 0; i < this._params.length; i++) {
      var p = this._params[i];
      var s = this._states[i];

      // Time to pick a new random target?
      if (this._time >= s.nextChange) {
        s.target = this._randomTarget(p);
        s.nextChange = this._time + this._randomInterval(p);
      }

      // Smooth lerp toward target
      var t = Math.min(p.speed * deltaSeconds, 1.0);
      s.current = s.current + (s.target - s.current) * t;

      // Apply to model
      this._model.setParameterValueById(p.id, s.current);
    }
  }

  private _randomTarget(p: MotionParam): number {
    return p.min + Math.random() * (p.max - p.min);
  }

  private _randomInterval(p: MotionParam): number {
    // ±50% randomization around the base interval
    return p.interval * (0.5 + Math.random());
  }
}
