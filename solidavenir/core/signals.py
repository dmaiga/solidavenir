from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import User, Association

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crée automatiquement les profils spécifiques selon le type d'utilisateur"""
    if created:
        if instance.user_type == 'association':
            # Créer le profil Association
            Association.objects.create(
                user=instance,
                nom=instance.nom_association or f"Association {instance.username}",
                domaine_principal='autre',
                causes_defendues=instance.causes_defendues or "Causes à définir",
                statut_juridique='loi_1901',
                adresse_siege=instance.adresse or "Adresse à compléter",
                ville=instance.ville or "Ville à compléter",
                code_postal=instance.code_postal or "00000",
                telephone=instance.telephone or "0000000000",
                email_contact=instance.email,
                date_creation=instance.date_creation_association or timezone.now().date()
            )