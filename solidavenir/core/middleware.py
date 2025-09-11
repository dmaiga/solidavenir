# core/middleware.py
from django.utils import translation

class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Vérifiez si la langue est définie dans la session
        if hasattr(request, 'session') and 'django_language' in request.session:
            language = request.session['django_language']
            translation.activate(language)
            request.LANGUAGE_CODE = language
        
        response = self.get_response(request)
        return response