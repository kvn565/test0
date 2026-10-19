@echo off
setlocal
chcp 65001 >nul
title Installation - Facturation

echo ============================================================
echo   Installation de l'application  FACTURATION
echo   (Facturation - gestion facturation, devis, stock)
echo ============================================================
echo.

set "SRC=%~dp0"
set "DEST=%LOCALAPPDATA%\Programs\Facturation"

if not exist "Facturation.exe" (
    echo ERREUR : ce programme doit etre lance depuis le dossier
    echo         qui contient Facturation.exe (le dossier dist/).
    echo.
    pause
    exit /b 1
)

echo [1/4] Copie des fichiers vers l'emplacement d'installation...
if not exist "%DEST%" mkdir "%DEST%"
xcopy /E /I /Y /Q "%SRC%*" "%DEST%\" >nul

echo [2/4] Creation du raccourci sur le bureau...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Facturation.lnk'); $s.TargetPath='%DEST%\Facturation.exe'; $s.WorkingDirectory='%DEST%'; $s.IconLocation='%DEST%\Facturation.exe,0'; $s.Description='Facturation - Facturation'; $s.Save()"

echo [3/4] Creation du raccourci dans le menu Demarrer...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$m=[Environment]::GetFolderPath('Programs'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($m+'\Facturation.lnk'); $s.TargetPath='%DEST%\Facturation.exe'; $s.WorkingDirectory='%DEST%'; $s.IconLocation='%DEST%\Facturation.exe,0'; $s.Description='Facturation - Facturation'; $s.Save()"

echo [4/4] Lancement de l'application...
start "" "%DEST%\Facturation.exe"

echo.
echo ============================================================
echo   Installation terminee !
echo.
echo   - Raccourci 'Facturation' cree sur le bureau.
echo   - L'application demarre maintenant :
echo       * patiente 10 a 30 secondes (premiere ouverture),
echo       * le code source est protege par mot de passe defini UNE SEULE
echo         FOIS par le proprietaire : plus de saisie a chaque lancement,
echo         et le mot de passe configure suit l'application partout.
echo       * l'application s'ouvre dans le navigateur.
echo   - Le code source n'est pas lisible (bytecode chiffre, anti-vol).
echo   - Ne ferme PAS la fenetre de controle tant que tu utilises
echo     l'application (elle arrete le serveur en arriere-plan).
echo   - Compatible Windows 8, 10 et 11.
echo ============================================================
echo.
timeout /t 10 >nul
exit /b 0
