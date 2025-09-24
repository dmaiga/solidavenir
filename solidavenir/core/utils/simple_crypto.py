import base64
from cryptography.fernet import Fernet
from django.conf import settings

def _get_fernet():
    # On utilise une clé simple stockée dans .env (SECRET_KEY_SIMPLE)
    key = settings.SECRET_KEY_SIMPLE.encode('utf-8')
    key = key.ljust(32, b'0')[:32]  # compléter ou tronquer à 32 bytes
    key = base64.urlsafe_b64encode(key)
    return Fernet(key)

def encrypt_value(plain_text: str) -> bytes:
    f = _get_fernet()
    return f.encrypt(plain_text.encode('utf-8'))

def decrypt_value(token: bytes) -> str:
    f = _get_fernet()
    return f.decrypt(token).decode('utf-8')
