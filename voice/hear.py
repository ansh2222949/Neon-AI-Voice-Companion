from faster_whisper import WhisperModel
import numpy as np
import soundfile as sf
import speech_recognition as sr
import tempfile
import os

MODEL_SIZE = "base.en"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# Load the model once when the module imports
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)

def transcribe_file(file_path: str) -> str:
    """Transcribes an audio file on disk."""
    audio, sr_rate = sf.read(file_path)

    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    audio = audio.astype(np.float32)

    segments, _ = model.transcribe(
        audio,
        language="en",
        beam_size=5,
        vad_filter=True,
    )

    text = " ".join(seg.text for seg in segments).strip()

    # Faster Whisper sometimes hallucinates these common phrases in dead silence
    bad_outputs = {"", "you", "thank you", "thanks", "bye"}
    if text.lower() in bad_outputs:
        return ""

    return text

def listen() -> str:
    """Listens to the microphone dynamically and returns transcribed text."""
    recognizer = sr.Recognizer()
    
    with sr.Microphone() as source:
        # Quickly adapt to background noise
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        try:
            # timeout=5: Waits up to 5 seconds for you to start speaking
            # phrase_time_limit=15: Cuts you off after 15 seconds of talking
            audio_data = recognizer.listen(source, timeout=5, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            # Return empty string if no one spoke
            return ""

    # Create a temporary file to pass to your existing transcribe function
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
        temp_wav.write(audio_data.get_wav_data())
        temp_path = temp_wav.name

    try:
        # Transcribe the temp file
        text = transcribe_file(temp_path)
    finally:
        # Always clean up the temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return text