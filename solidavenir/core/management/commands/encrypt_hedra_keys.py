# core/management/commands/encrypt_hedra_keys.py
from django.core.management.base import BaseCommand
from core.models import Projet
from core.utils.crypto import encrypt_value
from django.db import transaction

class Command(BaseCommand):
    help = "Chiffre les hedera_private_key existantes dans hedera_private_key_encrypted"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Ne pas modifier la DB, afficher seulement ce qui serait fait.")
        parser.add_argument("--delete-old", action="store_true", help="Après chiffrement, efface le champ hedera_private_key en clair.")

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_old = options['delete_old']

        projets = Projet.objects.exclude(hedera_private_key__isnull=True).exclude(hedera_private_key__exact="")
        self.stdout.write(f"Projets à traiter: {projets.count()}")

        for p in projets:
            plain = p.hedera_private_key
            if not plain:
                continue
            token = encrypt_value(plain)
            self.stdout.write(f"[{p.id}] chiffrement prêt.")
            if not dry_run:
                with transaction.atomic():
                    p.hedera_private_key_encrypted = token
                    if delete_old:
                        p.hedera_private_key = ""
                    p.save(update_fields=['hedera_private_key_encrypted'] + (['hedera_private_key'] if delete_old else []))

        self.stdout.write("Terminé.")
