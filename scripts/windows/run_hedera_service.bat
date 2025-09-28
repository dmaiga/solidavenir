@echo off
echo ==============================
echo  Lancement du service Hedera
echo ==============================

:: Aller dans le dossier hedera_service
cd /d %~dp0..\..\hedera_service

:: Vérifier si node_modules existe
if not exist node_modules (
    echo 📦 Installation des dépendances...
    npm install
)

echo ▶️ Démarrage du service Hedera...
npm run start

pause
