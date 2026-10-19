# -*- coding: utf-8 -*-
# ============================================================
#  CONSTRUCTION DE L'APPLICATION FACTURATION (.exe protégé)
# ------------------------------------------------------------
#  1. Compile le code en bytecode puis le chiffre avec le MOT DE
#     PASSE fourni (PBKDF2-HMAC-SHA256, 400 000 itAcrations)
#     -> aucun fichier .py source n'est prAcsent, aucune clAc lisible :
#        lecture du code protAcgAe (anti-vol de code)
#  2. PyInstaller  -> fige Python + Django + bundle chiffrAc en
#                     UN SEUL exe (marche SANS installer Python)
#  3. Copie des donnAces (db, GTK pour les PDF, media, logs)
#  4. Raccourci bureau avec icA'ne
#
#  Le mot de passe est dAcfini UNE SEULE FOIS ici (par dAfaut si non
#  prAcisA). La clA de dAchiffrement est embarquAe dans l'exe : plus de
#  saisie de mot de passe A chaque lancement, et dAplacer l'application
#  la fait fonctionner partout avec ce mASme mot de passe configurA.
#
#  Usage :
#    powershell -ExecutionPolicy Bypass -File construire_exe.ps1 [-MotDePasse "TonVraiMDP"]
# ============================================================

param([string]$MotDePasse = "", [switch]$Onedir)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

if (-not $MotDePasse) {
    $MotDePasse = 'jobs_test_1234'   # mot de passe par dAfaut (une seule fois)
    Write-Host "Mot de passe par defaut utilise : $MotDePasse" -ForegroundColor Yellow
}

if ($Onedir) {
    $dest   = Join-Path $root 'dist\Facturation'
    $exe    = Join-Path $dest 'Facturation.exe'
    $pyiArg = ''
    Write-Host "Mode : onedir (dossier $dest) - demarrage plus rapide (fichiers a chemin fixe, antivirus ne rescanne pas a chaque lancement)" -ForegroundColor Cyan
} else {
    $dest   = Join-Path $root 'dist'
    $exe    = Join-Path $dest 'Facturation.exe'
    $pyiArg = '--onefile'
    Write-Host "Mode : onefile (un seul exe $exe)" -ForegroundColor Cyan
}

Write-Host "==> 1/6 Installation de PyInstaller..." -ForegroundColor Cyan
python -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller a echoue" }

Write-Host "==> 2/6 Compilation + chiffrement du code avec le mot de passe..." -ForegroundColor Cyan
python crypter_code.py $MotDePasse
if ($LASTEXITCODE -ne 0) { throw "crypter_code a echoue" }

Write-Host "==> 3/6 Packaging (patience, quelques minutes)..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean $pyiArg --windowed `
    --name Facturation `
    --icon assets/icone.ico `
    --add-data "templates;templates" `
    --add-data "static;static" `
    --add-data "build_code;build_code" `
    --add-data "assets/icone.ico;assets" `
    --collect-all weasyprint `
    --collect-all pydyf `
    --collect-all tinycss2 `
    --collect-all cssselect2 `
    --collect-all tinyhtml5 `
    --collect-all Pyphen `
    --collect-all fontTools `
    --collect-all reportlab `
    --collect-all openpyxl `
    --collect-all num2words `
    --collect-all whitenoise `
    --hidden-import qrcode `
    --hidden-import requests `
    --hidden-import urllib3 `
    --hidden-import PIL.Image `
    --hidden-import cryptography `
    --hidden-import cffi `
    --hidden-import django `
    --hidden-import django.db.backends.mysql `
    --hidden-import mysqlclient `
    --hidden-import waitress `
    launcher.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a echoue" }

if (-not (Test-Path -LiteralPath $exe)) { throw "exe introuvable : $exe" }

Write-Host "==> 4/6 Copie des fichiers necessaires a cote de l'exe..." -ForegroundColor Cyan

# GTK3-Runtime (WeasyPrint -> PDF devis/facture) : obligatoire
$gtk = 'C:\Program Files\GTK3-Runtime Win64\bin'
if (Test-Path $gtk) {
    Copy-Item -Path (Join-Path $gtk '*') -Destination $dest -Recurse -Force
    Write-Host "    GTK copie (PDF)" -ForegroundColor DarkGray
} else {
    Write-Warning "GTK3-Runtime introuvable ! Les PDF WeasyPrint ne fonctionneront PAS sur le PC cible."
    Write-Warning "Installe-le depuis https://github.com/nicmav/gtk3-runtime/releases puis relance ce script."
}

# Base de donnees : Projet 2 utilise MySQL local (pas de fichier db a copier).
# Le launcher execute 'migrate' au demarrage (cree/met a jour la base MySQL).

# Dossiers media / logs
New-Item -ItemType Directory -Force -Path (Join-Path $dest 'media') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dest 'logs') | Out-Null

# Installateur (Setup.bat) + icone pour le raccourci de l'installe
if (Test-Path (Join-Path $root 'Setup.bat')) {
    Copy-Item (Join-Path $root 'Setup.bat') $dest -Force
}
if (Test-Path (Join-Path $root 'assets\icone.ico')) {
    Copy-Item (Join-Path $root 'assets\icone.ico') $dest -Force
}

Write-Host "==> 5/6 Creation du raccourci bureau..." -ForegroundColor Cyan
powershell -ExecutionPolicy Bypass -File (Join-Path $root 'creer_raccourci.ps1') -Exe $exe

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  TERMINE !" -ForegroundColor Green
Write-Host "  Exe : $exe" -ForegroundColor Green
Write-Host "  Raccourci 'Facturation' cree sur le bureau." -ForegroundColor Green
Write-Host "  Pour livrer : copie tout le dossier $dest vers le PC cible." -ForegroundColor Green
Write-Host "  Plus de saisie de mot de passe a chaque lancement : la cle est" -ForegroundColor Green
Write-Host "  embarquee dans l'exe, l'application se deplace avec le meme" -ForegroundColor Green
Write-Host "  mot de passe configure (defini une seule fois a la construction)." -ForegroundColor Green
Write-Host "  Aucun source .py ni cle lisible n'est present (anti-vol de code)." -ForegroundColor Green
Write-Host "  Compatible Windows 8, 10 et 11." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
