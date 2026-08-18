"""SenseVoice offline ASR service.

Uses sherpa-onnx with SenseVoice Small int8 model for multilingual
speech recognition with emotion detection.
"""

from __future__ import annotations

import struct
import wave
from io import BytesIO
from pathlib import Path

import sherpa_onnx
from backend.config import ASR_MODEL_DIR

# ---- WAV Decoder (stdlib, no extra deps) ----


def _decode_wav_to_float32(wav_bytes: bytes) -> tuple[list[float], int]:
    """Decode WAV bytes into a float32 mono sample array.

    Args:
        wav_bytes: Raw WAV file bytes.

    Returns:
        Tuple of (samples as float32 list, sample_rate).

    Raises:
        ValueError: If WAV format is unsupported.
    """
    with wave.open(BytesIO(wav_bytes), "rb") as wf:
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()

        raw = wf.readframes(n_frames)

        # Convert PCM to float32
        if sample_width == 2:
            fmt = f"<{n_frames * n_channels}h"
            int_samples = struct.unpack(fmt, raw)
            max_val = 32768.0
        elif sample_width == 4:
            fmt = f"<{n_frames * n_channels}i"
            int_samples = struct.unpack(fmt, raw)
            max_val = 2147483648.0
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")

        # Convert to mono float32 by averaging channels
        samples: list[float] = []
        if n_channels == 1:
            samples = [s / max_val for s in int_samples]
        else:
            for i in range(n_frames):
                ch_sum = sum(int_samples[i * n_channels + ch] for ch in range(n_channels))
                samples.append(ch_sum / (n_channels * max_val))

        return samples, sample_rate


# ---- ASR Service ----


class ASRService:
    """Singleton wrapper around SenseVoice sherpa-onnx recognizer.

    Load the model once at startup; reuse for all recognition requests.
    """

    def __init__(self, model_dir: str | None = None) -> None:
        self._model_dir = Path(model_dir or ASR_MODEL_DIR)
        self._recognizer: sherpa_onnx.OfflineRecognizer | None = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self) -> None:
        """Load the SenseVoice ONNX model.

        Assumes the model directory contains:
            - model.int8.onnx  (or model.onnx)
            - tokens.txt
        """
        model_dir = self._model_dir.resolve()

        # Find the ONNX model file
        model_file = None
        for candidate in [
            model_dir / "model.int8.onnx",
            model_dir / "model.onnx",
        ]:
            if candidate.exists():
                model_file = candidate
                break

        if model_file is None:
            # Try wildcard search
            onnx_files = list(model_dir.glob("*.onnx"))
            if onnx_files:
                model_file = onnx_files[0]

        if model_file is None:
            raise FileNotFoundError(f"No ONNX model found in {model_dir}. Expected model.int8.onnx or model.onnx")

        tokens_file = model_dir / "tokens.txt"
        if not tokens_file.exists():
            # Try alternative token filenames
            for name in ["tokens.txt", "vocab.txt"]:
                p = model_dir / name
                if p.exists():
                    tokens_file = p
                    break
            else:
                raise FileNotFoundError(f"Tokens file not found in {model_dir}")

        print(f"[ASR] Loading SenseVoice model from {model_file}")
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model_file),
            tokens=str(tokens_file),
            use_itn=True,
        )
        self._loaded = True
        print("[ASR] Model loaded successfully")

    def recognize(self, wav_bytes: bytes) -> dict:
        """Recognize speech from WAV audio bytes.

        Args:
            wav_bytes: Complete WAV file bytes (16-bit PCM, mono, 16kHz).

        Returns:
            Dict with keys: text (str), language (str), emotion (str).

        Raises:
            RuntimeError: If model is not loaded.
        """
        if not self._recognizer:
            self.load_model()

        samples, sample_rate = _decode_wav_to_float32(wav_bytes)

        stream = self._recognizer.create_stream()  # type: ignore[union-attr]
        stream.accept_waveform(sample_rate, samples)
        self._recognizer.decode_stream(stream)  # type: ignore[union-attr]

        result_text = stream.result.text if hasattr(stream.result, "text") else ""

        # SenseVoice outputs format: "<|zh|><|NEUTRAL|><|Speech|><|woitn|>text"
        # Parse the language and emotion tags
        language = "zh"
        emotion = "neutral"

        import re

        lang_match = re.search(r"<\|(\w+)\|>", result_text)
        if lang_match:
            language = lang_match.group(1)

        emotion_match = re.search(r"<\|(HAPPY|SAD|ANGRY|NEUTRAL|SURPRISED|EXCITED|FEARFUL|DISGUSTED)\|>", result_text)
        if emotion_match:
            emotion = emotion_match.group(1).lower()

        # Clean up the format tags for plain text output
        clean_text = re.sub(r"<\|[^|]*\|>", "", result_text).strip()
        # Remove "Speech" and "woitn" tags as well
        clean_text = re.sub(r"<\|Speech\|>", "", clean_text)
        clean_text = re.sub(r"<\|woitn\|>", "", clean_text).strip()

        return {
            "text": clean_text,
            "language": language,
            "emotion": emotion,
        }


# Global singleton
asr_service = ASRService()
