/**
 * Voice recording and ASR state management hook.
 */

import { useCallback, useRef, useState } from "react";
import { MicRecorder, RecorderState } from "../audio/MicRecorder";
import { recognizeSpeech } from "../chat/ASRClient";

export function useVoice() {
  const [recorderState, setRecorderState] = useState<RecorderState>("idle");
  const [audioLevel, setAudioLevel] = useState(-60);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const recorderRef = useRef<MicRecorder | null>(null);

  const startRecording = useCallback(async () => {
    setVoiceError(null);

    const recorder = new MicRecorder({
      onStateChange(state) {
        setRecorderState(state);
      },
      onLevel(db) {
        setAudioLevel(db);
      },
      onData: undefined, // handled in callback below
      onError(err) {
        setVoiceError(err.message);
        setRecorderState("idle");
      },
    });

    recorderRef.current = recorder;
    await recorder.start();
  }, []);

  /**
   * Stop recording, send to ASR, return recognized text.
   */
  const stopRecording = useCallback((): Promise<string> => {
    return new Promise((resolve, reject) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state !== "recording") {
        reject(new Error("Not recording"));
        return;
      }

      // Set the onData callback before stopping
      recorder.onData = async (wavBlob: Blob) => {
        try {
          const result = await recognizeSpeech(wavBlob);
          setRecorderState("idle");
          setAudioLevel(-60);
          resolve(result.text);
        } catch (err) {
          const msg = err instanceof Error ? err.message : "ASR failed";
          setVoiceError(msg);
          setRecorderState("idle");
          reject(err);
        }
      };

      recorder.stop();
    });
  }, []);

  const cancelRecording = useCallback(() => {
    recorderRef.current?.cancel();
    setRecorderState("idle");
    setAudioLevel(-60);
  }, []);

  const isRecording = recorderState === "recording";
  const isRecognizing = recorderState === "recognizing";

  return {
    recorderState,
    isRecording,
    isRecognizing,
    audioLevel,
    voiceError,
    startRecording,
    stopRecording,
    cancelRecording,
  };
}
