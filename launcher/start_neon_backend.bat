@echo off
title Neon Backend
cd /d D:\neon\NEON-FRONTEND\backend
uvicorn server:app --host 0.0.0.0 --port 9000
pause
