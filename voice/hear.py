import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import time
import queue

# =========================
# CONFIGURATION
# =========================
MODEL_SIZE = "base.en"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

SAMPLE_RATE = 16000
BLOCK_SIZE = 4000
THRESHOLD = 0.02
SILENCE_LIMIT = 2.0
MAX_RECORD_TIME = 10.0  # 🔥 hard safety cap

print("⏳ Loading Whisper Model...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("✅ Whisper Loaded.")

def listen():
    """
    Smart microphone listener with silence detection.
    Returns clean transcribed text or empty string.
    """
    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, flush=True)
        q.put(indata.copy())

    print("\n🎙️ Listening... (Speak now)")

    audio_chunks = []
    silence_start = None
    speaking_started = False
    record_start = time.time()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=BLOCK_SIZE,
        callback=callback,
    ):
        while True:
            chunk = q.get()

            # RMS volume (stable)
            rms = np.sqrt(np.mean(chunk ** 2))

            if rms > THRESHOLD:
                speaking_started = True
                silence_start = None
            else:
                if speaking_started and silence_start is None:
                    silence_start = time.time()

            if speaking_started:
                audio_chunks.append(chunk)

            # Stop on silence
            if speaking_started and silence_start:
                if time.time() - silence_start > SILENCE_LIMIT:
                    break

            # 🔥 Hard stop safety
            if time.time() - record_start > MAX_RECORD_TIME:
                break

    if not audio_chunks:
        return ""

    # =========================
    # AUDIO PREP
    # =========================
    audio = np.concatenate(audio_chunks, axis=0).flatten()
    audio = audio.astype(np.float32)

    # Normalize audio
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio /= max_val

    # =========================
    # TRANSCRIBE
    # =========================
    segments, _ = model.transcribe(
        audio,
        language="en",
        beam_size=5,
        vad_filter=True,
    )

    text = " ".join(seg.text for seg in segments).strip()

    # =========================
    # HALLUCINATION FILTER
    # =========================
    bad_outputs = {
        "", "you", "thank you", "thank you.", "thanks", "bye"
    }

    if text.lower() in bad_outputs:
        return ""

    return text
