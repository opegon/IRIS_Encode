@echo off
setlocal

REM ============================================================
REM  IRIS ENCODE — Lanceur Windows
REM  Vérifie Python 3.11+, délègue à main.py
REM ============================================================

title IRIS ENCODE v0.6

echo  IRIS ENCODE v0.6
echo.

REM --- Vérification Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERREUR] Python est introuvable dans le PATH.
    echo  Téléchargez Python 3.11+ depuis : https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM --- Vérification version minimale (3.11) ---
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "pyver=%%v"
for /f "tokens=1,2 delims=." %%a in ("%pyver%") do (
    set "pymaj=%%a"
    set "pymin=%%b"
)
if %pymaj% LSS 3 (
    echo  [ERREUR] Python 3.11+ requis ^(détecté : %pyver%^).
    pause
    exit /b 1
)
if %pymaj% EQU 3 if %pymin% LSS 11 (
    echo  [ERREUR] Python 3.11+ requis ^(détecté : %pyver%^).
    pause
    exit /b 1
)

REM --- Avertissement terminal (Windows Terminal recommandé) ---
echo %WT_SESSION% >nul 2>&1
if "%WT_SESSION%"=="" (
    echo.
    echo  [INFO] Rendu optimal avec Windows Terminal ^(store.microsoft.com^).
    echo  Le terminal actuel peut afficher des artefacts graphiques.
    echo.
)

REM --- Vérification des dépendances Python ---
python -c "import textual, requests, tomli_w, bs4" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [INFO] Dépendances manquantes — installation en cours...
    pip install -q -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo.
        echo  [ERREUR] Impossible d'installer les dépendances.
        echo  Essayez manuellement : pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
    echo.
)

REM --- Nettoyage des caches .pyc (évite les conflits après mise à jour) ---
cd /d "%~dp0"
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" >nul 2>&1
)

REM --- Lancement depuis le dossier du script (portabilité clé USB) ---
python main.py %*

if errorlevel 1 (
    echo.
    echo  [ERREUR] IRIS ENCODE s'est terminé avec une erreur.
    pause
)

endlocal
