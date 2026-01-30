# voice/speak.py
import requests
import sounddevice as sd
import soundfile as sf
import numpy as np
from io import BytesIO
import re

# =========================
# CONFIG
# =========================
API_URL = "http://127.0.0.1:9880/tts"

# MUST match reference audio exactly
REF_AUDIO_PATH = r"D:\neon\voice\neon.wav"
REF_PROMPT_TEXT = " I used to take long walks in Silvermoon Hall every day, so don't worry about me. I can keep up."
REF_LANG = "en"

# Persistent session (faster, stable)
session = requests.Session()


def _prepare_text(text: str) -> str:
    """Clean + normalize text before TTS (prevents word cut)"""

    # Remove *actions*
    text = re.sub(r"\*.*?\*", "", text)

    # Normalize quotes
    text = (
        text.replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
    )

    # Expand contractions
    contractions = {
        "that's": "that is",
        "it's": "it is",
        "i'm": "i am",
        "you're": "you are",
        "we're": "we are",
        "they're": "they are",
        "can't": "cannot",
        "won't": "will not",
        "don't": "do not",
        "i've": "i have",
        "i'll": "i will",
    }

    lower = text.lower()
    for k, v in contractions.items():
        if k in lower:
            text = re.sub(k, v, text, flags=re.IGNORECASE)

    # Cleanup spaces
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    # Safety anchor (prevents first-word drop)
    if not text.lower().startswith(("well", "okay", "so")):
        text = "Well, " + text

    return text


def speak(text: str):
    """Generate and play TTS audio (NO animation, NO lip-sync)"""
    if not text or not text.strip():
        return

    text = _prepare_text(text)
    if not text:
        return

    payload = {
        "text": text,
        "text_lang": "en",
        "ref_audio_path": REF_AUDIO_PATH,
        "prompt_lang": REF_LANG,
        "prompt_text": REF_PROMPT_TEXT,
        "text_split_method": "cut0",
        "top_k": 15,
        "top_p": 0.9,
        "temperature": 0.85,
        "repetition_penalty": 1.25,
        "speed_factor": 0.8,
        "fragment_interval": 0.3,
        "media_type": "wav"
    }

    try:
        r = session.post(API_URL, json=payload, timeout=120)
        if r.status_code != 200:
            print("[Neon VOICE ERROR]", r.status_code, r.text)
            return

        # Load audio
        audio, sr = sf.read(BytesIO(r.content), dtype="float32")

        # Stereo → Mono
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        audio = audio.astype(np.float32)

        # 🔇 0.2s silence padding (speaker wake-up)
        silence = np.zeros(int(sr * 0.2), dtype=np.float32)
        audio = np.concatenate([silence, audio])

        # Blocking playback (stable)
        sd.play(audio, sr, blocking=True)

    except Exception as e:
        print("[Neon VOICE ERROR]", e)


