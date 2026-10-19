# -*- coding: utf-8 -*-
# Crée un raccourci "Facturation" sur le bureau avec l'icône de l'app.
# Usage :
#   powershell -ExecutionPolicy Bypass -File creer_raccourci.ps1 -Exe "C:\Facturation\Facturation.exe"

param(
    [string]$Exe = "",
    [string]$Icone = "",
    [string]$Nom = "Facturation v4"
)

if (-not $Exe) {
    $Exe = Join-Path $PSScriptRoot "dist\Facturation.exe"
}
if (-not $Icone) {
    $Icone = Join-Path $PSScriptRoot "assets\icone.ico"
}

if (-not (Test-Path -LiteralPath $Exe)) {
    Write-Error "Exe introuvable : $Exe"
    exit 1
}

$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcut = $ws.CreateShortcut((Join-Path $desktop "$Nom.lnk"))
$shortcut.TargetPath = $Exe
$shortcut.WorkingDirectory = Split-Path $Exe
if (Test-Path -LiteralPath $Icone) {
    $shortcut.IconLocation = $Icone
}
$shortcut.Description = "Facturation v4 - Application"
$shortcut.Save()

Write-Output "Raccourci créé : $desktop\$Nom.lnk"
