@echo off
echo Starting Haovdim Bank Appointment and Verification Chatbot...

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0api_server.py"
) else (
    python "%~dp0api_server.py"
)

pause
