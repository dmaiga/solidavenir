from django.core.management.base import BaseCommand
from core.services.hedera_service import MOCK_BALANCES, MOCK_ACCOUNTS

class Command(BaseCommand):
    help = 'Réinitialiser les données mock Hedera pour les tests'
    
    def handle(self, *args, **options):
        MOCK_BALANCES.clear()
        MOCK_ACCOUNTS.clear()
        self.stdout.write(
            self.style.SUCCESS('Données mock Hedera réinitialisées avec succès')
        )