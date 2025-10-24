@echo off
echo ==============================
echo  Starting Hedera Service
echo ==============================

:: Go to the hedera_service folder
cd /d %~dp0..\..\hedera_service

:: Check if node_modules exists
if not exist node_modules (
    echo  Installing dependencies...
    npm install
)

echo  Starting Hedera service...
npm run start

pause
