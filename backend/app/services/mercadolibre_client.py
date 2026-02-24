"""
Cliente para Mercado Libre API: órdenes y subida de documentos fiscales.

- Autenticación: OAuth 2.0 (Bearer access_token). El token se obtiene por flujo
  Authorization Code y se renueva con refresh_token.
- Órdenes: GET /marketplace/orders/search, GET /orders/{id} (pack_id en la respuesta).
- Subir factura/boleta: POST /packs/{pack_id}/fiscal_documents (multipart PDF, max 1 MB).

Ref: https://developers.mercadolibre.com.ar/en_us/upload-invoices
"""

import logging
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

API_BASE = "https://api.mercadolibre.com"


class MercadoLibreClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self._headers = {"Authorization": f"Bearer {access_token}"}

    def get_orders(
        self,
        seller_id: Optional[str] = None,
        limit: int = 30,
        offset: int = 0,
        sort: str = "date_desc",
    ) -> Dict[str, Any]:
        """
        GET /marketplace/orders/search
        Devuelve órdenes recientes. Cada orden puede tener pack_id (o null → usar order id como pack).
        """
        try:
            url = f"{API_BASE}/marketplace/orders/search"
            params = {"limit": limit, "offset": offset, "sort": sort}
            if seller_id:
                params["seller"] = seller_id
            resp = requests.get(url, headers=self._headers, params=params, timeout=30)
            resp.raise_for_status()
            return {"success": True, "data": resp.json()}
        except requests.RequestException as e:
            logger.exception("ML get_orders error: %s", e)
            return {"success": False, "error": str(e), "response": getattr(e.response, "json", lambda: {})(())}

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        GET /orders/{order_id}
        Necesario para obtener pack_id (si no viene en el listado).
        """
        try:
            url = f"{API_BASE}/orders/{order_id}"
            resp = requests.get(url, headers=self._headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            pack_id = data.get("pack_id") or data.get("id")  # si pack_id null, usar order id
            return {"success": True, "data": data, "pack_id": pack_id}
        except requests.RequestException as e:
            logger.exception("ML get_order error: %s", e)
            return {"success": False, "error": str(e)}

    def get_fiscal_documents(self, pack_id: str) -> Dict[str, Any]:
        """
        GET /packs/{pack_id}/fiscal_documents
        Obtiene los IDs de documentos fiscales ya cargados en el pack.
        - 200 y fiscal_documents no vacío = ya hay documento en ML.
        - 404 o fiscal_documents vacío = no hay documento.
        """
        try:
            url = f"{API_BASE}/packs/{pack_id}/fiscal_documents"
            resp = requests.get(url, headers=self._headers, timeout=15)
            if resp.status_code == 404:
                return {"success": True, "data": {"fiscal_documents": []}}
            resp.raise_for_status()
            data = resp.json()
            docs = data.get("fiscal_documents") if isinstance(data, dict) else []
            if not isinstance(docs, list):
                docs = []
            return {"success": True, "data": {"fiscal_documents": docs, "pack_id": data.get("pack_id")}}
        except requests.RequestException as e:
            logger.exception("ML get_fiscal_documents error: %s", e)
            err_body = {}
            if hasattr(e, "response") and e.response is not None:
                try:
                    err_body = e.response.json()
                except Exception:
                    pass
            return {"success": False, "error": str(e), "response": err_body}

    def fiscal_document_uploaded(self, pack_id: str) -> Optional[bool]:
        """
        Comprueba si en Mercado Libre ya existe un documento fiscal cargado para este pack.
        Primera comprobación obligatoria antes de volver a emitir/subir.
        - True: ya hay documento en ML → no reemitir.
        - False: no hay documento en ML.
        - None: no se pudo comprobar (red, 403, etc.).
        """
        result = self.get_fiscal_documents(pack_id)
        if not result.get("success"):
            return None
        docs = (result.get("data") or {}).get("fiscal_documents") or []
        return True if docs else False

    def fiscal_document_uploaded_for_order(self, order_id: str) -> Optional[bool]:
        """
        Comprueba si la orden ya tiene documento fiscal en ML. Resuelve pack_id vía GET /orders/{id}.
        """
        order_resp = self.get_order(order_id)
        if not order_resp.get("success"):
            return None
        pack_id = order_resp.get("pack_id") or order_id
        return self.fiscal_document_uploaded(str(pack_id))

    def upload_fiscal_document(self, pack_id: str, pdf_content: bytes, filename: str = "factura.pdf") -> Dict[str, Any]:
        """
        POST /packs/{pack_id}/fiscal_documents
        multipart/form-data con el PDF. Máx 1 MB. Un documento fiscal por pack.
        """
        if len(pdf_content) > 1024 * 1024:
            return {"success": False, "error": "El archivo supera 1 MB"}
        try:
            url = f"{API_BASE}/packs/{pack_id}/fiscal_documents"
            files = {"fiscal_document": (filename, pdf_content, "application/pdf")}
            resp = requests.post(url, headers=self._headers, files=files, timeout=60)
            if not resp.ok:
                try:
                    err = resp.json()
                except Exception:
                    err = {"message": resp.text}
                return {"success": False, "error": err.get("message", resp.text), "response": err}
            return {"success": True, "data": resp.json()}
        except requests.RequestException as e:
            logger.exception("ML upload_fiscal_document error: %s", e)
            return {"success": False, "error": str(e)}


def refresh_ml_token(client_id: str, client_secret: str, refresh_token: str) -> Dict[str, Any]:
    """
    POST /oauth/token con grant_type=refresh_token.
    Devuelve nuevo access_token y refresh_token (el anterior queda invalidado).
    """
    try:
        url = f"{API_BASE}/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
        resp = requests.post(url, data=data, headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        resp.raise_for_status()
        return {"success": True, "data": resp.json()}
    except requests.RequestException as e:
        logger.exception("ML refresh_token error: %s", e)
        try:
            err = e.response.json()
        except Exception:
            err = {}
        return {"success": False, "error": str(e), "response": err}
