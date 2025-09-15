#!/bin/bash
set -e 

echo "=== Démarrage du déploiement ==="

# Installation des dépendances
echo "📦 Installation des dépendances..."
pip install -r requirements.txt

# Application des migrations
echo "🗄️ Application des migrations..."
python manage.py migrate

# Création du superuser directement avec infos fixes
echo "👤 Vérification du superuser..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()

# Vérifie si le superuser existe déjà
if not User.objects.filter(username='admin').exists():
    print('Création du superuser...')
    User.objects.create_superuser(
        username='admin',
        email='dadi@solidavenir.com',
        password='changeMe123!',
        user_type='admin'
    )
    print('Superuser créé !')
else:
    print('Superuser existe déjà')
"

# Collecte des fichiers statiques
echo "📁 Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

echo "✅ Déploiement terminé avec succès !"
