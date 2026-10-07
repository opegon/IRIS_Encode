@echo off
setlocal

REM ============================================================
REM  IRIS ENCODE — Compilation du lanceur IRIS_Encode.exe
REM
REM  Compile launcher\IrisEncodeLauncher.cs avec le csc.exe du
REM  .NET Framework 4.x, livré avec tout Windows 10/11 : rien à
REM  installer, aucun binaire tiers — le source du dépôt fait foi.
REM  Produit IRIS_Encode.exe à la racine du projet, puis propose
REM  d'en créer un raccourci sur le Bureau.
REM ============================================================

set "CSC="
if exist "%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not defined CSC if exist "%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not defined CSC (
    echo.
    echo  [ERROR] csc.exe not found. The .NET Framework 4.x ships with
    echo  Windows 10/11 - turn it on in "Optional features", or install
    echo  it: https://aka.ms/net48
    pause
    exit /b 1
)

REM Racine du projet : le parent de ce script, en chemin absolu.
for %%i in ("%~dp0..") do set "ROOT=%%~fi"

REM L'icône est versionnée en texte (iris.ico.b64) : le dépôt ne porte
REM aucun binaire. certutil, livré avec Windows, la décode sur place.
certutil -f -decode "%~dp0iris.ico.b64" "%~dp0iris.ico" >nul
if errorlevel 1 (
    echo.
    echo  [ERROR] Could not decode the icon ^(launcher\iris.ico.b64^).
    pause
    exit /b 1
)

"%CSC%" /nologo /target:winexe /win32icon:"%~dp0iris.ico" /reference:System.Windows.Forms.dll /out:"%ROOT%\IRIS_Encode.exe" "%~dp0IrisEncodeLauncher.cs"
if errorlevel 1 (
    echo.
    echo  [ERROR] Compilation failed.
    pause
    exit /b 1
)

echo.
echo  IRIS_Encode.exe created in:
echo  %ROOT%
echo.

choice /c YN /n /m "Create an 'IRIS ENCODE' shortcut on the Desktop? [Y/N] "
if errorlevel 2 goto :fin

powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\IRIS ENCODE.lnk'); $s.TargetPath = '%ROOT%\IRIS_Encode.exe'; $s.WorkingDirectory = '%ROOT%'; $s.Description = 'IRIS ENCODE'; $s.Save()"
if errorlevel 1 (
    echo  [ERROR] The shortcut could not be created. Right-click
    echo  IRIS_Encode.exe ^> "Send to" ^> "Desktop" does the same.
    pause
    exit /b 1
)
echo  Shortcut created on the Desktop.

:fin
pause
endlocal
