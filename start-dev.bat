@echo off
echo ========================================
echo   Demarrage E-AUDIT (Frontend + Backend)
echo ========================================
echo.

:: Verifier si Python est installe
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH
    echo Installez Python depuis https://python.org
    pause
    exit /b 1
)

:: Installer les dependances Python si necessaire
echo [1/3] Verification des dependances Python...
cd py_backend
pip install -q pandas numpy fastapi uvicorn pydantic PyPDF2 python-dotenv python-multipart 2>nul
cd ..

:: Demarrer le backend Python en arriere-plan
echo [2/3] Demarrage du backend Python (port 5000)...
start "Backend Python" cmd /c "cd py_backend && python main.py"

:: Attendre que le backend demarre
timeout /t 3 /nobreak >nul

:: Demarrer le frontend
echo [3/3] Demarrage du frontend Vite...
echo.
echo ========================================
echo   Backend: http://localhost:5000
echo   Frontend: http://localhost:5173
echo   API Pandas: http://localhost:5000/pandas/analysis/complete
echo ========================================
echo.

npm run dev
