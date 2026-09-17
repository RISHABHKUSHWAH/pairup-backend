import base64
import hashlib
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTOGRAPHY = True
except ImportError:
    Fernet = None
    InvalidToken = Exception
    HAS_CRYPTOGRAPHY = False
    logger.warning("cryptography package is not installed; run 'pip install cryptography'.")

CIPHER_PREFIX = "enc:v1:"


def get_cipher():
    """
    Derives a consistent, secure 32-byte URL-safe base64 key from settings.CHAT_ENCRYPTION_KEY
    or settings.SECRET_KEY using SHA-256.
    """
    if not HAS_CRYPTOGRAPHY or Fernet is None:
        return None
    key_material = getattr(settings, 'CHAT_ENCRYPTION_KEY', None) or settings.SECRET_KEY
    digest = hashlib.sha256(key_material.encode('utf-8')).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_text(plain_text: str) -> str:
    """
    Encrypts a plaintext string into an authenticated ciphertext token prefixed with 'enc:v1:'.
    Returns the ciphertext string.
    """
    if not plain_text:
        return ""
    # Avoid double encryption
    if plain_text.startswith(CIPHER_PREFIX):
        return plain_text
    cipher = get_cipher()
    if cipher is None:
        return plain_text
    token = cipher.encrypt(plain_text.encode('utf-8')).decode('utf-8')
    return f"{CIPHER_PREFIX}{token}"


def decrypt_text(cipher_or_plain: str) -> str:
    """
    Decrypts an 'enc:v1:' token.
    If the string does not have the 'enc:v1:' prefix (e.g. legacy message),
    it is returned as-is for backward compatibility.
    """
    if not cipher_or_plain:
        return ""
    if not cipher_or_plain.startswith(CIPHER_PREFIX):
        return cipher_or_plain
    cipher = get_cipher()
    if cipher is None:
        return "[Encryption module unavailable]"
    raw_token = cipher_or_plain[len(CIPHER_PREFIX):]
    try:
        return cipher.decrypt(raw_token.encode('utf-8')).decode('utf-8')
    except (InvalidToken, Exception):
        return "[Decryption failed]"
