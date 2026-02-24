#!/usr/bin/env python3
"""
Script para probar conexión a Mercado Libre API y estado de documentos fiscales.
Flujo principal: 1º comprobar si en ML ya hay documento cargado → Cargado; si no, estado desde DB.
Requiere: pip install requests
Uso: cd backend && python3 scripts/test_mercadolibre.py
Env: ML_ACCESS_TOKEN (obligatorio si no hay DB con usuario ML), ML_USER_ID (opcional, seller para get_orders).
     ML_PACK_IDS_CARGADOS=pack1,pack2 marca esos packs como cargados (override).
"""
import os
import sys
from datetime import datetime, timezone

# Credenciales desde env o desde DB (primer usuario con ML)
ML_ACCESS_TOKEN = os.environ.get("ML_ACCESS_TOKEN", "").strip()
ML_USER_ID = os.environ.get("ML_USER_ID", "").strip()


def _get_ml_client_and_seller():
    """Obtiene MercadoLibreClient y seller_id (ml_user_id). Primero env, luego DB."""
    if ML_ACCESS_TOKEN:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        os.chdir(backend_dir)
        from app.services.mercadolibre_client import MercadoLibreClient
        return MercadoLibreClient(access_token=ML_ACCESS_TOKEN), ML_USER_ID or None
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        os.chdir(backend_dir)
        from app import create_app
        from app.models import User
        from app.crypto_utils import decrypt_value
        from app.services.mercadolibre_client import MercadoLibreClient
        app = create_app()
        with app.app_context():
            for user in User.query.all():
                if not getattr(user, "ml_access_token_enc", None):
                    continue
                try:
                    token = decrypt_value(user.ml_access_token_enc)
                except Exception:
                    continue
                return MercadoLibreClient(access_token=token), (user.ml_user_id or None)
    except Exception:
        pass
    return None, None


def _doc_estado_db(orders, ml_user_id_for_lookup):
    """Dict id_venta -> Por emitir | Emitido | Cargado desde nuestra DB."""
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        os.chdir(backend_dir)
        from app import create_app
        from app.models import Sale, User
        app = create_app()
        with app.app_context():
            user = User.query.filter_by(ml_user_id=ml_user_id_for_lookup).first() if ml_user_id_for_lookup else User.query.first()
            if not user:
                return {}
            out = {}
            for o in orders:
                id_venta = str(o.get("id_venta") or o.get("id", ""))
                if not id_venta:
                    continue
                sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
                if not sale:
                    out[id_venta] = "Por emitir"
                elif getattr(sale, "document_uploaded_at", None):
                    out[id_venta] = "Cargado"
                elif sale.status == "Éxito":
                    out[id_venta] = "Emitido"
                else:
                    out[id_venta] = "Por emitir"
            return out
    except Exception:
        return {}


def _ml_documento_cargado(orders, client):
    """Dict id_venta -> True si en ML ya hay documento fiscal cargado. Incluye ML_PACK_IDS_CARGADOS."""
    env_loaded_packs = set()
    for pid in (os.environ.get("ML_PACK_IDS_CARGADOS") or "").replace(",", " ").split():
        pid = pid.strip()
        if pid:
            env_loaded_packs.add(pid)
    out = {}
    for o in orders:
        id_venta = str(o.get("id_venta") or o.get("id", ""))
        pack_id = str(o.get("pack_id") or id_venta)
        if pack_id in env_loaded_packs or client.fiscal_document_uploaded(pack_id) is True:
            out[id_venta] = True
    return out


def main():
    client, seller_id = _get_ml_client_and_seller()
    if not client:
        print("ERROR: Configura ML_ACCESS_TOKEN o conecta ML en la app (usuario con ml_access_token_enc).")
        return 1

    print("Probando Mercado Libre (marketplace/orders/search)...")
    print("Seller ID:", seller_id or "(no filtro)")
    result = client.get_orders(seller_id=seller_id, limit=20)
    if not result.get("success"):
        print("ERROR:", result.get("error", result))
        return 1

    data = result.get("data") or {}
    results = data.get("results") or []
    if not results:
        print("No hay órdenes recientes.")
        return 0

    # Enriquecer cada orden con pack_id, monto, fecha
    orders = []
    for r in results:
        order_id = str(r.get("id", ""))
        if not order_id:
            continue
        detail = client.get_order(order_id)
        if not detail.get("success"):
            continue
        pack_id = detail.get("pack_id") or order_id
        d = detail.get("data") or {}
        monto = float(d.get("total", 0) or 0)
        created = d.get("date_created") or r.get("date_created")
        try:
            if created and "T" in str(created):
                fecha = datetime.fromisoformat(str(created).replace("Z", "+00:00")).strftime("%Y-%m-%d")
            else:
                fecha = str(created)[:10] if created else "—"
        except Exception:
            fecha = "—"
        orders.append({
            "id_venta": order_id,
            "pack_id": str(pack_id),
            "monto": monto,
            "fecha": fecha,
            "status": d.get("status") or r.get("status") or "—",
        })

    # 1º Comprobación: ¿documento ya cargado en ML?
    ml_cargado = _ml_documento_cargado(orders, client)
    # 2º Estado desde DB
    doc_estados = _doc_estado_db(orders, seller_id)

    print(f"Órdenes encontradas: {len(orders)}")
    print()
    print(f"{'Plataforma':<14} | {'ID Venta':<14} | {'Pack ID':<14} | {'Fecha':<12} | {'Monto':>10} | {'Estado':<12} | Documento")
    print("-" * 100)
    for o in orders:
        id_venta = o["id_venta"]
        pack_id = o["pack_id"]
        monto_str = f"${o['monto']:,.0f}" if o["monto"] else "—"
        if ml_cargado.get(id_venta) or ml_cargado.get(pack_id):
            documento = "Cargado"
        else:
            documento = doc_estados.get(id_venta, "Por emitir")
        print(f"{'Mercado Libre':<14} | {id_venta:<14} | {pack_id:<14} | {o['fecha']:<12} | {monto_str:>10} | {str(o['status']):<12} | {documento}")
    print()
    print("Documento: 1º Si en ML ya está cargado → Cargado (no reemitir). 2º Si no: Por emitir | Emitido | Cargado (subido por nuestra plataforma).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
