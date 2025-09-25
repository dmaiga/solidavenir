#!/bin/bash
echo "=============================="
echo "🚀 Lancement du backend Django"
echo "=============================="

cd "$(dirname "$0")/../../solidavenir"

# Créer venv si pas existant
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer le venv
source venv/bin/activate

# Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# Appliquer les migrations
python manage.py makemigrations
python manage.py migrate

# Créer superuser si nécessaire
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser(username="admin", email="admin@solidavenir.com", password="changeMe123!", user_type="admin")
    print("✅ Superuser créé !")
else:
    print("ℹ️ Superuser existe déjà")
EOF

# Lancer le serveur
python manage.py runserver
