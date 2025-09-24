#!/bin/bash
set -e

echo "=== 🚀 Démarrage du déploiement Django ==="

# Attendre la DB
echo "⏳ Attente que Postgres soit prêt..."
until nc -z -v -w30 $POSTGRES_HOST $POSTGRES_PORT
do
  echo "⚠️  En attente de Postgres ($POSTGRES_HOST:$POSTGRES_PORT)..."
  sleep 1
done
echo "✅ Postgres est prêt !"

# Vérifier si des migrations manquent
echo "🔍 Vérification des migrations manquantes..."
if ! python manage.py makemigrations --check --dry-run; then
    echo "⚠️ Aucune migration trouvée, génération en cours..."
    python manage.py makemigrations --noinput
fi

# Appliquer les migrations
echo "📦 Application des migrations..."
python manage.py migrate --noinput

# Création du superuser
echo "👤 Vérification du superuser..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    print('Création du superuser...')
    User.objects.create_superuser(
        username='admin',
        email='admin@solidavenir.com',
        password='changeMe123!',
        user_type='admin'
    )
    print('✅ Superuser créé !')
else:
    print('ℹ️ Superuser existe déjà')
"

# Collecte des fichiers statiques
echo "📂 Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

echo "✅ Déploiement terminé avec succès !"

# Lancement du serveur de dev (tu peux remplacer par gunicorn pour la prod)
echo "🚀 Lancement du serveur Django (mode dev)..."
exec python manage.py runserver 0.0.0.0:8000
