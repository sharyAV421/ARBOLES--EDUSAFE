@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Creando el entorno virtual local...
    py -3 -m venv "%~dp0.venv"
    if errorlevel 1 goto setup_failed
)

"%PYTHON%" -c "import fastapi, uvicorn, pytest, httpx" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias desde requirements.txt...
    "%PYTHON%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 goto setup_failed
)

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue) { exit 1 }"
if errorlevel 1 (
    echo El puerto 8001 ya esta ocupado. Cierre el servicio que lo usa y vuelva a ejecutar start.bat.
    pause
    exit /b 1
)

start "EduSafe - servidor local" /D "%~dp0" "%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8001
set /a attempts=0
:wait_for_server
curl.exe --silent --fail http://127.0.0.1:8001/api/scenarios >nul
if not errorlevel 1 goto server_ready
set /a attempts+=1
if %attempts% geq 20 goto server_failed
timeout /t 1 /nobreak >nul
goto wait_for_server

:server_ready
echo EduSafe esta disponible en http://127.0.0.1:8001
start "" http://127.0.0.1:8001
exit /b 0

:server_failed
echo No se pudo iniciar EduSafe. Revise la ventana del servidor y las instrucciones de README.md.
pause
exit /b 1

:setup_failed
echo No se pudo preparar Python o instalar las dependencias. Consulte README.md.
pause
exit /b 1

