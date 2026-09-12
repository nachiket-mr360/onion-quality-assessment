@echo off
cd /d "%~dp0"
echo.
echo Onion quality demo
echo 1. On the phone, start IP Webcam.
echo 2. Video URL default: http://192.168.167.38:8080/video
echo 3. Point the camera at onions. SPACE = freeze + report. Q = quit.
echo.
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Use the project Python venv.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "cv\demo.py" --preview
echo.
pause
