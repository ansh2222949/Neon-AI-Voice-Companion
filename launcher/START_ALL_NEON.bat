@echo off
echo 🚀 Starting NEON AI SYSTEM...

start cmd /k call start_tts_server.bat
timeout /t 5 > nul

start cmd /k call start_neon_backend.bat
timeout /t 5 > nul

start cmd /k call start_ngrok.bat

echo ✅ NEON fully launched
