from django.core.management.base import BaseCommand
from core.models import Projet
import requests
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Créer un compte Hedera pour chaque projet existant sans wallet"

    def handle(self, *args, **kwargs):
        projets = Projet.objects.filter(hedera_account_id__isnull=True)
        self.stdout.write(f"🔎 {projets.count()} projets sans wallet trouvés")

        for projet in projets:
            try:
                response = requests.post("http://localhost:3001/create-wallet", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    projet.hedera_account_id = data.get("accountId")
                    projet.hedera_private_key = data.get("privateKey")
                    projet.save()

                    self.stdout.write(self.style.SUCCESS(
                        f"✅ Projet {projet.titre} → Wallet {projet.hedera_account_id}"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"❌ Erreur API pour projet {projet.titre} (status {response.status_code})"
                    ))

            except Exception as e:
                logger.error(f"Erreur création wallet projet {projet.id}: {str(e)}", exc_info=True)
                self.stdout.write(self.style.ERROR(
                    f"❌ Exception pour projet {projet.titre} → {str(e)}"
                ))
