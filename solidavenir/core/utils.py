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

# core/utils.py

import logging

logger = logging.getLogger(__name__)

def safe_float(value, default=0.0):
    """
    Convertit une valeur en float de manière sécurisée.
    
    Args:
        value: La valeur à convertir (peut être None, string, int, float, Decimal)
        default: La valeur par défaut si la conversion échoue (défaut: 0.0)
    
    Returns:
        float: La valeur convertie ou la valeur par défaut en cas d'erreur
    
    Examples:
        >>> safe_float("10.5")
        10.5
        >>> safe_float(None)
        0.0
        >>> safe_float("invalid", 1.0)
        1.0
        >>> safe_float(15)
        15.0
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning(f"Impossible de convertir la valeur '{value}' en float, utilisation de la valeur par défaut {default}")
        return default

def safe_int(value, default=0):
    """
    Convertit une valeur en int de manière sécurisée.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(f"Impossible de convertir la valeur '{value}' en int, utilisation de la valeur par défaut {default}")
        return default

def safe_decimal(value, default=0.0):
    """
    Convertit une valeur en Decimal de manière sécurisée.
    """
    from decimal import Decimal, InvalidOperation
    if value is None:
        return Decimal(str(default))
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        logger.warning(f"Impossible de convertir la valeur '{value}' en Decimal, utilisation de la valeur par défaut {default}")
        return Decimal(str(default))



