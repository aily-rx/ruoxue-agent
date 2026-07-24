/**
 * EmotionDriver — emotion label to Live2D expression mapping.
 *
 * Uses the model's preset .exp3.json expressions (corrected index mapping)
 * combined with per-parameter targets for emotions without presets.
 *
 * Important: the mao_pro model uses specific parameter names:
 *   Mouth: ParamMouthUp, ParamMouthDown, ParamMouthAngry, ParamA
 *   Eyes:  ParamEyeLOpen, ParamEyeROpen, ParamEyeLSmile, ParamEyeRSmile
 *   Brows: ParamBrowLY, ParamBrowRY, ParamBrowLAngle, ParamBrowRAngle
 *
 * NOT ParamMouthOpenY, ParamAngleX/Y/Z — those don't exist in this model.
 */

import { CubismModel } from './sdk/model/cubismmodel';
import { CubismFramework } from './sdk/live2dcubismframework';

type Emotion = 'happy' | 'sad' | 'angry' | 'surprised' | 'neutral' | 'thoughtful' | 'worried' | 'excited';

interface EmotionConfig {
  /** Preset expression index from .exp3.json files (0-based) */
  expressionIndex: number | null;
  /** Per-parameter targets for emotions without preset, or to augment presets */
  params?: Record<string, number>;
  transitionMs: number;
}

/**
 * Expression file → actual content (verified from .exp3.json files):
 *   exp_01: eyes open (neutral default)
 *   exp_02: eye smile (happy eyes)
 *   exp_03: all zero (blank neutral)
 *   exp_04: big eyes + sparkle (excited)
 *   exp_05: brows down + mouth down (angry/sad brows)
 *   exp_06: cheek blush + brows down (shy/embarrassed)
 *   exp_07: wide eyes + surprised brows + mouth down (surprised)
 *   exp_08: angry mouth + sharp eyes (angry)
 */
var CONFIG: Record<Emotion, EmotionConfig> = {
  neutral: {
    expressionIndex: 0,   // exp_01: pass-through (all Add=0, Multiply=1)
    params: {
      // Mouth
      ParamMouthUp: 0, ParamMouthDown: 0, ParamMouthAngry: 0, ParamMouthAngryLine: 0,
      ParamA: 0, ParamI: 0, ParamU: 0, ParamE: 0, ParamO: 0,
      // Cheek
      ParamCheek: 0,
      // Eyes — openness (1.0 = fully open, NOT 0)
      ParamEyeLOpen: 1.0, ParamEyeROpen: 1.0,
      // Eyes — expression effects reset from happy/excited/angry presets
      ParamEyeLSmile: 0, ParamEyeRSmile: 0,
      ParamEyeLForm: 0, ParamEyeRForm: 0,
      ParamEyeEffect: 0, ParamEyeBallForm: 0,
      // Brows — reset from sad/thoughtful/surprised/angry presets
      ParamBrowLY: 0, ParamBrowRY: 0,
      ParamBrowLAngle: 0, ParamBrowRAngle: 0,
      ParamBrowLForm: 0, ParamBrowRForm: 0,
    },
    transitionMs: 500,
  },
  happy: {
    expressionIndex: 1,   // exp_02: eye smile
    params: {
      ParamMouthUp: 0.8,      // smile
      ParamMouthDown: 0.0,
      ParamCheek: 0.5,         // slight blush
    },
    transitionMs: 300,
  },
  excited: {
    expressionIndex: 3,   // exp_04: big eyes + sparkle
    params: {
      ParamMouthUp: 1.0,
      ParamCheek: 0.8,
      ParamA: 0.2,             // mouth slightly open
    },
    transitionMs: 200,
  },
  sad: {
    expressionIndex: 4,   // exp_05: brows down + mouth down
    params: {
      ParamMouthDown: 1.0,
      ParamMouthUp: 0.0,
      ParamEyeLOpen: 0.7,     // eyes half-closed
      ParamEyeROpen: 0.7,
    },
    transitionMs: 500,
  },
  surprised: {
    expressionIndex: 6,   // exp_07: wide eyes + surprised brows
    params: {
      ParamA: 0.8,             // mouth open wide
      ParamMouthDown: 0.2,
    },
    transitionMs: 150,
  },
  angry: {
    expressionIndex: 7,   // exp_08: angry mouth + sharp eyes
    params: {
      ParamMouthAngry: 1.0,
      ParamMouthUp: 0.0,
      ParamBrowLY: -0.5,
      ParamBrowRY: -0.5,
    },
    transitionMs: 200,
  },
  thoughtful: {
    expressionIndex: 5,   // exp_06: blush + slight brow change
    params: {
      ParamEyeLOpen: 0.85,
      ParamEyeROpen: 1.0,     // one eye slightly more open
      ParamBrowLY: 0.3,
      ParamBrowRY: -0.1,
      ParamCheek: 0.3,
    },
    transitionMs: 450,
  },
  worried: {
    expressionIndex: 4,   // exp_05: sad brows — combine with worried mouth
    params: {
      ParamMouthDown: 0.2,
      ParamMouthAngry: 0.3,
      ParamBrowLY: -0.2,
      ParamBrowRY: -0.2,
      ParamEyeLOpen: 0.85,
      ParamEyeROpen: 0.85,
    },
    transitionMs: 400,
  },
};

export class EmotionDriver {
  private _model: CubismModel | null = null;
  private _expressions: Array<{ name: string; motion: any }> = [];
  private _cur: Emotion = 'neutral';
  private _intensity: number = 0.0;

  // Per-parameter smooth transition state
  private _paramIds: Record<string, any> = {};
  private _paramCurrent: Record<string, number> = {};
  private _paramTarget: Record<string, number> = {};
  private _paramFrom: Record<string, number> = {};
  private _transitionStartMs: number = 0;
  private _transitionMs: number = 400;
  // Two-phase transition: neutral → target for visual clarity
  private _phaseTwo: EmotionConfig | null = null;
  private _phaseTwoIntensity: number = 0;
  // Deferred expression preset — applied at END of transition, not instantly
  private _targetExpressionIndex: number | null = null;

  attach(model: CubismModel, exps: Array<{ name: string; motion: any }> = []): void {
    this._model = model;
    this._expressions = exps;
    // Pre-resolve parameter IDs
    var idm = CubismFramework.getIdManager();
    for (var emo in CONFIG) {
      var cfg = CONFIG[emo as Emotion];
      for (var pname in cfg.params) {
        if (!this._paramIds[pname]) {
          this._paramIds[pname] = idm.getId(pname);
          this._paramCurrent[pname] = cfg.params[pname]; // start at neutral-like default
        }
      }
    }
    // Initialize from neutral
    var ncfg = CONFIG['neutral'];
    for (var p in ncfg.params) {
      this._paramCurrent[p] = ncfg.params[p];
      this._paramTarget[p] = ncfg.params[p];
      this._paramFrom[p] = ncfg.params[p];
    }
    this._targetExpressionIndex = 0;   // neutral expression preset
    this._applyExpression(0);           // set neutral expression immediately on attach
  }

  detach(): void {
    this._model = null;
    this._expressions = [];
  }

  transitionTo(emotion: Emotion, intensity: number): void {
    this._cur = emotion;
    this._intensity = Math.max(0, Math.min(1, intensity));
    var cfg = CONFIG[emotion];
    var tgtParams = cfg.params || {};
    var neutralParams = CONFIG['neutral'].params || {};

    if (emotion === 'neutral') {
      // Single-phase: smooth lerp directly to full neutral values.
      // Intensity is ignored — "half neutral" makes eyes half-closed.
      for (var p in tgtParams) {
        var cur = this._paramCurrent[p] !== undefined ? this._paramCurrent[p] : (neutralParams[p] !== undefined ? neutralParams[p] : 0);
        this._paramFrom[p] = cur;
        this._paramTarget[p] = tgtParams[p];  // full neutral: eyes=1.0, mouth=0, etc.
      }
      this._transitionStartMs = performance.now();
      this._transitionMs = cfg.transitionMs;
      this._phaseTwo = null;
    } else {
      // Two-phase for non-neutral: snap ALL params to real neutral → transition to target.
      // Phase 1 drives EVERY neutral config param (not just tgtParams), so expression-preset
      // effects from the previous emotion (eye smile, brow angle, sparkle) are fully reset.
      var NEUTRAL_MS = 200;
      for (var p in neutralParams) {
        var cur = this._paramCurrent[p] !== undefined ? this._paramCurrent[p] : neutralParams[p];
        this._paramFrom[p] = cur;
        this._paramTarget[p] = neutralParams[p];  // eyes→1.0, mouth→0, effects→0
      }
      this._transitionStartMs = performance.now();
      this._transitionMs = NEUTRAL_MS;
      this._phaseTwo = cfg;
      this._phaseTwoIntensity = this._intensity;
    }

    // Defer expression preset — apply at END of transition (not instantly),
    // so eye shapes and per-param lerp share the same timeline.
    this._targetExpressionIndex = (cfg.expressionIndex !== null && cfg.expressionIndex !== undefined)
      ? cfg.expressionIndex : null;
  }

  reset(): void {
    // Restore model to pristine default state — load saved parameters from initial load
    this._phaseTwo = null;
    this._targetExpressionIndex = null;
    this._cur = 'neutral';
    this._intensity = 0;
    // Clear all driven param targets so update() stops overriding model defaults
    for (var p in this._paramTarget) {
      delete this._paramTarget[p];
    }
    if (this._model) {
      // Reload the saved baseline (captured at model load time via saveParameters)
      this._model.loadParameters();
      // Apply neutral preset expression on top of defaults
      this._applyExpression(0);
    }
  }

  /**
   * Called every frame. Lerps parameters using easeInOutCubic.
   * Applies deferred expression preset only at transition end.
   */
  update(_now: number): void {
    if (!this._model) return;

    var elapsed = performance.now() - this._transitionStartMs;
    var t = Math.min(elapsed / this._transitionMs, 1.0);
    var eased = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

    // Lerp all driven params
    for (var p in this._paramTarget) {
      var id = this._paramIds[p];
      if (!id) continue;
      this._paramCurrent[p] = this._paramFrom[p] + (this._paramTarget[p] - this._paramFrom[p]) * eased;
      try { this._model.setParameterValueById(id, this._paramCurrent[p]); } catch (_) {}
    }

    // IMPORTANT: check expression/cleanup BEFORE Phase 2 trigger.
    // If Phase 2 fires first, it clears _phaseTwo, then the expression check
    // sees !_phaseTwo and immediately applies+clears _paramTarget — deleting
    // the Phase 2 targets before they ever get lerped. (single-frame race)
    if (t >= 1.0 && !this._phaseTwo && this._targetExpressionIndex !== null) {
      this._applyExpression(this._targetExpressionIndex);
      this._targetExpressionIndex = null;
      // Transition complete — release all params so eye blink / idle motion work
      for (var p in this._paramTarget) {
        delete this._paramTarget[p];
      }
    }

    // Phase 2 trigger: phase 1 complete, start target transition
    if (t >= 1.0 && this._phaseTwo) {
      var cfg = this._phaseTwo;
      var tgtParams = cfg.params || {};

      for (var p2 in tgtParams) {
        this._paramFrom[p2] = this._paramCurrent[p2] !== undefined ? this._paramCurrent[p2] : 0;
        this._paramTarget[p2] = tgtParams[p2] * this._phaseTwoIntensity;
      }

      this._transitionStartMs = performance.now();
      this._transitionMs = cfg.transitionMs;
      this._phaseTwo = null;  // only once
      // Don't apply expression yet — Phase 2 just started
    }
  }

  get currentEmotion(): Emotion { return this._cur; }
  get currentIntensity(): number { return this._intensity; }

  private _applyExpression(index: number): void {
    if (!this._model || index < 0 || index >= this._expressions.length) return;
    var exp = this._expressions[index];
    if (exp && exp.motion) {
      exp.motion.doUpdateParameters(this._model, performance.now() / 1000, 1.0, null as any);
    }
  }
}
