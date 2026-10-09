@echo off
REM Sans expansion retardée : avec elle, cmd efface tout « ! » d'un chemin
REM développé (« D:\Films!\IRIS ») et le .venv n'était jamais retrouvé (CR-108).
setlocal

REM ============================================================
REM  IRIS ENCODE — Lanceur Windows
REM  Vérifie Python 3.11+, délègue à main.py
REM ============================================================

REM Version lue dans version.py : la coder en dur ici la dupliquerait, et les
REM deux finiraient par diverger. main.py affiche la même source.
title IRIS ENCODE

REM ============================================================
REM  Choix de l'interpréteur, dans cet ordre :
REM    1. .venv local — celui que bootstrap.ps1 construit ;
REM    2. le Python du PATH, s'il est en 3.11+ ;
REM    3. bootstrap.ps1, qui installe uv, un CPython et le .venv.
REM
REM  Le .venv passe devant le Python du système : c'est le seul dont
REM  on connaisse les versions de dépendances. Un Python système qui
REM  convient évite le téléchargement, mais ne le remplace pas.
REM ============================================================

set "PY="

REM dependances.py compare les paquets installés aux bornes de
REM requirements.txt : un simple import laissait passer un Textual trop
REM ancien (CR-109).
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0dependances.py" >nul 2>&1
    if not errorlevel 1 set "PY=%~dp0.venv\Scripts\python.exe"
)

REM La version, c'est Python qui la juge : plus de découpage de
REM « python --version » par cmd, qui exigeait l'expansion retardée.
if not defined PY (
    python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

REM --- Aucun interpréteur utilisable : on installe le nôtre ---
if not defined PY (
    echo.
    echo  [INFO] No usable Python 3.11+ found - setting up the environment.
    echo  No administrator rights needed; everything is written to this folder.
    echo.
    where powershell >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] PowerShell not found, so the automatic setup cannot run.
        echo  Install Python 3.11+ manually:
        echo  https://www.python.org/downloads/
        pause
        exit /b 1
    )
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
    if errorlevel 1 (
        echo.
        echo  [ERROR] Environment setup failed.
        pause
        exit /b 1
    )
    set "PY=%~dp0.venv\Scripts\python.exe"
)

REM --- Avertissement terminal (Windows Terminal recommandé) ---
echo %WT_SESSION% >nul 2>&1
if "%WT_SESSION%"=="" (
    echo.
    echo  [INFO] Best rendering in Windows Terminal ^(store.microsoft.com^).
    echo  The current terminal may show graphical glitches.
    echo.
)

REM --- Dépendances : l'interpréteur du PATH peut en manquer ---
REM Le .venv a déjà été vérifié plus haut ; ce cas ne concerne que le Python
REM du système. pip ramène dans les bornes de requirements.txt un paquet
REM absent, trop ancien ou d'une version majeure jamais éprouvée.
"%PY%" "%~dp0dependances.py" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [INFO] Missing dependencies - installing...
    "%PY%" -m pip install -q -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo.
        echo  [INFO] pip failed - switching to the isolated environment.
        powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
        if errorlevel 1 (
            echo  [ERROR] Could not set up a Python environment.
            pause
            exit /b 1
        )
        set "PY=%~dp0.venv\Scripts\python.exe"
    )
    echo.
)

REM --- Mise à jour d'IRIS ENCODE, depuis la release GitHub « Latest » ---
REM updater.py demande confirmation (réglage [updates] app de config.toml) et
REM rend 10 s'il a remplacé les fichiers : on se relance alors sur la version
REM neuve, dépendances revérifiées. Hors ligne ou en échec, il rend 0.
REM
REM Tout tient dans UN SEUL bloc. cmd lit un .bat au fil de l'exécution, par
REM position dans le fichier : si la mise à jour remplace ce fichier-ci, la
REM suite serait lue dans le nouveau à l'ancienne position — un fragment de
REM ligne exécuté comme une commande (mesuré). Un bloc ( ) est lu en entier
REM avant de s'exécuter : la relance part de là, sans rien relire.
(
    "%PY%" "%~dp0updater.py"
    if errorlevel 10 if not errorlevel 11 (
        endlocal
        "%~f0" %*
        exit /b
    )
)

REM --- Bandeau, une fois l'interpréteur connu ---
REM Version lue dans version.py : la coder en dur ici la dupliquerait, et les
REM deux finiraient par diverger. main.py affiche la même source.
set "APPVER="
REM Les `^"` encadrants : sans eux, `for /f` casse une commande dont
REM l'exécutable *et* l'argument sont entre guillemets, et APPVER reste vide.
REM Le dossier passe par l'environnement, pas dans le code Python : une
REM apostrophe (« D:\Vidéos d'été ») y fermait la chaîne (CR-108).
set "IRIS_DIR=%~dp0."
for /f "usebackq delims=" %%v in (`^""%PY%" -c "import os,sys;sys.path.insert(0,os.environ['IRIS_DIR']);from version import __version__;print(__version__)" 2^>nul^"`) do set "APPVER=%%v"
if defined APPVER (
    title IRIS ENCODE v%APPVER%
    echo  IRIS ENCODE v%APPVER%
) else (
    echo  IRIS ENCODE
)
echo.

REM --- Lancement depuis le dossier du script (portabilité clé USB) ---
REM Plus de purge des __pycache__ : elle descendait dans .venv et faisait
REM recompiler toutes les dépendances à chaque lancement (CR-107). Python
REM invalide lui-même un .pyc dont la source a changé, et n'en charge
REM jamais un de __pycache__ sans sa source.
cd /d "%~dp0"
"%PY%" main.py %*

if errorlevel 1 (
    echo.
    echo  [ERROR] IRIS ENCODE exited with an error.
    pause
)

endlocal
