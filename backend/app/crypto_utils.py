"""
Encriptación de API keys con Fernet (cifrado simétrico).
Las keys se almacenan encriptadas en la BD; se desencriptan solo en memoria al llamar APIs.

Genera una clave válida con:
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import os
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """
    Obtiene la instancia Fernet desde ENCRYPTION_KEY.
    Fernet requiere exactamente una clave de 32 bytes codificada en base64-urlsafe (44 chars).
    """
    raw = os.environ.get("ENCRYPTION_KEY", "").strip()
    if not raw:
        raise ValueError(
            "ENCRYPTION_KEY no configurada. "
            "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(raw.encode())
    except Exception:
        raise ValueError(
            f"ENCRYPTION_KEY inválida (longitud: {len(raw)}). "
            "Debe ser una clave Fernet de 44 caracteres en base64-urlsafe. "
            "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )


def encrypt_value(plain: str) -> bytes:
    """Encripta un string. Devuelve bytes vacíos si plain es vacío."""
    if not plain:
        return b""
    return _get_fernet().encrypt(plain.encode())


def decrypt_value(encrypted: bytes) -> str:
    """
    Desencripta bytes previamente encriptados con encrypt_value.
    Lanza InvalidToken si los datos fueron encriptados con una clave distinta.
    """
    if not encrypted:
        return ""
    try:
        return _get_fernet().decrypt(encrypted).decode()
    except InvalidToken:
        raise ValueError(
            "No se puede desencriptar: la ENCRYPTION_KEY actual no coincide con la usada al guardar. "
            "Si cambiaste la clave, debes volver a guardar las credenciales en Configuración."
        )
