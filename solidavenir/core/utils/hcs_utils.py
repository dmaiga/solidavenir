# utils/hcs_utils.py - 
from django.utils import timezone
import logging
from core.models import HcsTopic, HcsMessage, Projet, Transaction, TransactionAdmin
from django.db.models import Prefetch, Count, Sum, Max, Q
from django.db.models.functions import Coalesce, TruncMonth
from django.db.models import Sum, Count, Q, Avg, Max, Min, DecimalField
from django import m
logger = logging.getLogger(__name__)

def creer_ou_maj_topic(projet, topic_id, transaction_hash, createur):
    """Crée ou met à jour un topic HCS dans le registre"""
    try:
        topic, created = HcsTopic.objects.get_or_create(
            topic_id=topic_id,
            defaults={
                'projet': projet,
                'createur': createur,
                'transaction_creation': transaction_hash,
                'hashscan_url': f"https://hashscan.io/testnet/topic/{topic_id}",
                'memo': f"Topic pour le projet: {projet.titre}"
            }
        )
        
        if not created:
            # Mise à jour si le topic existe déjà
            topic.projet = projet
            topic.transaction_creation = transaction_hash
            topic.statut = 'actif'
            topic.save()
        
        action = "créé" if created else "mis à jour"
        logger.info(f"Topic HCS {topic_id} {action} pour le projet {projet.titre}")
        return topic
        
    except Exception as e:
        logger.error(f"Erreur création topic HCS: {e}")
        return None

def enregistrer_message_hcs(message_data, topic_id, type_message, transactions_associees=None):
    """Enregistre un message HCS dans la base de données"""
    try:
        # Trouver le topic
        topic = HcsTopic.objects.get(topic_id=topic_id)
        
        # Créer le message
        message = HcsMessage.objects.create(
            message_id=message_data.get('messageId') or f"msg_{timezone.now().timestamp()}",
            topic=topic,
            type_message=type_message,
            contenu_message=message_data,
            hash_transaction=message_data.get('transactionHash'),
            hashscan_url=message_data.get('hashscanUrl'),
            sequence_number=message_data.get('sequenceNumber'),
            running_hash=message_data.get('runningHash'),
            statut='confirme' if message_data.get('success') else 'envoye'
        )
        
        # Lier les transactions associées si fournies
        if transactions_associees:
            if 'transaction' in transactions_associees:
                message.transaction_associee = transactions_associees['transaction']
            if 'transaction_admin' in transactions_associees:
                message.transaction_admin_associee = transactions_associees['transaction_admin']
            message.save()
        
        # Actualiser les statistiques du topic
        topic.actualiser_statistiques()
        
        logger.info(f"Message HCS enregistré: {message.message_id}")
        return message
        
    except HcsTopic.DoesNotExist:
        logger.error(f"Topic HCS {topic_id} non trouvé pour l'enregistrement du message")
        return None
    except Exception as e:
        logger.error(f"Erreur enregistrement message HCS: {e}")
        return None

def get_statistiques_topics():
    """Retourne des statistiques globales sur les topics HCS"""
    from django.db.models import Count, Max
    
    stats = HcsTopic.objects.aggregate(
        total_topics=Count('topic_id'),
        topics_actifs=Count('topic_id', filter=models.Q(statut='actif')),
        total_messages=Count('messages'),
        dernier_message=Max('messages__date_message')
    )
    
    return stats

def get_messages_par_type():
    """Retourne le nombre de messages par type"""
    return dict(HcsMessage.objects.values_list('type_message').annotate(
        total=Count('id')
    ).order_by('-total'))