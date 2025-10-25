#!/bin/bash
set -e

echo "=============================="
echo "Preparing the Django backend environment"
echo "=============================="

# Go to the solidavenir folder
cd "$(dirname "$0")/../../solidavenir"

# Check if python3 is installed
if ! command -v python3 &> /dev/null
then
    echo " Python3 is not installed. Install it with: sudo apt install python3-full python3-venv python3-pip"
    exit 1
fi

# Create the virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo " Creating virtual environment..."
    python3 -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo " Installing dependencies..."
pip install -r requirements.txt

# Apply migrations
echo " Applying migrations..."
python manage.py makemigrations
python manage.py migrate

# Check and create the admin superuser if necessary
echo " Checking for superuser..."
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser(username="admin", email="admin@solidavenir.com", password="changeMe123!", user_type="admin")
    print("Superuser created!")
else:
    print("Superuser already exists")
EOF

echo " Backend ready! You can now start the server with ./run_backend.sh"
