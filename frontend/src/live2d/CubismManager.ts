/**
 * CubismManager - Live2D model lifecycle orchestrator.
 * Uses official Cubism SDK for Web 5.
 */

import { CubismFramework } from './sdk/live2dcubismframework';
import { CubismModelSettingJson } from './sdk/cubismmodelsettingjson';
import { CubismMoc } from './sdk/model/cubismmoc';
import { CubismModel } from './sdk/model/cubismmodel';
import { CubismUserModel } from './sdk/model/cubismusermodel';
import { CubismRenderer_WebGL } from './sdk/rendering/cubismrenderer_webgl';
import { CubismExpressionMotion } from './sdk/motion/cubismexpressionmotion';
import { CubismMatrix44 } from './sdk/math/cubismmatrix44';
import { CubismModelMatrix } from './sdk/math/cubismmodelmatrix';
import { CubismUpdateScheduler } from './sdk/motion/cubismupdatescheduler';
import { CubismPhysicsUpdater } from './sdk/motion/cubismphysicsupdater';
import { CubismPoseUpdater } from './sdk/motion/cubismposeupdater';
import { CubismEyeBlinkUpdater } from './sdk/motion/cubismeyeblinkupdater';
import { CubismEyeBlink } from './sdk/effect/cubismeyeblink';
import { CubismMotion } from './sdk/motion/cubismmotion';
import { EmotionDriver } from './EmotionDriver';
import { LipSyncDriver } from './LipSyncDriver';

export interface Live2DState {
  loaded: boolean;
  error: string | null;
}

export class CubismManager extends CubismUserModel {
  private _canvas: HTMLCanvasElement;
  private _gl: WebGLRenderingContext;
  private _rafId: number = 0;
  private _state: Live2DState = { loaded: false, error: null };
  private _loading = false;
  private _disposed = false;
  private _resizeObserver: ResizeObserver | null = null;
  private _expressions: Array<{ name: string; motion: any }> = [];
  private _motions: Map<string, CubismMotion> = new Map();
  private _modelSetting: CubismModelSettingJson | null = null;
  private _updateScheduler = new CubismUpdateScheduler();
  private _lastFrameTime = 0;

  emotionDriver = new EmotionDriver();
  lipSyncDriver = new LipSyncDriver();
  onStateChange?: (state: Live2DState) => void;

  // Motion-based idle state
  private _idleTimer: number = 0;
  private _idleActive: boolean = false;

  private static _frameworkStarted = false;

  constructor(canvas: HTMLCanvasElement) {
    super();
    this._canvas = canvas;
    // SDK sample uses webgl2 — premultipliedAlpha required for correct Cubism rendering
    var gl = canvas.getContext('webgl2', {
      alpha: true, premultipliedAlpha: true, antialias: true, stencil: true,
    }) || canvas.getContext('webgl', {
      alpha: true, premultipliedAlpha: true, antialias: true, stencil: true,
    });
    if (!gl) throw new Error('WebGL not supported');
    this._gl = gl;

    // Ensure non-zero initial size (ResizeObserver will correct it immediately after observe)
    var dpr = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
    } else {
      canvas.width = 100;
      canvas.height = 100;
    }
    console.log('[Cubism] Canvas init:', canvas.width, 'x', canvas.height);

    // Use ResizeObserver to respond to CSS layout changes (flex, grid, etc.),
    // not just window resize. Fires synchronously on observe().
    var self = this;
    this._resizeObserver = new ResizeObserver(function() {
      self._resizeCanvas();
    });
    this._resizeObserver.observe(canvas);
  }

  get state() { return this._state; }

  private static _initFramework(): void {
    if (CubismManager._frameworkStarted) return;
    console.log('[Cubism] Init Framework...');
    CubismFramework.startUp();
    CubismFramework.initialize(1024 * 1024 * 16);
    CubismManager._frameworkStarted = true;
    console.log('[Cubism] Framework OK');
  }

  async loadModelFromUrl(modelJsonPath: string): Promise<void> {
    if (this._loading || this._model) return;
    this._loading = true;
    try {
      this._state = { loaded: false, error: null };
      this.onStateChange?.(this._state);
      CubismManager._initFramework();

      var baseUrl = modelJsonPath.substring(0, modelJsonPath.lastIndexOf('/') + 1);

      // 1. model3.json
      var resp = await fetch(modelJsonPath);
      if (!resp.ok) throw new Error('model3.json HTTP ' + resp.status);
      var buf = await resp.arrayBuffer();
      this._modelSetting = new CubismModelSettingJson(buf, buf.byteLength);
      console.log('[Cubism] model3.json OK');

      // 2. moc3 — CubismUserModel.loadModel creates CubismMoc + CubismModel
      var mocUrl = baseUrl + this._modelSetting.getModelFileName();
      var mocResp = await fetch(mocUrl);
      if (!mocResp.ok) throw new Error('moc3 HTTP ' + mocResp.status);
      var mocBuf = await mocResp.arrayBuffer();
      console.log('[Cubism] moc3:', mocBuf.byteLength, 'bytes');
      super.loadModel(mocBuf);
      if (!this._model) throw new Error('loadModel failed');
      console.log('[Cubism] Model OK, params:', this._model.getParameterCount(),
                  'masking:', this._model.isUsingMasking());

      // 3. Renderer — createRenderer already calls initialize() internally
      var cw = Math.max(this._canvas.width, 100);
      var ch = Math.max(this._canvas.height, 100);
      this.createRenderer(cw, ch);
      var rr0 = this.getRenderer() as CubismRenderer_WebGL;
      rr0.setIsPremultipliedAlpha(true);
      console.log('[Cubism] Renderer created');

      // 4. Textures (premultiplied alpha — required by SDK)
      for (var i = 0; i < this._modelSetting.getTextureCount(); i++) {
        var img = await this._loadImage(baseUrl + this._modelSetting.getTextureFileName(i));
        var t = this._gl.createTexture()!;
        this._gl.bindTexture(this._gl.TEXTURE_2D, t);
        this._gl.pixelStorei(this._gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 1);
        this._gl.texImage2D(this._gl.TEXTURE_2D, 0, this._gl.RGBA, this._gl.RGBA, this._gl.UNSIGNED_BYTE, img);
        this._gl.pixelStorei(this._gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 0);
        this._gl.texParameteri(this._gl.TEXTURE_2D, this._gl.TEXTURE_MIN_FILTER, this._gl.LINEAR);
        this._gl.texParameteri(this._gl.TEXTURE_2D, this._gl.TEXTURE_MAG_FILTER, this._gl.LINEAR);
        this._gl.texParameteri(this._gl.TEXTURE_2D, this._gl.TEXTURE_WRAP_S, this._gl.CLAMP_TO_EDGE);
        this._gl.texParameteri(this._gl.TEXTURE_2D, this._gl.TEXTURE_WRAP_T, this._gl.CLAMP_TO_EDGE);
        (this.getRenderer() as CubismRenderer_WebGL).bindTexture(i, t);
      }
      console.log('[Cubism] Textures:', this._modelSetting.getTextureCount());

      // 5. startUp + shaders
      var rr = this.getRenderer() as CubismRenderer_WebGL;
      rr.startUp(this._gl);
      rr.loadShaders('/shaders/WebGL/');
      console.log('[Cubism] Renderer ready, GL:', this._gl.getParameter(this._gl.VERSION));

      // 6. Physics + Pose — load and register updaters (matches SDK sample)
      try {
        var physicsPath = baseUrl + this._modelSetting.getPhysicsFileName();
        if (physicsPath && physicsPath.indexOf('undefined') < 0) {
          var physicsResp = await fetch(physicsPath);
          if (physicsResp.ok) {
            var physicsBuf = await physicsResp.arrayBuffer();
            this.loadPhysics(physicsBuf, physicsBuf.byteLength);
            if (this._physics) {
              this._updateScheduler.addUpdatableList(new CubismPhysicsUpdater(this._physics));
            }
            console.log('[Cubism] Physics loaded');
          }
        }
      } catch (e) { console.log('[Cubism] Physics skipped:', (e as Error).message); }

      try {
        var posePath = baseUrl + this._modelSetting.getPoseFileName();
        if (posePath && posePath.indexOf('undefined') < 0) {
          var poseResp = await fetch(posePath);
          if (poseResp.ok) {
            var poseBuf = await poseResp.arrayBuffer();
            this.loadPose(poseBuf, poseBuf.byteLength);
            if (this._pose) {
              this._updateScheduler.addUpdatableList(new CubismPoseUpdater(this._pose));
            }
            console.log('[Cubism] Pose loaded');
          }
        }
      } catch (e) { console.log('[Cubism] Pose skipped:', (e as Error).message); }

      // 6b. Eye blink — auto-blink using model settings (PRD: interval 2-5s random)
      try {
        if (this._modelSetting.getEyeBlinkParameterCount() > 0) {
          this._eyeBlink = CubismEyeBlink.create(this._modelSetting);
          this._updateScheduler.addUpdatableList(new CubismEyeBlinkUpdater(function() { return false; }, this._eyeBlink));
          console.log('[Cubism] EyeBlink loaded, params:', this._modelSetting.getEyeBlinkParameterCount());
        }
      } catch (e) { console.log('[Cubism] EyeBlink skipped:', (e as Error).message); }

      // 7. Expressions
      for (var i = 0; i < this._modelSetting.getExpressionCount(); i++) {
        try {
          var er = await fetch(baseUrl + this._modelSetting.getExpressionFileName(i));
          if (!er.ok) continue;
          var eb = await er.arrayBuffer();
          var m = CubismExpressionMotion.create(eb, eb.byteLength);
          if (m) this._expressions.push({ name: this._modelSetting.getExpressionName(i), motion: m });
        } catch (e) {}
      }

      // 8. Motions — load all .motion3.json files with effect IDs for EyeBlink/LipSync
      var motionNames = ['mtn_01', 'mtn_02', 'mtn_03', 'mtn_04', 'special_01', 'special_02', 'special_03'];
      // Collect eye blink and lip sync parameter IDs for setEffectIds (required before doUpdateParameters)
      var eyeBlinkIds: any[] = [];
      var lipSyncIds: any[] = [];
      for (var bi = 0; bi < this._modelSetting.getEyeBlinkParameterCount(); bi++) {
        eyeBlinkIds.push(this._modelSetting.getEyeBlinkParameterId(bi));
      }
      for (var li = 0; li < this._modelSetting.getLipSyncParameterCount(); li++) {
        lipSyncIds.push(this._modelSetting.getLipSyncParameterId(li));
      }
      for (var mi = 0; mi < motionNames.length; mi++) {
        try {
          var motionUrl = baseUrl + 'motions/' + motionNames[mi] + '.motion3.json';
          var mr = await fetch(motionUrl);
          if (!mr.ok) continue;
          var mb = await mr.arrayBuffer();
          var motion = CubismMotion.create(mb, mb.byteLength);
          if (motion) {
            // REQUIRED: set EyeBlink/LipSync effect IDs before doUpdateParameters,
            // otherwise _eyeBlinkParameterIds is null → TypeError.
            motion.setEffectIds(eyeBlinkIds, lipSyncIds);
            // SDK ignores JSON "Loop":true — must set manually.
            motion._isLoop = true;
            this._motions.set(motionNames[mi], motion);
            console.log('[Cubism] Motion loaded:', motionNames[mi],
                        'dur:', motion.getDuration().toFixed(1) + 's');
          }
        } catch (e) { console.log('[Cubism] Motion skip:', motionNames[mi]); }
      }
      console.log('[Cubism] Motions loaded:', this._motions.size);

      // 8. Drivers
      this.emotionDriver.attach(this._model, this._expressions);
      this.lipSyncDriver.attach(this._model);

      this._state = { loaded: true, error: null };
      this.onStateChange?.(this._state);
      this._startLoop();
      this.startIdleMotion();  // begin motion-based idle after load
      console.log('[Cubism] Loaded OK');
    } catch (err) {
      var msg = (err as Error).message || String(err);
      console.error('[Cubism] FAILED:', msg);
      this._state = { loaded: false, error: msg };
      this.onStateChange?.(this._state);
      throw err;
    } finally { this._loading = false; }
  }

  startLipSync(t: Array<{ time_ms: number; A: number; I: number; U: number; E: number; O: number }>, d: number, startTime?: number) { this.lipSyncDriver.start(t, d, startTime); }
  stopLipSync() { this.lipSyncDriver.stop(); }

  playMotion(name: string, priority: number = 1): boolean {
    var motion = this._motions.get(name);
    if (!motion) { console.warn('[Cubism] Motion not found:', name); return false; }
    // Stop all existing motions first to avoid multi-motion conflict
    this._motionManager.stopAllMotions();
    this._motionManager.startMotionPriority(motion, false, priority);
    console.log('[Cubism] Motion:', name, 'pri:', priority);
    return true;
  }

  stopAllMotions(): void {
    this._motionManager.stopAllMotions();
    this._idleActive = false;
  }

  /** Start idle motion — fixed mtn_01 loop. */
  startIdleMotion(): void {
    this._motionManager.stopAllMotions();
    var motion = this._motions.get('mtn_01');
    if (!motion) return;
    this._motionManager.startMotionPriority(motion, false, 0);
    this._idleTimer = Infinity;  // never auto-switch
    this._idleActive = true;
    console.log('[Cubism] Idle: mtn_01 (fixed)');
  }

  getMotionNames(): string[] { return Array.from(this._motions.keys()); }

  dispose(): void {
    this._disposed = true;
    this._stopLoop();
    this.lipSyncDriver.detach();
    this.emotionDriver.detach();
    this._motions.forEach(function(m) { m.release(); });
    this._motions.clear();
    this.release();
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
  }

  private _resizeCanvas = (): void => {
    var dpr = window.devicePixelRatio || 1;
    var r = this._canvas.getBoundingClientRect();
    var w = r.width * dpr;
    var h = r.height * dpr;
    // Guard: avoid setting canvas dimensions to the same value,
    // which would otherwise destroy the WebGL context and all loaded resources.
    if (this._canvas.width === w && this._canvas.height === h) return;
    this._canvas.width = w;
    this._canvas.height = h;
    var rr = this.getRenderer() as CubismRenderer_WebGL;
    rr?.setRenderTargetSize(this._canvas.width, this._canvas.height);
  };

  private _startLoop(): void {
    if (this._rafId) return;
    var self = this;
    var frame = function() {
      self._rafId = requestAnimationFrame(frame);
      if (!self._model || self._disposed) { self._rafId = 0; return; }
      try {
        var n = performance.now();
        var dt = self._lastFrameTime
          ? Math.min((n - self._lastFrameTime) / 1000, 0.1) // cap at 100ms to avoid physics burst
          : 0.016;
        self._lastFrameTime = n;
        // Motion-based idle timer — switch motion when expired
        if (self._idleActive && self._model) {
          self._idleTimer -= dt;
          if (self._idleTimer <= 0) {
            self.startIdleMotion();
          }
        }

        // Render order: motion (base) → emotion (face override) → lip-sync (mouth override)
        // This prevents motion from overwriting expression or lip-sync params.
        self._motionManager.updateMotion(self._model, dt);
        self.emotionDriver.update(n);
        self.lipSyncDriver.update(n);
        // Run SDK update scheduler: physics, pose, eye blink updaters
        self._updateScheduler.onLateUpdate(self._model, dt);
        self._model.update();

        var gl = self._gl;
        var rr = self.getRenderer() as CubismRenderer_WebGL;
        if (!rr) { self._rafId = 0; return; }

        // Per-frame GL setup — matches official SDK sample lAppSubdelegate.update()
        gl.clearColor(0.0, 0.0, 0.0, 0.0);
        gl.enable(gl.DEPTH_TEST);
        gl.depthFunc(gl.LEQUAL);
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
        gl.clearDepth(1.0);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

        // MVP matrix — matches official SDK sample lAppModel.draw()
        var proj = new CubismMatrix44();
        var modelMatrix = new CubismModelMatrix(
          self._model.getCanvasWidth(), self._model.getCanvasHeight()
        );
        proj.loadIdentity();
        var ratio = self._canvas.width / self._canvas.height;
        if (ratio < 1) {
          proj.scale(1, ratio);
        } else {
          proj.scale(1 / ratio, 1);
        }
        proj.multiplyByMatrix(modelMatrix);
        rr.setMvpMatrix(proj);

        // setRenderState + drawModel — matches official SDK sample lAppModel.doDraw()
        rr.setRenderState(null, [0, 0, self._canvas.width, self._canvas.height]);
        rr.drawModel();
      } catch (e) {
        console.error('[Cubism] Render error:', e);
        self._rafId = 0;
        self._state = { loaded: false, error: 'Render: ' + ((e as Error).message || String(e)) };
        self.onStateChange?.(self._state);
      }
    };
    this._rafId = requestAnimationFrame(frame);
  }

  private _stopLoop(): void { if (this._rafId) { cancelAnimationFrame(this._rafId); this._rafId = 0; } }

  private _loadImage(url: string): Promise<HTMLImageElement> {
    return new Promise(function(resolve, reject) {
      var img = new Image(); img.crossOrigin = 'anonymous';
      img.onload = function() { resolve(img); };
      img.onerror = function() { reject(new Error('Texture: ' + url)); };
      img.src = url;
    });
  }
}
