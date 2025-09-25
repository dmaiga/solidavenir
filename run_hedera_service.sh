#!/bin/bash
echo "=============================="
echo "🚀 Lancement du service Hedera"
echo "=============================="

cd hedera_service/src || exit
npm install
npm start
