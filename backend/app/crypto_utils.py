"""
Encriptación de API keys con Fernet (symmetric encryption).
Las keys se almacenan encriptadas en BD; se desencriptan solo en memoria al llamar APIs.
"""
import os
import base64
from cryptography.fernet import Fernet


def get_fernet():
    """Obtiene instancia Fernet desde variable de entorno ENCRYPTION_KEY."""
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise ValueError("ENCRYPTION_KEY no configurada. Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
    if isinstance(key, str) and len(key) != 44:
        key = base64.urlsafe_b64encode(key.encode().ljust(32)[:32])
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(plain: str) -> bytes:
    if not plain:
        return b""
    return get_fernet().encrypt(plain.encode())


def decrypt_value(encrypted: bytes) -> str:
    if not encrypted:
        return ""
    return get_fernet().decrypt(encrypted).decode()
