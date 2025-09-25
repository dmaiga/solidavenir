#!/bin/bash
set -e

echo "=============================="
echo "⚙️  Préparation de l'environnement backend Django"
echo "=============================="

# Aller dans le dossier solidavenir
cd "$(dirname "$0")/../../solidavenir"

# Vérifier si python3 est installé
if ! command -v python3 &> /dev/null
then
    echo "❌ Python3 n'est pas installé. Installez-le avec: sudo apt install python3-full python3-venv python3-pip"
    exit 1
fi

# Créer le virtual environment si inexistant
if [ ! -d "venv" ]; then
    echo "📦 Création du virtual environment..."
    python3 -m venv venv
fi

# Activer le virtual environment
source venv/bin/activate

# Mettre à jour pip
pip install --upgrade pip

# Installer les dépendances
echo "📦 Installation des dépendances..."
pip install -r requirements.txt

# Appliquer les migrations
echo "🗄️  Appliquer les migrations..."
python manage.py makemigrations
python manage.py migrate

# Vérifier et créer le superuser admin si nécessaire
echo "👤 Vérification du superuser..."
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser(username="admin", email="admin@solidavenir.com", password="changeMe123!", user_type="admin")
    print("✅ Superuser créé !")
else:
    print("ℹ️ Superuser existe déjà")
EOF

echo "✅ Backend prêt ! Vous pouvez maintenant démarrer le serveur avec ./run_backend.sh"
