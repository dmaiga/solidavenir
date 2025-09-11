from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from cryptography.fernet import Fernet
from django.conf import settings

User = get_user_model()

class Command(BaseCommand):
    help = 'Initialiser les données de développement'
    
    def handle(self, *args, **options):
        # Créer des comptes de test avec Hedera pré-configuré
        users_data = [
            {
                'username': 'donateur_test',
                'email': 'donateur@test.com',
                'password': 'test123',
                'user_type': 'donateur',
                'hedera_account_id': '0.0.dev12345',
                'hedera_private_key': 'dev_private_key_123'
            },
            {
                'username': 'porteur_test',
                'email': 'porteur@test.com',
                'password': 'test123',
                'user_type': 'porteur',
                'hedera_account_id': '0.0.dev67890',
                'hedera_private_key': 'dev_private_key_456'
            }
        ]
        
        for user_data in users_data:
            private_key = user_data.pop('hedera_private_key')
            hedera_account_id = user_data.pop('hedera_account_id')
            
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults=user_data
            )
            
            if created:
                user.set_password(user_data['password'])
                user.hedera_account_id = hedera_account_id
                user.set_hedera_private_key(private_key)
                user.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'Utilisateur {user.username} créé avec compte Hedera: {hedera_account_id}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Données de développement initialisées avec succès')
        )