#!/bin/bash
set -e

echo "=============================="
echo "🚀 Starting Django Backend"
echo "=============================="

cd "$(dirname "$0")/../../solidavenir"

echo "📁 Current directory: $(pwd)"

# Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed!"
    echo "📦 Installing Python3..."
    sudo apt update && sudo apt install -y python3 python3-venv python3-pip
fi

echo "✅ Python3 version: $(python3 --version)"

# Clean and recreate virtual environment
echo "📦 Cleaning and creating virtual environment..."
rm -rf venv
python3 -m venv venv

# Verify creation
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ Virtual environment creation failed!"
    exit 1
fi

echo "✅ Virtual environment created"

# Activate
echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "✅ Virtual environment activated"

# Update pip
echo "🔄 Updating pip..."
python -m pip install --upgrade pip
echo "✅ Pip updated"

# Install dependencies
echo "📚 Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
else
    echo "❌ requirements.txt file not found"
    exit 1
fi

# Migrations
echo "🗃️ Applying migrations..."
python manage.py makemigrations
python manage.py migrate
echo "✅ Migrations applied"

# Superuser
echo "👤 Creating superuser..."
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@solidavenir.com", "changeMe123!", user_type="admin")
    print("✅ Superuser created!")
    print("   👤 admin / changeMe123!")
else:
    print("ℹ️ Superuser already exists")
EOF

# Start server
echo ""
echo "🌐 Starting Django server..."
echo "   📍 http://localhost:8000"
echo "   👤 admin / changeMe123!"
echo "=============================="
python manage.py runserver