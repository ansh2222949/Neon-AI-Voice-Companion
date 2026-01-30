# voice/set_model.py
import requests
import os

GPT_API = "http://127.0.0.1:9880/set_gpt_weights"
SOVITS_API = "http://127.0.0.1:9880/set_sovits_weights"

GPT_MODEL = r"D:\GPT-SoVITS\GPT_SoVITS\pretrained_models\s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt"
SOVITS_MODEL = r"D:\GPT-SoVITS\GPT_SoVITS\pretrained_models\s2G488k.pth"

def set_models():
    if not os.path.exists(GPT_MODEL):
        print("[MODEL ERROR] GPT model not found:", GPT_MODEL)
        return

    if not os.path.exists(SOVITS_MODEL):
        print("[MODEL ERROR] SoVITS model not found:", SOVITS_MODEL)
        return

    try:
        # 🔹 Set GPT model
        print("[MODEL] Setting GPT model...")
        r1 = requests.get(
            GPT_API,
            params={"weights_path": GPT_MODEL},
            timeout=60
        )
        r1.raise_for_status()
        print("✅ GPT model set")

        # 🔹 Set SoVITS model
        print("[MODEL] Setting SoVITS model...")
        r2 = requests.get(
            SOVITS_API,
            params={"weights_path": SOVITS_MODEL},
            timeout=60
        )
        r2.raise_for_status()
        print("✅ SoVITS model set")

    except Exception as e:
        print("[MODEL ERROR]", e)

if __name__ == "__main__":
    set_models()
