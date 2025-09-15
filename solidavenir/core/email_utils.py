# email_utils.py
import os
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .models import EmailLog

logger = logging.getLogger(__name__)

def envoyer_email_simule(destinataire, sujet, corps, type_email='other', utilisateur=None):
    """
    Envoie un email simulé (enregistrement en base sans réel envoi)
    """
    try:
        # Créer le log d'email
        email_log = EmailLog.objects.create(
            destinataire=destinataire,
            sujet=sujet,
            corps=corps,
            type_email=type_email,
            statut='simulated',
            utilisateur=utilisateur
        )
        
        # Si la simulation est désactivée, envoyer un vrai email
        if not getattr(settings, 'SIMULATION_EMAIL', True):
            return envoyer_email_reel(destinataire, sujet, corps, type_email, utilisateur)
        
        logger.info(f"Email simulé enregistré: {sujet} pour {destinataire} (ID: {email_log.id})")
        return email_log
        
    except Exception as e:
        logger.error(f"Erreur lors de la simulation d'email: {str(e)}")
        return None

def envoyer_email_reel(destinataire, sujet, corps, type_email='other', utilisateur=None):
    """
    Envoie un email réel via le backend Django
    """
    try:
        # Créer le log d'email
        email_log = EmailLog.objects.create(
            destinataire=destinataire,
            sujet=sujet,
            corps=corps,
            type_email=type_email,
            statut='pending',
            utilisateur=utilisateur
        )
        
        # Envoyer l'email réel
        send_mail(
            sujet,
            corps,
            settings.DEFAULT_FROM_EMAIL,
            [destinataire],
            fail_silently=False,
        )
        
        # Marquer comme envoyé
        email_log.marquer_comme_envoye()
        logger.info(f"Email envoyé: {sujet} à {destinataire}")
        return email_log
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erreur lors de l'envoi d'email: {error_msg}")
        if 'email_log' in locals():
            email_log.marquer_comme_erreur(error_msg)
        return None

def envoyer_email(destinataire, sujet, corps, type_email='other', utilisateur=None):
    """
    Fonction principale pour envoyer des emails (gère simulation/réel automatiquement)
    """
    if getattr(settings, 'SIMULATION_EMAIL', True):
        return envoyer_email_simule(destinataire, sujet, corps, type_email, utilisateur)
    else:
        return envoyer_email_reel(destinataire, sujet, corps, type_email, utilisateur)

def envoyer_email_template(destinataire, sujet, template_name, context, type_email='other', utilisateur=None):
    """
    Envoie un email en utilisant un template HTML
    """
    try:
        # Rendre le template
        corps_html = render_to_string(template_name, context)
        corps_texte = render_to_string(template_name, context)  # Version texte simple
        
        return envoyer_email(destinataire, sujet, corps_texte, type_email, utilisateur)
        
    except Exception as e:
        logger.error(f"Erreur lors du rendu du template email: {str(e)}")
        return None