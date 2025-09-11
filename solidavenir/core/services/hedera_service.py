import os
import logging
import uuid
from django.conf import settings

logger = logging.getLogger(__name__)

# Mode développement - désactiver les vérifications strictes
DEV_MODE = True

class HederaService:
    def __init__(self):
        if DEV_MODE:
            logger.warning("Mode développement activé - Vérifications Hedera simplifiées")
    
    def creer_topic(self, titre_projet):
        """Créer un nouveau topic Hedera (simulé)"""
        return f"0.0.topic_{uuid.uuid4().hex[:8]}"
    
    def get_account_balance(self, account_id):
        """Toujours retourner un solde suffisant en mode développement"""
        if DEV_MODE:
            return 1000.0  # Solde toujours suffisant
        return 0.0

    def effectuer_transaction(self, compte_source, cle_privee_source, compte_destination, montant):
        """Effectuer une transaction (toujours réussie en mode développement)"""
        if DEV_MODE:
            logger.info(f"Transaction DEV: {compte_source} -> {compte_destination} ({montant} HBAR)")
            return f"dev_tx_{uuid.uuid4().hex[:16]}"
        
        # Logique pour la production
        raise Exception("Mode production non implémenté")

    def creer_compte(self, cle_publique_initial=None):
        """Créer un nouveau compte (simulé)"""
        if DEV_MODE:
            account_id = f"0.0.dev{uuid.uuid4().int % 100000}"
            private_key = f"dev_key_{uuid.uuid4().hex[:16]}"
            
            logger.info(f"Compte développement créé: {account_id}")
            
            return {
                'account_id': account_id,
                'private_key': private_key
            }
        
        raise Exception("Mode production non implémenté")

    def verifier_transaction(self, transaction_hash):
        """Vérifier une transaction (toujours valide en mode développement)"""
        if DEV_MODE:
            return {
                'status': 'success',
                'transaction_hash': transaction_hash,
                'timestamp': '2024-01-01T12:00:00Z'
            }
        
        return {'status': 'unknown'}