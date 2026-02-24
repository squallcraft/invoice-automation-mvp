#!/usr/bin/env python3
"""Genera una clave Fernet para ENCRYPTION_KEY (variable de entorno)."""
from cryptography.fernet import Fernet

if __name__ == "__main__":
    print(Fernet.generate_key().decode())
