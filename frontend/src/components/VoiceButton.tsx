/**
 * Voice input button with recording state animation.
 *
 * Handles press-to-talk interaction for voice input.
 */

import { useVoice } from "../hooks/useVoice";

export interface VoiceButtonProps {
  onRecognized: (text: string) => void;
  disabled?: boolean;
}

export function VoiceButton({ onRecognized, disabled }: VoiceButtonProps) {
  const {
    isRecording,
    isRecognizing,
    audioLevel,
    voiceError,
    startRecording,
    stopRecording,
  } = useVoice();

  const handlePointerDown = async () => {
    if (disabled || isRecording || isRecognizing) return;
    try {
      await startRecording();
    } catch {
      // Permission denied or device error — already set in useVoice
    }
  };

  const handlePointerUp = async () => {
    if (!isRecording) return;
    try {
      const text = await stopRecording();
      if (text.trim()) {
        onRecognized(text);
      }
    } catch {
      // Error already handled in useVoice
    }
  };

  // Map audio level (-60..0 dB) to a 0..1 scale
  const level = Math.max(0, Math.min(1, (audioLevel + 60) / 60));



  return (
    <div className="voice-button-wrapper">
      {voiceError && <span className="voice-error">{voiceError}</span>}
      <button
        className={`voice-button ${isRecording ? "recording" : ""} ${isRecognizing ? "recognizing" : ""}`}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        disabled={disabled || isRecognizing}
        aria-label={isRecording ? "Release to send" : "Press to talk"}
      >
        {/* Mic icon */}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>

        {/* Recording level ring */}
        {isRecording && (
          <span
            className="voice-level-ring"
            style={{
              transform: `scale(${0.8 + level * 0.4})`,
              opacity: 0.3 + level * 0.7,
            }}
          />
        )}

        {/* Recognizing spinner */}
        {isRecognizing && <span className="voice-spinner" />}
      </button>

      <style>{`
        .voice-button-wrapper {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          position: relative;
        }
        .voice-error {
          font-size: 11px;
          color: #ef4444;
          white-space: nowrap;
        }
        .voice-button {
          position: relative;
          width: 40px;
          height: 40px;
          border: 1px solid var(--border);
          border-radius: 50%;
          background: var(--surface);
          color: var(--text-secondary);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
          flex-shrink: 0;
        }
        .voice-button:hover:not(:disabled) {
          border-color: var(--primary);
          color: var(--primary);
          background: var(--primary-light);
        }
        .voice-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .voice-button.recording {
          border-color: #ef4444;
          color: #ef4444;
          background: #fef2f2;
          animation: pulse-ring 1.5s infinite;
        }
        .voice-button.recognizing {
          border-color: var(--primary);
          color: var(--primary);
          background: var(--primary-light);
        }
        .voice-level-ring {
          position: absolute;
          inset: -4px;
          border-radius: 50%;
          border: 2px solid #ef4444;
          pointer-events: none;
          transition: transform 0.1s, opacity 0.1s;
        }
        .voice-spinner {
          position: absolute;
          inset: -2px;
          border-radius: 50%;
          border: 2px solid var(--primary-light);
          border-top-color: var(--primary);
          animation: spin 0.8s linear infinite;
        }
        @keyframes pulse-ring {
          0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
          50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @media (max-width: 767px) {
          .voice-button { width: 36px; height: 36px; }
        }
      `}</style>
    </div>
  );
}
