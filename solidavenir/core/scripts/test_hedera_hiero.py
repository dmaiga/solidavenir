# scripts/test_hedera_hiero.py
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solidAvenir.settings')
django.setup()

from services.hedera_hiero_service import HederaHieroService

def test_hedera_connection():
    """Teste la connexion à Hedera avec Hiero"""
    try:
        service = HederaHieroService()
        
        # Test de solde du compte opérateur
        balance = service.get_account_balance(settings.HEDERA_OPERATOR_ID)
        print(f"✅ Connexion réussie! Solde opérateur: {balance} HBAR")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return False

if __name__ == "__main__":
    test_hedera_connection()