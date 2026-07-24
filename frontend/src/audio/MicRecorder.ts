/**
 * Microphone recorder with WAV output and silence detection.
 *
 * Uses MediaRecorder API + AnalyserNode — no deprecated APIs.
 * Outputs 16-bit PCM mono WAV at 16kHz via client-side webm→WAV conversion.
 */

export type RecorderState = "idle" | "recording" | "recognizing";

export interface MicRecorderCallbacks {
  onStateChange?: (state: RecorderState) => void;
  onLevel?: (db: number) => void;
  onData?: (wavBlob: Blob) => void;
  onError?: (error: Error) => void;
}

const SAMPLE_RATE = 16000;
const SILENCE_TIMEOUT_MS = 2000;
const MAX_RECORD_MS = 60000;
const MIN_RECORD_MS = 500;
const LEVEL_POLL_MS = 50;
/** dB threshold: below this is "silence". Higher = less sensitive (-50 is quieter than -40). */
const SILENCE_DB = -50;

export class MicRecorder {
  private _state: RecorderState = "idle";
  private _stream: MediaStream | null = null;
  private _context: AudioContext | null = null;
  private _analyser: AnalyserNode | null = null;
  private _source: MediaStreamAudioSourceNode | null = null;
  private _recorder: MediaRecorder | null = null;
  private _chunks: Blob[] = [];
  private _silenceTimer: number | null = null;
  private _maxTimer: number | null = null;
  private _levelTimer: number | null = null;
  private _startTime = 0;
  private _callbacks: MicRecorderCallbacks;

  constructor(callbacks: MicRecorderCallbacks = {}) {
    this._callbacks = callbacks;
  }

  get state(): RecorderState {
    return this._state;
  }

  set onData(cb: ((blob: Blob) => void) | undefined) {
    this._callbacks.onData = cb;
  }

  async start(): Promise<void> {
    if (this._state !== "idle") return;

    try {
      this._stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: false,  // off: preserves consonant detail for ASR
        },
      });

      // AudioContext for level metering (native sample rate)
      this._context = new AudioContext();
      this._source = this._context.createMediaStreamSource(this._stream);
      this._analyser = this._context.createAnalyser();
      this._analyser.fftSize = 256;
      this._source.connect(this._analyser);

      // MediaRecorder for capture (webm/opus) — high bitrate for ASR quality
      this._chunks = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      this._recorder = new MediaRecorder(this._stream, {
        mimeType,
        audioBitsPerSecond: 128000,  // 128 kbps mono = near-transparent for speech
      });
      this._recorder.ondataavailable = (e) => {
        if (e.data.size > 0) this._chunks.push(e.data);
      };

      this._startTime = Date.now();

      // Start recording + level polling
      this._recorder.start(100); // Collect data every 100ms
      this._startLevelPolling();

      this._setState("recording");
      this._resetSilenceTimer();
      this._maxTimer = window.setTimeout(() => this.stop(), MAX_RECORD_MS);
    } catch (err) {
      this._callbacks.onError?.(err as Error);
    }
  }

  async stop(): Promise<void> {
    if (this._state !== "recording") return;

    this._clearTimers();

    const duration = Date.now() - this._startTime;
    if (duration < MIN_RECORD_MS) {
      this._cleanup();
      this._setState("idle");
      return;
    }

    this._setState("recognizing");

    // Stop MediaRecorder and wait for final data
    const wavBlob = await new Promise<Blob>((resolve) => {
      this._recorder!.onstop = async () => {
        const webmBlob = new Blob(this._chunks, { type: "audio/webm" });
        try {
          const wav = await this._webmToWav(webmBlob);
          resolve(wav);
        } catch {
          // Fallback: send webm, backend will handle
          resolve(webmBlob);
        }
      };
      this._recorder!.stop();
    });

    this._callbacks.onData?.(wavBlob);
    this._cleanup();
  }

  cancel(): void {
    this._clearTimers();
    if (this._recorder?.state === "recording") {
      this._recorder.onstop = null;
      this._recorder.stop();
    }
    this._cleanup();
    this._setState("idle");
    this._chunks = [];
  }

  private _startLevelPolling(): void {
    const dataArray = new Uint8Array(this._analyser!.fftSize);
    this._levelTimer = window.setInterval(() => {
      if (!this._analyser) return;
      this._analyser.getByteTimeDomainData(dataArray);

      // Compute RMS
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        const normalized = (dataArray[i] - 128) / 128;
        sum += normalized * normalized;
      }
      const rms = Math.sqrt(sum / dataArray.length);
      const db = 20 * Math.log10(Math.max(rms, 1e-10));

      this._callbacks.onLevel?.(Math.max(-60, db));

      if (db > SILENCE_DB) {
        this._resetSilenceTimer();
      }
    }, LEVEL_POLL_MS);
  }

  private _resetSilenceTimer(): void {
    if (this._silenceTimer) clearTimeout(this._silenceTimer);
    this._silenceTimer = window.setTimeout(() => this.stop(), SILENCE_TIMEOUT_MS);
  }

  private _clearTimers(): void {
    if (this._silenceTimer) { clearTimeout(this._silenceTimer); this._silenceTimer = null; }
    if (this._maxTimer) { clearTimeout(this._maxTimer); this._maxTimer = null; }
    if (this._levelTimer) { clearInterval(this._levelTimer); this._levelTimer = null; }
  }

  private _setState(state: RecorderState): void {
    this._state = state;
    this._callbacks.onStateChange?.(state);
  }

  private _cleanup(): void {
    this._stream?.getTracks().forEach((t) => t.stop());
    this._source?.disconnect();
    this._context?.close();
    this._stream = null;
    this._context = null;
    this._analyser = null;
    this._source = null;
    this._recorder = null;
  }

  /**
   * Decode webm/blob → PCM → re-encode as WAV.
   *
   * Uses a temporary AudioContext to decode (no length limit),
   * then resamples to SAMPLE_RATE via OfflineAudioContext.
   */
  private async _webmToWav(blob: Blob): Promise<Blob> {
    if (blob.size < 100) throw new Error("Recording too short");

    const arrayBuffer = await blob.arrayBuffer();

    // Step 1: decode the compressed audio to get the raw PCM
    const decodeCtx = new AudioContext();
    let audioBuffer: AudioBuffer;
    try {
      // Resume if suspended (autoplay policy)
      if (decodeCtx.state === "suspended") {
        await decodeCtx.resume();
      }
      audioBuffer = await decodeCtx.decodeAudioData(arrayBuffer);
    } finally {
      decodeCtx.close();
    }

    // Step 2: resample to target sample rate
    const channel = audioBuffer.getChannelData(0);
    const duration = Math.max(audioBuffer.duration, 0.1);
    const offlineCtx = new OfflineAudioContext(
      1,
      Math.ceil(SAMPLE_RATE * duration),
      SAMPLE_RATE,
    );
    const source = offlineCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineCtx.destination);
    source.start(0);

    const resampled = await offlineCtx.startRendering();
    return this._encodeWAV(resampled.getChannelData(0));
  }

  private _encodeWAV(samples: Float32Array): Blob {
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    const buffer = new ArrayBuffer(44 + pcm.length * 2);
    const view = new DataView(buffer);
    writeStr(view, 0, "RIFF");
    view.setUint32(4, 36 + pcm.length * 2, true);
    writeStr(view, 8, "WAVE");
    writeStr(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, SAMPLE_RATE, true);
    view.setUint32(28, SAMPLE_RATE * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(view, 36, "data");
    view.setUint32(40, pcm.length * 2, true);

    const pcmView = new Int16Array(buffer, 44);
    pcmView.set(pcm);

    return new Blob([buffer], { type: "audio/wav" });
  }
}

function writeStr(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}
