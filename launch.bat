@echo off
setlocal enabledelayedexpansion

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

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -c "import textual, rich, requests, tomli_w, bs4, numpy" >nul 2>&1
    if not errorlevel 1 set "PY=%~dp0.venv\Scripts\python.exe"
)

if not defined PY (
    python --version >nul 2>&1
    if not errorlevel 1 (
        for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "pyver=%%v"
        for /f "tokens=1,2 delims=." %%a in ("!pyver!") do (
            set "pymaj=%%a"
            set "pymin=%%b"
        )
        if !pymaj! GEQ 3 if !pymin! GEQ 11 set "PY=python"
    )
)

REM --- Aucun interpréteur utilisable : on installe le nôtre ---
if not defined PY (
    echo.
    echo  [INFO] Aucun Python 3.11+ utilisable — installation de l'environnement.
    echo  Aucun droit administrateur n'est requis ; tout est écrit dans ce dossier.
    echo.
    where powershell >nul 2>&1
    if errorlevel 1 (
        echo  [ERREUR] PowerShell est introuvable, l'installation automatique
        echo  ne peut pas se faire. Installez Python 3.11+ manuellement :
        echo  https://www.python.org/downloads/
        pause
        exit /b 1
    )
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
    if errorlevel 1 (
        echo.
        echo  [ERREUR] L'installation de l'environnement a échoué.
        pause
        exit /b 1
    )
    set "PY=%~dp0.venv\Scripts\python.exe"
)

REM --- Avertissement terminal (Windows Terminal recommandé) ---
echo %WT_SESSION% >nul 2>&1
if "%WT_SESSION%"=="" (
    echo.
    echo  [INFO] Rendu optimal avec Windows Terminal ^(store.microsoft.com^).
    echo  Le terminal actuel peut afficher des artefacts graphiques.
    echo.
)

REM --- Dépendances : l'interpréteur du PATH peut en manquer ---
REM Le .venv a déjà été vérifié plus haut ; ce cas ne concerne que le Python
REM du système. La liste doit suivre requirements.txt : un module oublié ici
REM ne déclenche pas l'installation, et main.py s'arrête ensuite dessus.
"%PY%" -c "import textual, rich, requests, tomli_w, bs4, numpy" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [INFO] Dépendances manquantes — installation en cours...
    "%PY%" -m pip install -q -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo.
        echo  [INFO] pip a échoué — bascule sur l'environnement isolé.
        powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
        if errorlevel 1 (
            echo  [ERREUR] Impossible de préparer un environnement Python.
            pause
            exit /b 1
        )
        set "PY=%~dp0.venv\Scripts\python.exe"
    )
    echo.
)

REM --- Bandeau, une fois l'interpréteur connu ---
REM Version lue dans version.py : la coder en dur ici la dupliquerait, et les
REM deux finiraient par diverger. main.py affiche la même source.
set "APPVER="
REM Les `^"` encadrants : sans eux, `for /f` casse une commande dont
REM l'exécutable *et* l'argument sont entre guillemets, et APPVER reste vide.
for /f "usebackq delims=" %%v in (`^""%PY%" -c "import sys;sys.path.insert(0,r'%~dp0.');from version import __version__;print(__version__)" 2^>nul^"`) do set "APPVER=%%v"
if defined APPVER (
    title IRIS ENCODE v%APPVER%
    echo  IRIS ENCODE v%APPVER%
) else (
    echo  IRIS ENCODE
)
echo.

REM --- Nettoyage des caches .pyc (évite les conflits après mise à jour) ---
cd /d "%~dp0"
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d" >nul 2>&1
)

REM --- Lancement depuis le dossier du script (portabilité clé USB) ---
"%PY%" main.py %*

if errorlevel 1 (
    echo.
    echo  [ERREUR] IRIS ENCODE s'est terminé avec une erreur.
    pause
)

endlocal
