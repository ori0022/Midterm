@echo off
set /p password=Enter Admin Password: 
if "%password%"=="NotPoalim123" (
    echo Starting "Haovdim" Bank Admin Portal...
    python main.py --admin
) else (
    echo Incorrect password. Access denied.
)
pause
