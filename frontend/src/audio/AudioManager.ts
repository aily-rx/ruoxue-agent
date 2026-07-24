/**
 * Web Audio API manager for playing TTS audio from base64 MP3.
 *
 * Supports play/stop with auto-cleanup. Hooks into chat lifecycle
 * to stop playback when user sends a new message.
 */

export type PlayState = "idle" | "playing" | "paused";

export interface AudioManagerCallbacks {
  onStateChange?: (state: PlayState) => void;
  onEnded?: () => void;
  onError?: (error: Error) => void;
}

export class AudioManager {
  private _context: AudioContext | null = null;
  private _source: AudioBufferSourceNode | null = null;
  private _state: PlayState = "idle";
  private _callbacks: AudioManagerCallbacks;

  constructor(callbacks: AudioManagerCallbacks = {}) {
    this._callbacks = callbacks;
  }

  get state(): PlayState {
    return this._state;
  }

  private _getContext(): AudioContext {
    if (!this._context || this._context.state === "closed") {
      this._context = new AudioContext();
    }
    return this._context;
  }

  /**
   * Play audio from base64-encoded MP3 data.
   */
  async playBase64(base64: string): Promise<void> {
    this.stop();

    try {
      const ctx = this._getContext();

      // Decode base64 → ArrayBuffer
      const binaryStr = atob(base64);
      const bytes = new Uint8Array(binaryStr.length);
      for (let i = 0; i < binaryStr.length; i++) {
        bytes[i] = binaryStr.charCodeAt(i);
      }

      // Decode MP3 → AudioBuffer
      const audioBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0));

      // Play
      this._source = ctx.createBufferSource();
      this._source.buffer = audioBuffer;
      this._source.connect(ctx.destination);
      this._source.onended = () => {
        this._setState("idle");
        this._callbacks.onEnded?.();
      };

      this._source.start(0);
      this._setState("playing");
    } catch (err) {
      this._setState("idle");
      this._callbacks.onError?.(err as Error);
    }
  }

  /**
   * Stop current playback immediately.
   */
  stop(): void {
    if (this._source) {
      try { this._source.stop(); } catch { /* already stopped */ }
      this._source.disconnect();
      this._source = null;
    }
    this._setState("idle");
  }

  /**
   * Suspend the audio context (pauses playback).
   */
  async pause(): Promise<void> {
    if (this._context && this._context.state === "running") {
      await this._context.suspend();
      this._setState("paused");
    }
  }

  /**
   * Resume a paused audio context.
   */
  async resume(): Promise<void> {
    if (this._context && this._context.state === "suspended") {
      await this._context.resume();
      this._setState("playing");
    }
  }

  /**
   * Close the audio context and release resources.
   */
  close(): void {
    this.stop();
    this._context?.close();
    this._context = null;
  }

  private _setState(state: PlayState): void {
    this._state = state;
    this._callbacks.onStateChange?.(state);
  }
}
