<div align="center"> <h1>🚀 Neon – AI Voice Companion</h1> <h3>Local-First • Voice-Driven • Experimental AI System</h3>

<p> <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python Version"> <img src="https://img.shields.io/badge/LLM-Ollama-orange?style=for-the-badge" alt="Ollama"> <img src="https://img.shields.io/badge/Voice-GPT--SoVITS-ff69b4?style=for-the-badge" alt="GPT-SoVITS"> <img src="https://img.shields.io/badge/Architecture-Offline%20First-green?style=for-the-badge" alt="Offline First"> </p>

<p> <b>Mode-Driven Intelligence • Privacy Focused • System > Model</b> </p>

🧠 What Is Neon?
Neon is a local-first AI voice companion designed to run primarily on your own machine using a fully local LLM pipeline, with optional and tightly controlled online access.

What started as an experiment evolved into a complete AI system architecture featuring:

🎭 Emotion-Aware Responses (Internal state affects tone).

🧠 Persistent Memory & Context awareness.

🗣️ Real-Time Voice (Whisper Input + GPT-SoVITS Output).

⚡ Dual Input Mode (Seamless Text & Voice switching).

⚠️ This is not a chatbot wrapper. Neon is an AI system, not just a model interface.

✨ Core Philosophy
🧠 Local LLM First — No mandatory cloud LLM APIs.

🔒 Privacy-Focused — All data stays on the user’s machine.

🎯 Mode-Driven Intelligence — Behavior changes based on context.

🧪 Experimental by Design — Built for system-level exploration.

🧩 System > Model — The LLM is a tool, not the decision-maker.

🎙️ Core Capabilities
🎤 Voice Input via Faster-Whisper (Offline STT with VAD).

🔊 Voice Output via GPT-SoVITS (High-Quality Custom TTS).

🧠 Local LLM via Ollama (Mistral / Llama based).

😐 Emotion Engine — Determines mood based on conversation context.

🔌 Offline-First Operation — Works completely without internet.

🧱 System Architecture
Key Principle: The LLM never directly controls responses. All outputs pass through emotion analysis, rule constraints, and post-processing filters.

Code snippet
graph TD;
    User((User)) -- Voice/Text --> Input_Handler;
    Input_Handler -- Audio --> Whisper_STT;
    Whisper_STT -- Text --> Neon_Brain;
    
    subgraph BRAIN_CORE
        Neon_Brain --> Emotion_Engine;
        Emotion_Engine --> Context_Memory;
        Context_Memory --> Local_LLM;
    end
    
    Local_LLM -- Response --> Post_Process;
    Post_Process -- Text --> GPT_SoVITS_TTS;
    GPT_SoVITS_TTS -- Audio --> Speakers;
📂 Project Structure
Plaintext
Neon/
│
├── main.py                     # Application entry point (Dual Input)
├── requirements.txt            # Dependencies
│
├── brain/                      # LLM interaction + Logic
│   ├── core.py                 # Main Intelligence Pipeline
│   ├── prompt.py               # Dynamic System Prompts
│   └── llm.py                  # Ollama Interface
│
├── core/                       # Emotion & Safety
│   └── emotion.py              # Emotion State Machine
│
├── memory/                     # Persistent Local Storage
│   └── manager.py              # JSON/Vector Memory
│
├── voice/                      # Audio I/O System
│   ├── hear.py                 # Whisper (STT) with VAD
│   ├── speak.py                # GPT-SoVITS (TTS) + Audio Playback
│   ├── set_model.py            # Model Loader
│   └── set_reference.py        # Voice Cloning Setup
│
└── .gitignore                  # Runtime & private data ignored
▶️ How To Run
1️⃣ Requirements
Python 3.10+

Ollama installed & running.

GPT-SoVITS API running locally (Port 9880).

2️⃣ Install Dependencies
Bash
pip install -r requirements.txt
3️⃣ Start Neon
Bash
python main.py
Neon will start in Interactive Mode. You can Type text OR press Enter to Speak.

🧪 Project Status
✅ Core system functional.

✅ Voice input (Whisper) & output (SoVITS) working.

✅ Emotion & memory pipeline stable.

⚠️ Experimental (Architecture locked for iteration).

⚠️ Disclaimer
This is an experimental project built for learning, research, and AI system design exploration. It is not a commercial product.

<div align="center"> <h3>🧠 Author</h3> <b>Ansh</b>


<i>B.Tech CSE</i>



<b>Focus Areas:</b>


AI Systems (not just models) • Offline-First Architecture • Controlled & Safe AI Design



<i>"Neon is not about how smart the model is. It’s about how controlled, safe, and purposeful AI should be."</i> </div>
