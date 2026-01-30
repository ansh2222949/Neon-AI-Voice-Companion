# voice/set_reference.py
import requests
import os

API_URL = "http://127.0.0.1:9880/set_refer_audio"

# ⚠️ MUST be relative to server root (D:\GPT-SoVITS)
REF_AUDIO = r"D:\neon\voice\neon.wav"

def set_reference():
    if not os.path.exists(REF_AUDIO):
        print("[REF ERROR] Reference file not found:", REF_AUDIO)
        return

    try:
        print("[REF] Setting reference voice...")
        r = requests.get(
            API_URL,
            params={"refer_audio_path": REF_AUDIO},
            timeout=60
        )
        r.raise_for_status()
        print("✅ Reference voice set successfully")

    except Exception as e:
        print("[REF ERROR]", e)

if __name__ == "__main__":
    set_reference()
