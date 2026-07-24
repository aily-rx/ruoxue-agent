/**
 * ASR HTTP client — sends WAV audio to /api/asr and returns text.
 */

const API_BASE = "/api";

export interface ASRResult {
  text: string;
  language: string;
  emotion: string;
}

/**
 * Upload a WAV audio blob for speech recognition.
 */
export async function recognizeSpeech(
  wavBlob: Blob,
  signal?: AbortSignal,
): Promise<ASRResult> {
  const formData = new FormData();
  formData.append("file", wavBlob, "recording.wav");

  const response = await fetch(`${API_BASE}/asr`, {
    method: "POST",
    body: formData,
    signal,
  });

  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}));
    const detail = (errBody as { detail?: string }).detail || response.statusText;
    throw new Error(`ASR failed: ${detail}`);
  }

  return response.json();
}
