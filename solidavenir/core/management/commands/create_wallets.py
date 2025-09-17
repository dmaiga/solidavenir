from django.core.management.base import BaseCommand
from core.models import User
from django.db import models
from django.utils import timezone
from datetime import date
from django.db.models import Sum
import uuid
import requests


class Command(BaseCommand):
    help = 'Crée des wallets Hedera pour les utilisateurs qui n\'en ont pas'
    
    def handle(self, *args, **options):
        users_without_wallet = User.objects.filter(
            models.Q(hedera_account_id__isnull=True) | 
            models.Q(hedera_account_id='') |
            models.Q(wallet_activated=False)
        )
        
        self.stdout.write(f"Création de wallets pour {users_without_wallet.count()} utilisateurs...")
    
        for user in users_without_wallet:
            try:
                if user.ensure_wallet():
                    self.stdout.write(f"✓ Wallet créé pour {user.username}")
                else:
                    self.stdout.write(f"✗ Échec pour {user.username}")
            except Exception as e:
                self.stdout.write(f"✗ Erreur pour {user.username}: {e}")
    