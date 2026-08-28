<#
.SYNOPSIS
    IRIS ENCODE — installe l'environnement Python, sans droits administrateur.

.DESCRIPTION
    Le prérequis Python était le seul que l'application ne savait pas satisfaire
    elle-même : ffmpeg, mkvmerge et dovi_tool sont déjà téléchargés dans `bin/`
    par `core/preflight.py`, sans droits admin ni modification du PATH. Python
    faisait exception pour une raison mécanique — `preflight.py` est du Python,
    et ne peut donc pas s'exécuter avant lui.

    Ce script est cette exception, écrite hors de Python. Il suit la même
    convention que le reste de l'outillage :

      1. `uv` — un exécutable unique, téléchargé dans `bin/` depuis GitHub ;
      2. un CPython, que `uv` va chercher lui-même, installé sous `bin/python/` ;
      3. un environnement `.venv/` local, garni depuis `requirements.txt`.

    Tout tient dans le dossier de l'application : rien n'est écrit ailleurs, rien
    n'est ajouté au PATH, et une copie sur clé USB reste une copie complète —
    la portabilité que `launch.bat` protège depuis l'origine.

    Le script est **idempotent** : relancé, il constate et ne retélécharge rien.

.PARAMETER Force
    Reconstruit l'environnement même s'il paraît complet.

.NOTES
    Compatible Windows PowerShell 5.1 — présent sur toute installation Windows
    supportée. Ne pas y introduire de syntaxe PowerShell 7.
#>
[CmdletBinding()]
param(
    [switch] $Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# TLS 1.2 : Windows PowerShell 5.1 négocie encore TLS 1.0 par défaut sur
# certaines installations, et github.com le refuse depuis 2018.
[Net.ServicePointManager]::SecurityProtocol = `
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$Racine  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BinDir  = Join-Path $Racine 'bin'
$PyDir   = Join-Path $BinDir 'python'
$VenvDir = Join-Path $Racine '.venv'
$UvExe   = Join-Path $BinDir 'uv.exe'
$VenvPy  = Join-Path $VenvDir 'Scripts\python.exe'

# La version demandée à uv. Le projet exige 3.11 ; on installe 3.12, stable et
# encore soutenue, plutôt que « la plus récente » — une version fraîche casse
# régulièrement une roue binaire, et numpy en fournit une pour 3.12.
$PythonDemande = '3.12'

function Dire([string] $texte, [string] $couleur = 'Gray') {
    Write-Host "  $texte" -ForegroundColor $couleur
}

function Test-EnvComplet {
    if (-not (Test-Path $VenvPy)) { return $false }
    # Un venv peut exister et lui manquer une dépendance : une installation
    # interrompue laisse exactement cet état. On vérifie ce qui compte —
    # que les modules s'importent — plutôt que la seule présence du dossier.
    & $VenvPy -c "import textual, rich, requests, tomli_w, bs4, numpy" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

# ── 0. Rien à faire ? ─────────────────────────────────────────────────────────

if (-not $Force -and (Test-EnvComplet)) {
    Dire "Environnement Python déjà en place." 'DarkGray'
    exit 0
}

Write-Host ''
Write-Host '  IRIS ENCODE — installation de l''environnement Python' -ForegroundColor Cyan
Write-Host '  Aucun droit administrateur requis. Tout est écrit sous :' -ForegroundColor DarkGray
Write-Host "  $Racine" -ForegroundColor DarkGray
Write-Host ''

# ── 1. uv — un exécutable unique ──────────────────────────────────────────────

if (-not (Test-Path $UvExe)) {
    # L'architecture décide de l'archive. `PROCESSOR_ARCHITECTURE` vaut encore
    # AMD64 dans un processus 32 bits lancé depuis un hôte 64 bits, d'où le
    # recours à la variable que Windows réserve à ce cas.
    $arch = $env:PROCESSOR_ARCHITEW6432
    if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
    switch ($arch) {
        'ARM64' { $cible = 'aarch64-pc-windows-msvc' }
        'AMD64' { $cible = 'x86_64-pc-windows-msvc'  }
        default { $cible = 'i686-pc-windows-msvc'    }
    }
    $url = "https://github.com/astral-sh/uv/releases/latest/download/uv-$cible.zip"
    $zip = Join-Path $env:TEMP "uv-$cible.zip"

    Dire "Téléchargement de uv ($cible)…" 'White'
    try {
        # `ProgressPreference` : la barre de progression d'Invoke-WebRequest
        # divise son débit par dix sur PowerShell 5.1. Bug connu, contournement
        # connu.
        $prog = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        $ProgressPreference = $prog
    } catch {
        Dire "Échec du téléchargement : $($_.Exception.Message)" 'Red'
        Dire "Vérifiez la connexion, ou installez uv à la main :" 'Yellow'
        Dire "  https://github.com/astral-sh/uv/releases" 'Yellow'
        exit 1
    }

    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    $extrait = Join-Path $env:TEMP "uv-extrait-$PID"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($zip, $extrait)
    # L'archive place uv.exe à la racine ou dans un sous-dossier selon la
    # version : on cherche plutôt que de supposer.
    $trouve = Get-ChildItem -Path $extrait -Filter 'uv.exe' -Recurse |
              Select-Object -First 1
    if (-not $trouve) {
        Dire "uv.exe absent de l'archive téléchargée." 'Red'
        exit 1
    }
    Copy-Item $trouve.FullName $UvExe -Force
    Remove-Item $zip, $extrait -Recurse -Force -ErrorAction SilentlyContinue
    Dire "uv installé : $UvExe" 'Green'
} else {
    Dire "uv déjà présent." 'DarkGray'
}

# ── 2. Un CPython, que uv va chercher lui-même ────────────────────────────────

# Sans cette variable, uv installe les interpréteurs sous %LOCALAPPDATA% : ils
# survivraient à la suppression du dossier, et manqueraient à une copie sur clé.
$env:UV_PYTHON_INSTALL_DIR = $PyDir

# Le cache de uv vit sous %LOCALAPPDATA%, sur C:. Une application posée sur un
# autre volume — une clé, un disque de travail — ne peut pas y créer de lien
# physique, et uv avertit à chaque paquet. La copie est le comportement voulu
# ici : c'est ce qui rend le dossier autonome.
$env:UV_LINK_MODE = 'copy'

Dire "Python $PythonDemande…" 'White'
& $UvExe python install $PythonDemande
if ($LASTEXITCODE -ne 0) {
    Dire "uv n'a pas pu installer Python $PythonDemande." 'Red'
    exit 1
}

# ── 3. L'environnement et ses dépendances ─────────────────────────────────────

if ($Force -and (Test-Path $VenvDir)) {
    Remove-Item $VenvDir -Recurse -Force
}

Dire "Environnement .venv…" 'White'
& $UvExe venv --python $PythonDemande $VenvDir
if ($LASTEXITCODE -ne 0) {
    Dire "Création de l'environnement impossible." 'Red'
    exit 1
}

Dire "Dépendances (requirements.txt)…" 'White'
& $UvExe pip install --python $VenvPy -r (Join-Path $Racine 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Dire "Installation des dépendances impossible." 'Red'
    exit 1
}

# ── 4. Vérifier plutôt que déduire ────────────────────────────────────────────

# Un code de retour nul ne prouve pas que l'application démarrera : c'est la
# leçon de `pistes_audio_vides`, et elle vaut ici aussi. On importe.
if (-not (Test-EnvComplet)) {
    Dire "L'environnement s'est construit mais une dépendance manque à l'appel." 'Red'
    Dire "Relancez avec -Force, ou signalez le cas." 'Yellow'
    exit 1
}

$v = (& $VenvPy --version) -join ''
Write-Host ''
Dire "Prêt — $v dans .venv" 'Green'
Write-Host ''
exit 0
