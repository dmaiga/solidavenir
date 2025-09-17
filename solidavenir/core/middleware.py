# core/middleware.py
import requests
from django.conf import settings

class AutoWalletMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Créer un wallet automatiquement pour les utilisateurs authentifiés
        if request.user.is_authenticated and not request.user.is_anonymous:
            # Vérifier si l'utilisateur a besoin d'un wallet
            if (not request.user.hedera_account_id or 
                not request.user.wallet_activated):
                try:
                    request.user.ensure_wallet()
                except Exception as e:
                    # Loguer l'erreur mais ne pas bloquer l'utilisateur
                    print(f"Erreur création auto wallet: {e}")