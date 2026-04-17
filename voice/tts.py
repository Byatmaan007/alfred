"""
Text-to-Speech for Alfred.
Uses edge-tts (Microsoft neural voices) — free, no API key required.
"""

import asyncio
import os
import re
import tempfile
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pygame")
warnings.filterwarnings("ignore", message=".*pkg_resources.*deprecated.*")

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
import edge_tts

VOICE = os.getenv("EDGE_TTS_VOICE", "en-NG-AbeoNeural")

pygame.mixer.init()


def set_voice(voice_name: str) -> None:
    """Change the TTS voice at runtime."""
    global VOICE
    VOICE = voice_name


def _clean(text: str) -> str:
    """Strip markdown that sounds odd when read aloud."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"`(.+?)`",       r"\1", text)
    text = re.sub(r"#+\s*",         "",    text)
    text = text.replace("_", " ")
    return text.strip()


async def _speak_async(text: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = f.name
    try:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(tmp)
        pygame.mixer.music.load(tmp)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    finally:
        pygame.mixer.music.unload()
        try:
            os.unlink(tmp)
        except OSError:
            pass


def speak(text: str) -> None:
    """Speak text aloud. Blocks until complete."""
    clean = _clean(text)
    if not clean:
        return
    asyncio.run(_speak_async(clean))


def speak_sample(key: str) -> bool:
    """Stub — no pre-recorded samples."""
    return False
