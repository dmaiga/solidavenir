#!/bin/bash
set -e

echo "=============================="
echo "🚀 Lancement du service Hedera"
echo "=============================="

# Aller dans le dossier hedera_service/src
cd "$(dirname "$0")/../../hedera_service/src" || exit

# Installer les dépendances si besoin
if [ ! -d "node_modules" ]; then
    echo "📦 Installation des dépendances..."
    npm install
fi

# Lancer le service
echo "▶️ Démarrage du service Hedera..."
npm start
