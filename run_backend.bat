@echo off
echo ==============================
echo 🚀 Lancement du backend Django
echo ==============================

cd solidavenir
if not exist venv (
    echo 📦 Création de l'environnement virtuel...
    python -m venv venv
)

call venv\Scripts\activate

pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate

echo 👤 Vérification du superuser...
python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); \
if not User.objects.filter(username='admin').exists(): \
    print('Création du superuser...'); \
    User.objects.create_superuser(username='admin', email='admin@solidavenir.com', password='changeMe123!', user_type='admin'); \
    print('✅ Superuser créé !'); \
else: \
    print('ℹ️ Superuser existe déjà');"

echo ✅ Backend Django prêt sur http://localhost:8000
python manage.py runserver
