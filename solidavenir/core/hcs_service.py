import requests
from django.conf import settings
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

HEDERA_API_URL = getattr(settings, 'HEDERA_API_URL', 'http://localhost:3001')

class HCSService:
    @staticmethod
    def create_project_topic(project_id, admin_id, project_content=None):
        """Crée un topic HCS pour un projet et retourne le résultat complet"""
        payload = {
            "projectId": project_id,
            "projectContent": project_content,
            "adminId": admin_id  # Ajout de l'admin ID pour l'audit
        }
        
        try:
            response = requests.post(
                f"{HEDERA_API_URL}/create-project-topic",
                json=payload,
                timeout=30
            )
            result = response.json()
            
            # Journalisation détaillée
            logger.info(f"Création topic HCS - Projet: {project_id}, Succès: {result.get('success')}, TopicID: {result.get('topicId')}")
            
            return result
        except Exception as e:
            error_msg = f"Erreur création topic: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    @staticmethod
    def notarize_validation(project_id, admin_id, validation_status, project_content=None):
        """Notarise une validation de projet et retourne le résultat complet"""
        payload = {
            "projectId": project_id,
            "adminId": admin_id,
            "validationStatus": validation_status,
            "projectContent": project_content
        }
        
        try:
            response = requests.post(
                f"{HEDERA_API_URL}/notarize-project-validation",
                json=payload,
                timeout=30
            )
            result = response.json()
            
            # Journalisation détaillée
            logger.info(f"Notarisation validation - Projet: {project_id}, Statut: {validation_status}, Succès: {result.get('success')}")
            
            return result
        except Exception as e:
            error_msg = f"Erreur notarisation validation: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    @staticmethod
    def get_topic_creation_status(topic_id):
        """Vérifie le statut de création d'un topic sur HashScan"""
        # Cette fonction peut être implémentée pour vérifier sur HashScan
        # Pour le moment, retournons une structure simulée
        return {
            "exists": True,
            "topic_id": topic_id,
            "hashscan_url": f"https://hashscan.io/testnet/topic/{topic_id}",
            "consensus_timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def sync_project_messages(project_topic):
        """Synchronise les messages d'un topic avec la base de données"""
        result = HCSService.get_project_messages(project_topic.project_id)
        
        if not result.get('success'):
            return result
        
        from .models import HCSMessage
        
        messages_created = 0
        for msg_data in result.get('messages', []):
            # Vérifier si le message existe déjà
            if not HCSMessage.objects.filter(
                topic=project_topic, 
                sequence_number=msg_data['sequenceNumber']
            ).exists():
                
                message_content = msg_data['message']
                message_type = message_content.get('type', 'OTHER')
                
                HCSMessage.objects.create(
                    topic=project_topic,
                    sequence_number=msg_data['sequenceNumber'],
                    consensus_timestamp=datetime.fromtimestamp(
                        msg_data['consensusTimestamp'].seconds + 
                        msg_data['consensusTimestamp'].nanos / 1e9
                    ),
                    message_type=message_type,
                    content=message_content,
                    transaction_id=message_content.get('transactionId')
                )
                messages_created += 1
        
        return {
            "success": True,
            "messages_created": messages_created,
            "total_messages": len(result.get('messages', []))
        }