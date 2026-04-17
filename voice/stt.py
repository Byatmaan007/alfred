"""
Speech-to-Text module for Alfred.
Uses OpenAI Whisper with VAD (Voice Activity Detection) silence detection.
Stops recording automatically when you stop talking — no fixed wait time.
"""

import whisper
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os

# ── Whisper model ──────────────────────────────────────────────────────────────
_model      = None
_MODEL_SIZE = "base"

SAMPLE_RATE = 16000

# ── VAD settings ───────────────────────────────────────────────────────────────
VAD_CHUNK_SECS    = 0.3    # read microphone in 300 ms chunks
VAD_SPEECH_THRESH = 0.015  # RMS above this = speech
VAD_SILENCE_SECS  = 1.2    # stop after 1.2 s of continuous silence
VAD_MIN_SECS      = 0.5    # don't stop before at least 0.5 s of speech
VAD_MAX_SECS      = 12.0   # hard cap


def _load_model() -> whisper.Whisper:
    global _model
    if _model is None:
        _model = whisper.load_model(_MODEL_SIZE)
    return _model


def transcribe(audio: np.ndarray) -> str:
    """Write audio to a temp WAV and transcribe with Whisper."""
    model = _load_model()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    wav.write(tmp, SAMPLE_RATE, (audio * 32767).astype(np.int16))
    try:
        result = model.transcribe(tmp, fp16=False, language="en")
        return result["text"].strip()
    finally:
        os.unlink(tmp)

# alias kept for internal use
_transcribe = transcribe


def listen(duration: int = 5) -> str:
    """
    Smart listen: records until silence is detected (VAD).
    Falls back to fixed-duration recording if VAD finds nothing.

    Args:
        duration: Max seconds to record (default 5, hard cap VAD_MAX_SECS)
    Returns:
        Transcribed text, or empty string if nothing heard.
    """
    chunk_n        = int(VAD_CHUNK_SECS * SAMPLE_RATE)
    silence_needed = int(VAD_SILENCE_SECS / VAD_CHUNK_SECS)
    min_chunks     = int(VAD_MIN_SECS   / VAD_CHUNK_SECS)
    max_chunks     = int(min(duration, VAD_MAX_SECS) / VAD_CHUNK_SECS)

    audio_chunks   = []
    silence_count  = 0
    speech_chunks  = 0
    has_speech     = False

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=chunk_n,
    ) as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(chunk_n)
            chunk    = chunk.flatten()
            rms      = float(np.sqrt(np.mean(chunk ** 2)))
            is_speech = rms >= VAD_SPEECH_THRESH

            if is_speech:
                has_speech    = True
                silence_count = 0
                speech_chunks += 1
                audio_chunks.append(chunk)
            else:
                if has_speech:
                    silence_count += 1
                    audio_chunks.append(chunk)    # include trailing silence
                    if silence_count >= silence_needed and speech_chunks >= min_chunks:
                        break   # natural end of utterance

    if not audio_chunks or not has_speech:
        return ""

    audio = np.concatenate(audio_chunks)
    return _transcribe(audio)
