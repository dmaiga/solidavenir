# core/utils.py ou core/admin.py
from decimal import Decimal
from .models import Palier

def creer_paliers(projet):
    """
    Crée automatiquement les paliers pour un projet selon la répartition 40%-30%-30%
    """
    # Supprimer les paliers existants pour éviter les doublons
    projet.paliers.all().delete()
    
    # Définition des paliers standard
    pourcentages = [40, 30, 30]
    paliers_crees = []
    
    for pct in pourcentages:
        montant_palier = (projet.montant_demande * Decimal(pct)) / 100
        palier = Palier.objects.create(
            projet=projet,
            pourcentage=Decimal(pct),
            montant=montant_palier
        )
        paliers_crees.append(palier)
    
    return paliers_crees

# Dans vos modèles ou utils.py
from django.template.defaulttags import register

@register.filter
def get_preuve_status(palier):
    """Retourne la dernière preuve soumise pour un palier"""
    return palier.preuves.first()

def get_transaction_explorer_url(transaction_hash, network='testnet'):

    """Génère l'URL d'exploration de la transaction selon le réseau"""
    explorers = {
        'testnet': 'https://hashscan.io/testnet/transaction',
        'mainnet': 'https://hashscan.io/mainnet/transaction'
    }
    base_url = explorers.get(network, explorers['testnet'])
    return f"{base_url}/{transaction_hash}"





