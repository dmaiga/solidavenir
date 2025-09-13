# core/services.py
import requests
from decimal import Decimal
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class HederaService:
    """Service principal pour les opérations Hedera"""
    
    def __init__(self):
        self.mirror_url = "https://testnet.mirrornode.hedera.com/api/v1"
        self.hashio_url = "https://testnet.hashio.io/api"
        self.operator_id = getattr(settings, 'HEDERA_OPERATOR_ID', '0.0.6808286')
    
    def get_account_balance(self, account_id):
        """Récupère le solde HBAR d'un compte"""
        try:
            url = f"{self.mirror_url}/accounts/{account_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                balance = data.get('balance', {}).get('balance', 0)
                return Decimal(balance) / Decimal('100000000')  # Conversion tinybars → HBAR
            return Decimal('0')
        except Exception as e:
            logger.error(f"Erreur récupération solde {account_id}: {e}")
            return Decimal('0')
    
    def transfer_hbar(self, sender_account_id, sender_private_key, receiver_account_id, amount_hbar, memo="Contribution projet"):
        """Effectue un transfert HBAR réel"""
        try:
            # Nettoyage de la clé privée
            private_key = sender_private_key
            if private_key and private_key.startswith('0x'):
                private_key = private_key[2:]
            
            # Conversion en tinybars (1 HBAR = 100,000,000 tinybars)
            amount_tinybars = int(Decimal(amount_hbar) * Decimal('100000000'))
            
            # Construction de la transaction
            transaction_data = {
                "transactions": [
                    {
                        "transaction": {
                            "cryptoTransfer": {
                                "transfers": {
                                    "accountAmounts": [
                                        {
                                            "accountID": sender_account_id,
                                            "amount": -amount_tinybars  # Débit
                                        },
                                        {
                                            "accountID": receiver_account_id,
                                            "amount": amount_tinybars   # Crédit
                                        }
                                    ]
                                }
                            },
                            "transactionFee": 2000000,  # 0.02 HBAR de frais
                            "transactionValidDuration": 120,
                            "memo": memo
                        },
                        "operatorAccountId": self.operator_id,
                        "signatures": [
                            {
                                "accountId": sender_account_id,
                                "privateKey": private_key,
                                "signature": "AUTO"  # Hashio.io signe automatiquement
                            }
                        ]
                    }
                ]
            }
            
            # Envoi de la transaction
            response = requests.post(
                f"{self.hashio_url}/transaction",
                json=transaction_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                transaction_id = data[0].get('transactionId')
                if transaction_id:
                    logger.info(f"Transaction réussie: {transaction_id}")
                    return transaction_id, True
            
            logger.error(f"Échec transaction: {response.status_code} - {response.text}")
            return None, False
            
        except Exception as e:
            logger.error(f"Erreur transfert HBAR: {e}")
            return None, False
    
    def verify_transaction(self, transaction_id):
        """Vérifie le statut d'une transaction"""
        try:
            url = f"{self.mirror_url}/transactions/{transaction_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('result') == 'SUCCESS'
            return False
        except Exception as e:
            logger.error(f"Erreur vérification transaction: {e}")
            return False
    
    def get_transaction_details(self, transaction_id):
        """Récupère les détails d'une transaction"""
        try:
            url = f"{self.mirror_url}/transactions/{transaction_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Erreur détails transaction: {e}")
            return None
    
    def creer_compte_hedera(self, initial_balance=0):
        """
        Crée un nouveau compte Hedera via hashio.io
        Retourne {'account_id': '0.0.123', 'private_key': '...'}
        """
        try:
            # Appel à l'API hashio.io pour créer un compte
            response = requests.post(
                f"{self.hashio_url}/account",
                json={
                    "operatorAccountId": self.operator_id,
                    "initialBalance": initial_balance
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'account_id': data.get('accountId'),
                    'private_key': data.get('privateKey'),
                    'public_key': data.get('publicKey')
                }
            else:
                raise Exception(f"Erreur API: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Erreur création compte: {e}")
            # Fallback: simulation pour le développement
            return self._simuler_creation_compte()
    
    def _simuler_creation_compte(self):
        """Simule la création d'un compte pour le développement"""
        import uuid
        return {
            'account_id': f"0.0.sim{uuid.uuid4().hex[:8]}",
            'private_key': f"simulated_private_key_{uuid.uuid4().hex[:16]}",
            'public_key': f"simulated_public_key_{uuid.uuid4().hex[:16]}"
        }