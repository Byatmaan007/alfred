"""Alfred — main entry point."""
import collections
import msvcrt
import os
import queue
import sys
import threading
import time
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

if not os.getenv("ANTHROPIC_API_KEY"):
    print("ERROR: ANTHROPIC_API_KEY not found.")
    sys.exit(1)

import numpy as np
import sounddevice as sd
from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from agent import chat, reset
from voice.tts import speak, speak_sample
from voice.stt import transcribe

from ui import halo, C_HOT, C_SCAN, C_MUTED, C_WHITE, C_ACCENT

console = Console(highlight=False)

# ── VAD config ─────────────────────────────────────────────────────────────────
RATE          = 16_000
CHUNK_SECS    = 0.05                      # 50 ms callback chunks
CHUNK_N       = int(CHUNK_SECS * RATE)
ENERGY_THRESH = 0.015                     # RMS threshold — speech vs silence
PRE_ROLL_N    = int(0.2  / CHUNK_SECS)   # 200 ms pre-roll before speech
SILENCE_N     = int(0.6  / CHUNK_SECS)   # 0.6 s silence → end of utterance
MIN_SPEECH_N  = int(0.2  / CHUNK_SECS)   # ignore bursts < 200 ms
MAX_RECORD_N  = int(12.0 / CHUNK_SECS)   # hard cap at 12 s


def _w() -> int:
    return max(55, min(console.width, 120))


# ── unified input loop ─────────────────────────────────────────────────────────

def _wait_for_input() -> tuple[str, str]:
    """
    Shows idle halo, detects voice via VAD, also accepts keyboard.
    Returns ('voice', transcribed_text) or ('keyboard', typed_text).
    """
    typed:    list[str]        = []
    pre_roll: collections.deque = collections.deque(maxlen=PRE_ROLL_N)
    recording: list             = []
    audio_q   = queue.Queue()

    state         = 'idle'   # 'idle' | 'listening'
    speech_chunks = 0
    silence_chunks = 0

    def _cb(indata, frames, time_info, status):
        audio_q.put(indata.flatten().copy())

    t_start = time.time()

    with sd.InputStream(
        samplerate=RATE, channels=1, dtype='float32',
        blocksize=CHUNK_N, callback=_cb,
    ):
        with Live(console=console, refresh_per_second=20) as live:
            while True:
                dt = time.time() - t_start
                w  = _w()

                # ── keyboard ──────────────────────────────────────────────────
                while msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch == '\r':
                        return 'keyboard', ''.join(typed)
                    elif ch == '\x03':
                        raise KeyboardInterrupt
                    elif ch in ('\x00', '\xe0'):
                        msvcrt.getwch()
                    elif ch == '\x08' and typed:
                        typed.pop()
                    elif ord(ch) >= 32:
                        typed.append(ch)

                # ── VAD ───────────────────────────────────────────────────────
                recording_done = False
                while not audio_q.empty():
                    chunk = audio_q.get_nowait()
                    rms   = float(np.sqrt(np.mean(chunk ** 2)))

                    if state == 'idle':
                        pre_roll.append(chunk)
                        if rms > ENERGY_THRESH:
                            state         = 'listening'
                            recording     = list(pre_roll)
                            speech_chunks  = 1
                            silence_chunks = 0

                    elif state == 'listening':
                        recording.append(chunk)
                        if rms > ENERGY_THRESH:
                            speech_chunks  += 1
                            silence_chunks  = 0
                        else:
                            silence_chunks += 1

                        end = (silence_chunks >= SILENCE_N and speech_chunks >= MIN_SPEECH_N)
                        if end or len(recording) >= MAX_RECORD_N:
                            recording_done = True
                            break

                # ── transcribe when utterance complete ────────────────────────
                if recording_done:
                    live.update(halo(dt, 'thinking', w))
                    audio = np.concatenate(recording)
                    text  = transcribe(audio).strip()
                    if text:
                        return 'voice', text
                    # false positive — reset
                    state          = 'idle'
                    recording      = []
                    speech_chunks  = 0
                    silence_chunks = 0
                    pre_roll.clear()

                # ── display ───────────────────────────────────────────────────
                cur_state  = 'listening' if state == 'listening' else 'idle'
                typed_str  = ''.join(typed)
                hint       = f"▶ {typed_str}█" if typed_str else "type or just speak"
                hint_style = C_WHITE if typed_str else C_MUTED

                live.update(Group(
                    halo(dt, cur_state, w),
                    Text(hint.center(w), style=hint_style, no_wrap=True),
                ))
                time.sleep(1 / 20)


# ── helpers ────────────────────────────────────────────────────────────────────

def handle_message(user_message: str) -> None:
    console.print()
    response = chat(user_message)
    speak(response)
    console.print()


# ── main loop ──────────────────────────────────────────────────────────────────

def run() -> None:
    console.clear()

    # Pre-load Whisper base model before first use
    console.print(f"\n  [{C_MUTED}]loading voice model...[/]", end="")
    from voice.stt import _load_model
    _load_model()
    console.print(f"  [{C_SCAN}]ready[/]\n")

    greeting = "Alfred online. Just speak to me."
    console.print(f"  [{C_SCAN}]◈[/] {greeting}\n")
    if not speak_sample('greeting'):
        speak(greeting)

    while True:
        try:
            source, value = _wait_for_input()

            if source == 'voice':
                console.print(f'  [{C_MUTED}]heard:[/] [{C_WHITE}]"{value}"[/]')
                handle_message(value)

            else:  # keyboard
                raw = value

                if raw.lower() in ('quit', 'exit', 'q', 'bye'):
                    farewell = 'Goodbye, Shrey.'
                    console.print(f"\n  [{C_SCAN}]◈[/] {farewell}\n")
                    speak(farewell)
                    break

                if raw.lower() == 'reset':
                    reset()
                    msg = 'Memory cleared.'
                    console.print(f"\n  [{C_SCAN}]◈[/] {msg}\n")
                    speak(msg)
                    continue

                if raw == '':
                    continue

                handle_message(raw)

        except KeyboardInterrupt:
            console.print(f'\n  [{C_MUTED}]Interrupted.[/]\n')
            speak('Goodbye.')
            break

        except Exception as e:
            console.print(f'\n  [{C_MUTED}]Error:[/] {e}\n')


if __name__ == '__main__':
    run()
