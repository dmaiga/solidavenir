@echo off
echo ==============================
echo 🚀 Lancement du backend Django
echo ==============================

cd /d %~dp0..\..\solidavenir
if not exist venv (
    echo 📦 Création de l'environnement virtuel...
    python -m venv venv
)

call venv\Scripts\activate

pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate

echo 👤 Vérification du superuser...
python manage.py shell < create_superuser.py

echo ✅ Backend Django prêt sur http://localhost:8000
python manage.py runserver
