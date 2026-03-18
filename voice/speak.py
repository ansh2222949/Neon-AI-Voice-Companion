import requests
import sounddevice as sd
import soundfile as sf
import numpy as np
from io import BytesIO
import re
import os

# =========================
# ⚙️ CONFIGURATION
# =========================
API_URL = "http://127.0.0.1:9880/tts"

# Ref Audio (Make sure this path is 100% correct on your system)
REF_AUDIO_PATH = r"D:\neon\voice\neon.wav" 
REF_PROMPT_TEXT = "I used to take long walks in Silvermoon Hall every day, so don't worry about me. I can keep up."
REF_LANG = "en"

# Session for faster API calls (Keep-Alive)
session = requests.Session()

VOICE_STYLE = "default"
_VOICE_STYLE_PARAMS = {
    # Keep changes subtle; GPT-SoVITS can get unstable with extreme params.
    "default":   {"temperature": 1.0,  "speed_factor": 1.0,  "top_k": 10},
    "calm":      {"temperature": 0.9,  "speed_factor": 0.98, "top_k": 10},
    "energetic": {"temperature": 1.05, "speed_factor": 1.05, "top_k": 12},
    "soft":      {"temperature": 0.95, "speed_factor": 0.96, "top_k": 10},
}


def configure_voice_style(style: str) -> None:
    """Sets a persistent runtime voice style (loaded from memory prefs at startup)."""
    global VOICE_STYLE
    s = (style or "default").strip().lower()
    if s not in _VOICE_STYLE_PARAMS:
        s = "default"
    VOICE_STYLE = s

def _prepare_text(text: str) -> str:
    """
    TTS-safe text normalization for GPT-SoVITS.
    Ensures clean speech, no filler, no action narration.
    """
    if not text:
        return ""

    # 1. Remove actions: *laughs* OR (smiles)
    # This prevents the TTS from reading "(smiles)" out loud.
    text = re.sub(r"\*.*?\*", "", text)
    text = re.sub(r"\(.*?\)", "", text)

    # 2. Normalize smart quotes to standard quotes
    text = text.translate(str.maketrans({
        "’": "'", "‘": "'", "“": '"', "”": '"'
    }))

    # 3. Expand common contractions (Helps TTS pronunciation)
    contractions = {
        r"\bthat's\b": "that is",
        r"\bit's\b": "it is",
        r"\bi'm\b": "i am",
        r"\byou're\b": "you are",
        r"\bwe're\b": "we are",
        r"\bthey're\b": "they are",
        r"\bcan't\b": "cannot",
        r"\bwon't\b": "will not",
        r"\bdon't\b": "do not",
        r"\bi've\b": "i have",
        r"\bi'll\b": "i will",
        r"\bu\b": "you",  # SMS slang fix
        r"\br\b": "are",  # SMS slang fix
    }

    for pattern, replacement in contractions.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 4. Cleanup whitespace
    text = re.sub(r"\s+", " ", text).strip()
    
    if not text:
        return ""

    # 5. Length guard (keeps TTS snappy)
    # Prevents latency spikes if LLM hallucinates a huge paragraph
    if len(text) > 300:
        text = text[:300]

    # 6. Smart Silent Anchor
    # Only add the dot if the sentence starts with a Letter (A-Z).
    # If it starts with "..." or "!" or "?", we don't add it.
    if re.match(r"^[A-Za-z]", text):
        text = ". " + text

    return text

def speak(text: str):
    """
    Synthesizes speech and plays it immediately.
    Blocking Mode: True (Prevents bot from listening to itself).
    """
    
    # 1. Pre-Check
    clean_text = _prepare_text(text)
    if not clean_text:
        return

    # Check if reference audio exists to avoid API 500 errors
    if not os.path.exists(REF_AUDIO_PATH):
        print(f"[ERROR] [Neon VOICE] Reference audio not found at {REF_AUDIO_PATH}")
        return

    # 2. API Payload (Optimized Parameters)
    style = _VOICE_STYLE_PARAMS.get(VOICE_STYLE, _VOICE_STYLE_PARAMS["default"])
    payload = {
        "text": clean_text,
        "text_lang": "en",
        "ref_audio_path": REF_AUDIO_PATH,
        "prompt_lang": REF_LANG,
        "prompt_text": REF_PROMPT_TEXT,
        "text_split_method": "cut0",      # 'cut0' is best for short conversational sentences
        "top_k": style["top_k"],          # Slightly style-dependent
        "top_p": 1.0,
        "temperature": style["temperature"],
        "repetition_penalty": 1.35,       # Increased to prevent stuttering
        "speed_factor": style["speed_factor"],
        "fragment_interval": 0.3,
        "media_type": "wav"
    }

    try:
        # 3. Request TTS
        response = session.post(API_URL, json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"[WARN] [Neon VOICE] API Error {response.status_code}: {response.text}")
            return

        # 4. Process Audio
        audio_data = BytesIO(response.content)
        audio, sr = sf.read(audio_data, dtype="float32")

        # Stereo to Mono conversion (if needed)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # 5. Audio Padding (Hardware Warmup + Cutoff Prevention)
        # 0.25s silence at START (Wake up speakers)
        # 0.1s silence at END (Prevent trailing cut-off)
        start_silence = np.zeros(int(sr * 0.25), dtype=np.float32)
        end_silence = np.zeros(int(sr * 0.1), dtype=np.float32)
        
        final_audio = np.concatenate([start_silence, audio, end_silence])

        # 6. Playback (Blocking)
        sd.play(final_audio, sr)
        sd.wait()

    except requests.exceptions.ConnectionError:
        print("[ERROR] [Neon VOICE] Connection refused. Is GPT-SoVITS running?")
    except Exception as e:
        print(f"[ERROR] [Neon VOICE] Critical error: {e}")

# Test run (optional)
if __name__ == "__main__":
    # Test case: Action removal and smart anchor
    speak("(smiles) This is much better. No weird brackets in my voice.")