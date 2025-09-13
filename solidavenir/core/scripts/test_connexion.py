# scripts/test_connexion.py
from hiero_sdk_python import HieroClient, Network

def test_connexion():
    try:
        client = HieroClient(
            operator_id="0.0.VOTRE_ID",
            operator_key="VOTRE_CLE_PRIVEE", 
            network=Network.TESTNET
        )
        
        # Test de balance
        balance = client.get_account_balance("0.0.VOTRE_ID")
        print(f"✅ Connexion réussie! Solde: {balance} HBAR")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")

test_connexion()