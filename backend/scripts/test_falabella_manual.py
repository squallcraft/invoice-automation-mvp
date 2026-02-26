import os
import sys
import json
import logging

# Añadir el directorio raíz del backend al path para poder importar app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.falabella_client import FalabellaClient

# Configurar logging
logging.basicConfig(level=logging.INFO)

def test_falabella():
    user_id = os.environ.get("FALABELLA_USER_ID")
    api_key = os.environ.get("FALABELLA_API_KEY")

    if not user_id or not api_key:
        print("Error: Define las variables de entorno FALABELLA_USER_ID y FALABELLA_API_KEY")
        print("Ejemplo: FALABELLA_USER_ID=correo@falabella.com FALABELLA_API_KEY=... python3 scripts/test_falabella_manual.py")
        return

    print(f"Probando conexión con Falabella Seller Center...")
    print(f"User ID: {user_id}")
    # print(f"API Key: {api_key[:5]}...")

    client = FalabellaClient(user_id=user_id, api_key=api_key)
    
    # Probar get_orders
    print("\n1. Obteniendo órdenes recientes (GetOrders)...")
    # Usar una fecha reciente para no traer demasiada data o demorar
    from datetime import datetime, timedelta
    created_after = (datetime.utcnow() - timedelta(days=5)).isoformat()
    
    result = client.get_orders(created_after=created_after)
    
    if result.get("success"):
        data = result.get("data", {})
        orders = data.get("SuccessResponse", {}).get("Body", {}).get("Orders", {}).get("Order", [])
        if isinstance(orders, dict): orders = [orders] # Si es una sola orden viene como dict
        
        print(f"✅ Éxito. Se encontraron {len(orders)} órdenes en los últimos 5 días.")
        if orders:
            print("Primera orden encontrada:")
            print(json.dumps(orders[0], indent=2, default=str))
    else:
        print("❌ Error al obtener órdenes:")
        print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    test_falabella()
