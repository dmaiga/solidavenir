from django.core.management.base import BaseCommand
from core.models import Projet
from core.utils import creer_topic_pour_projet

class Command(BaseCommand):
    help = "Vérifie les projets actifs sans topic et en crée un"

    def handle(self, *args, **kwargs):
        projets = Projet.objects.filter(statut="actif", topic_id__isnull=True)
        for projet in projets:
            topic_id = creer_topic_pour_projet(projet)
            if topic_id:
                self.stdout.write(self.style.SUCCESS(f"Topic créé pour projet {projet.id}: {topic_id}"))
            else:
                self.stdout.write(self.style.ERROR(f"Échec création topic pour projet {projet.id}"))
