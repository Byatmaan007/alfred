"""
Wake word detection for Alfred.
Uses a rolling 3-second audio buffer checked every second.
No chunk boundary misses — "Hey Alfred" is always captured whole.
"""

import collections
import re
import tempfile
import os
import numpy as np
import whisper
import sounddevice as sd
import scipy.io.wavfile as wav

SAMPLE_RATE   = 16000
CHUNK_SECS    = 0.5    # stream in 0.5 s blocks
WINDOW_SECS   = 3.0    # transcribe the last 3 s each check
CHECK_EVERY   = 2      # check after every 2 new chunks (every 1 s)
ENERGY_THRESH = 0.008  # ignore silence

# All phrases that trigger Alfred
_WAKE_VARIANTS = {
    "alfred",
    "hey alfred",
    "ok alfred",
    "okay alfred",
    "hi alfred",
}

_model = None


def _get_model() -> whisper.Whisper:
    global _model
    if _model is None:
        _model = whisper.load_model("tiny")
    return _model


def load() -> None:
    """Pre-load Whisper tiny so the first wake is instant."""
    _get_model()


def _is_wake(text: str) -> bool:
    t = text.lower().strip().rstrip(".,!?")
    return any(re.search(r'\b' + re.escape(v) + r'\b', t) for v in _WAKE_VARIANTS)


def listen_for_wake_word() -> None:
    """
    Block until a wake phrase is detected.
    Streams audio continuously into a rolling 3-second window,
    then transcribes every second — no chunk boundary misses.
    """
    model        = _get_model()
    chunk_n      = int(CHUNK_SECS * SAMPLE_RATE)
    window_n     = int(WINDOW_SECS * SAMPLE_RATE)
    buffer       = collections.deque(maxlen=window_n)
    new_chunks   = 0

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=chunk_n,
    ) as stream:
        while True:
            chunk, _ = stream.read(chunk_n)
            buffer.extend(chunk.flatten())
            new_chunks += 1

            if new_chunks < CHECK_EVERY:
                continue
            new_chunks = 0

            audio = np.array(buffer, dtype=np.float32)
            if np.sqrt(np.mean(audio ** 2)) < ENERGY_THRESH:
                continue   # silence — skip transcription

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            wav.write(tmp, SAMPLE_RATE, (audio * 32767).astype(np.int16))

            try:
                result = model.transcribe(tmp, fp16=False, language="en")
                if _is_wake(result.get("text", "")):
                    return
            except Exception:
                pass
            finally:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass
