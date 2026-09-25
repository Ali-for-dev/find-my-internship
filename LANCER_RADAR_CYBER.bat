@echo off
chcp 65001 > nul
title CyberStage Radar - Veille Stages Cybersécurité France
color 0b

echo ==============================================================================
echo           🛡️  CYBERSTAGE RADAR - VEILLE STAGES CYBERSÉCURITÉ FRANCE 🛡️
echo ==============================================================================
echo.
echo  Bienvenue ! Choisissez le mode d'exécution :
echo.
echo   [1] Scan immédiat + Ouvrir le Dashboard Web interactif (Recommandé)
echo   [2] Mode surveillance continue (Scan automatique toutes les 30 minutes)
echo   [3] Ouvrir directement le Dashboard Web (sans rescanner)
echo   [4] Ouvrir le fichier de configuration (config.json)
echo   [5] Quitter
echo.
echo ==============================================================================
set /p choice="Votre choix (1, 2, 3, 4 ou 5) : "

if "%choice%"=="1" (
    echo.
    echo [*] Lancement du scan immédiat sur LinkedIn, HelloWork et France Travail...
    python cyber_radar.py --now --open
    pause
    exit /b
)

if "%choice%"=="2" (
    echo.
    echo [*] Démarrage de la surveillance continue en arrière-plan...
    echo [*] Vous recevrez une alerte Windows dès qu'un nouveau stage est publié !
    echo [*] Appuyez sur Ctrl+C pour arrêter la surveillance.
    echo.
    python cyber_radar.py --daemon
    pause
    exit /b
)

if "%choice%"=="3" (
    if exist stages_cyber_dashboard.html (
        echo [*] Ouverture du Dashboard...
        start stages_cyber_dashboard.html
    ) else (
        echo [!] Aucun scan n'a encore été réalisé. Lancement d'un premier scan...
        python cyber_radar.py --now --open
        pause
    )
    exit /b
)

if "%choice%"=="4" (
    start notepad config.json
    exit /b
)

if "%choice%"=="5" (
    exit /b
)

echo Choix invalide.
pause
