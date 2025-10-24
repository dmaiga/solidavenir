@echo off
echo ==============================
echo  Starting Django backend
echo ==============================

cd /d %~dp0..\..\solidavenir
if not exist venv (
    echo  Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate

pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate

echo  Checking for superuser...
python manage.py shell < create_superuser.py

echo  Django backend ready at http://localhost:8000
python manage.py runserver
