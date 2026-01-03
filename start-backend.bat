@echo off
echo ============================================
echo 🐼 Demarrage du Backend ClaraVerse
echo ============================================
echo.

cd /d "%~dp0py_backend"

echo Verification des dependances...
pip show beautifulsoup4 >nul 2>&1
if errorlevel 1 (
    echo Installation de beautifulsoup4...
    pip install beautifulsoup4
)

echo.
echo ============================================
echo   Backend : http://localhost:5000
echo   Frontend: http://localhost:5173
echo ============================================
echo.
echo Endpoints disponibles:
echo   - /pandas-agent/status          : Status de l'agent
echo   - /pandas-agent/process         : Traitement des tables
echo   - /pandas-agent/process-all-tables : Traitement groupe de tables
echo   - /pandas-agent/test            : Test rapide
echo.
echo Appuyez sur Ctrl+C pour arreter le serveur
echo ============================================
echo.

python main.py --host 127.0.0.1 --port 5000

pause
