#!/usr/bin/env python3
"""
Prueba: traer órdenes de Falabella usando las credenciales guardadas en la app.
Uso (desde la raíz del proyecto):
  cd backend && python scripts/fetch_falabella_orders.py
O con flask:
  cd backend && flask --app app.app run  # no, mejor:
  python scripts/fetch_falabella_orders.py
Requiere que exista al menos un usuario con Falabella configurado (falabella_user_id + falabella_api_key).
"""
import os
import sys
from datetime import datetime, timezone, timedelta

# Asegurar que backend está en el path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app import create_app
from app.models import User
from app.crypto_utils import decrypt_value
from app.services.falabella_client import FalabellaClient


def main():
    app = create_app()
    with app.app_context():
        # Usuario con Falabella configurado
        users = User.query.filter(
            User.falabella_user_id.isnot(None),
            User.falabella_api_key_enc.isnot(None),
        ).all()
        if not users:
            print("No hay ningún usuario con Falabella configurado (falabella_user_id + API Key).")
            print("Configura Falabella en Configuración de la app y vuelve a ejecutar.")
            return 1
        user = users[0]
        try:
            api_key = decrypt_value(user.falabella_api_key_enc)
        except Exception as e:
            print(f"Error al desencriptar API Key del usuario {user.email}: {e}")
            return 1
        client = FalabellaClient(user_id=user.falabella_user_id, api_key=api_key)
        since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00+00:00")
        print(f"Usuario: {user.email} | UserID Falabella: {user.falabella_user_id}")
        print(f"Pidiendo órdenes desde {since} (últimos 30 días), limit=30...")
        result = client.get_orders(created_after=since, updated_after=since, limit=30, offset=0)
        if not result.get("success"):
            print("Error Falabella:", result.get("error", result))
            return 1
        data = result.get("data", {})
        body = data.get("Body") or data
        orders_raw = (body.get("Orders") or {}).get("Order") or body.get("Order") or []
        orders = orders_raw if isinstance(orders_raw, list) else [orders_raw] if orders_raw else []
        print(f"\nTotal órdenes recibidas: {len(orders)}")
        if not orders:
            print("(No hay órdenes en el rango indicado.)")
            return 0
        print("\nPrimeras órdenes (OrderId, Status, Price, CreatedAt):")
        for i, o in enumerate(orders[:10]):
            o = o or {}
            print(f"  {i+1}. OrderId={o.get('OrderId')} Status={o.get('Status')} Price={o.get('Price')} CreatedAt={o.get('CreatedAt')}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
