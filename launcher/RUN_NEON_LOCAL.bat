@echo off
echo 🚀 Starting Neon (Local Mode)

REM ---- START GPT-SoVITS TTS ----
start cmd /k "title GPT-SoVITS TTS && cd /d D:\GPT-SoVITS && python api_v2.py"

REM ---- WAIT A BIT ----
timeout /t 5 > nul

REM ---- START NEON MAIN ----
start cmd /k "title Neon Main && cd /d D:\neon && python main.py"

echo ✅ Neon Local Mode Started
