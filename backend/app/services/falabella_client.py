"""
Cliente para Falabella Seller Center API (sellercenter-api.falabella.com).

- Autenticación: UserID (email) + API Key, firma HMAC-SHA256 sobre params (RFC 3986).
- Documentación: https://developers.falabella.com/
- Etiquetas: GetDocument con DocumentType=shippingParcel y OrderItemIds.
- Documentos tributarios: SetInvoicePDF (POST /v1/marketplace-sellers/invoice/pdf) para subir
  boleta/factura en PDF; equivalente a https://sellercenter.falabella.com/order/invoice#/upload-documents
"""
import logging
import requests
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)

# URL oficial Falabella Seller Center
DEFAULT_BASE_URL = "https://sellercenter-api.falabella.com"


def _rfc3986_encode(s: str) -> str:
    """Codificación tipo RFC 3986 para nombres y valores en la firma."""
    return quote(str(s), safe="-_.~")


def _build_signature(parameters: Dict[str, str], api_key: str) -> str:
    """
    Firma HMAC-SHA256 del string de parámetros (orden alfabético, name=value con &).
    No incluir el parámetro Signature en parameters al llamar.
    """
    sorted_keys = sorted(parameters.keys())
    pairs = [f"{_rfc3986_encode(k)}={_rfc3986_encode(parameters[k])}" for k in sorted_keys]
    string_to_sign = "&".join(pairs)
    sig = hmac.new(
        api_key.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return sig


def _iso8601_timestamp() -> str:
    """Timestamp en formato ISO 8601 UTC para la API."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


class FalabellaClient:
    """
    Cliente para la API de Falabella Seller Center.
    Credenciales: user_id = email del usuario en Seller Center, api_key = API Key (Manage Users).
    """

    def __init__(
        self,
        user_id: str,
        api_key: str,
        base_url: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        self.user_id = user_id.strip()
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        # User-Agent recomendado: SELLER_ID/TECHNOLOGY/VERSION/INTEGRATION_TYPE/BUSINESS_UNIT (Chile: FACL)
        self.user_agent = user_agent or "SELLER/Python/3/INVOICE_MVP/FACL"

    def _base_params(self, action: str, fmt: str = "JSON") -> Dict[str, str]:
        """Parámetros comunes a todas las llamadas: Action, Format, Timestamp, UserID, Version."""
        return {
            "Action": action,
            "Format": fmt,
            "Timestamp": _iso8601_timestamp(),
            "UserID": self.user_id,
            "Version": "1.0",
        }

    def _request(self, params: Dict[str, Any], method: str = "GET") -> Dict[str, Any]:
        """
        Ejecuta la petición firmada. Convierte listas en múltiples valores para la query string.
        """
        # Valores para firma: todo en string; las listas se unen en comma para la firma
        str_params = {}
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, list):
                str_params[k] = ",".join(str(x) for x in v)
            else:
                str_params[k] = str(v)

        signature = _build_signature(str_params, self.api_key)
        str_params["Signature"] = signature

        # Construir query: mismos params que la firma; arrays como múltiples keys (OrderItemIds=1&OrderItemIds=2)
        query_parts = []
        for k in sorted(str_params.keys()):
            v = str_params[k]
            if k == "Signature":
                query_parts.append(f"Signature={quote(signature, safe='')}")
                continue
            if k in params and isinstance(params[k], list):
                for item in params[k]:
                    query_parts.append(f"{quote(k)}={quote(str(item), safe='')}")
            else:
                query_parts.append(f"{quote(k)}={quote(str(v), safe='')}")
        query_string = "&".join(query_parts)

        url = f"{self.base_url}/?{query_string}"
        headers = {"User-Agent": self.user_agent}

        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=60)
            else:
                resp = requests.post(url, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.exception("Falabella API request error: %s", e)
            try:
                err_body = resp.json() if resp else {}
            except Exception:
                err_body = {}
            return {"success": False, "error": str(e), "response": err_body}
        except ValueError as e:
            logger.exception("Falabella API JSON decode error: %s", e)
            return {"success": False, "error": f"Invalid response: {e}"}

        # Respuesta éxito viene en SuccessResponse; error en ErrorResponse
        if "SuccessResponse" in data:
            return {"success": True, "data": data.get("SuccessResponse", data)}
        if "ErrorResponse" in data:
            head = data["ErrorResponse"].get("Head", {})
            return {
                "success": False,
                "error": head.get("ErrorMessage", "Unknown error"),
                "error_code": head.get("ErrorCode"),
                "response": data,
            }
        return {"success": True, "data": data}

    def get_orders(
        self,
        created_after: Optional[str] = None,
        updated_after: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        shipping_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        GetOrders. Obtiene órdenes. Obligatorio CreatedAfter o UpdatedAfter (ISO 8601).
        status: pending, canceled, ready_to_ship, shipped, delivered, returned, failed_delivery, etc.
        shipping_type: dropshipping | own_warehouse | cross_docking
        """
        if not created_after and not updated_after:
            return {"success": False, "error": "CreatedAfter o UpdatedAfter es obligatorio"}
        params = self._base_params("GetOrders")
        if created_after:
            params["CreatedAfter"] = created_after
        if updated_after:
            params["UpdatedAfter"] = updated_after
        if status:
            params["Status"] = status
        params["Limit"] = min(limit, 100)
        params["Offset"] = offset
        if shipping_type:
            params["ShippingType"] = shipping_type
        return self._request(params)

    def get_order_items(self, order_id: str) -> Dict[str, Any]:
        """
        GetOrderItems. Obtiene los ítems de una orden por OrderId.
        Devuelve OrderItemId por cada ítem (necesarios para GetDocument/etiquetas).
        """
        params = self._base_params("GetOrderItems")
        params["OrderId"] = str(order_id)
        return self._request(params)

    def get_document(
        self,
        order_item_ids: List[int],
        document_type: str = "shippingParcel",
    ) -> Dict[str, Any]:
        """
        GetDocument. Obtiene la etiqueta de envío (shipping label) para los OrderItemIds dados.

        - document_type: debe ser "shippingParcel" (etiqueta de paquete).
        - Los ítems deben estar empaquetados (SetStatusToReadyToShip) antes de llamar.
        - Respuesta: Document con File (base64), MimeType (application/pdf o text/plain para ZPL).

        Returns:
            success, file_base64, mime_type, error
        """
        if not order_item_ids:
            return {"success": False, "error": "OrderItemIds es obligatorio"}
        params = self._base_params("GetDocument")
        params["DocumentType"] = document_type
        params["OrderItemIds"] = [int(x) for x in order_item_ids]
        result = self._request(params)
        if not result.get("success"):
            return result

        body = result.get("data", {}).get("Body") or result.get("data", {})
        doc = body if isinstance(body, dict) else body.get("Document", {})
        if isinstance(body, dict) and "Document" in body:
            doc = body["Document"]
        file_b64 = doc.get("File") or doc.get("file")
        mime = doc.get("MimeType") or doc.get("mime_type") or "application/pdf"
        return {
            "success": True,
            "file_base64": file_b64,
            "mime_type": mime,
            "data": result.get("data"),
        }

    def set_invoice_pdf(
        self,
        order_item_ids: List[int],
        invoice_number: str,
        invoice_date: str,
        invoice_type: str,
        operator_code: str,
        pdf_base64: str,
    ) -> Dict[str, Any]:
        """
        SetInvoicePDF. Sube el documento tributario (boleta/factura) en PDF a Falabella.
        Equivalente a la carga manual en: Seller Center > Order/Invoice > Upload documents.

        Requisitos:
        - La orden debe estar al menos en estado ready_to_ship.
        - Solo órdenes FBS (Fulfilled by Seller), no Own Warehouse/FBF.
        - invoice_date debe ser <= hoy.
        - invoice_type: BOLETA | FACTURA | NOTA_DE_CREDITO (BOLETA no válido en Colombia).
        - operator_code: FACL (Chile) | FACO (Colombia) | FAPE (Perú).

        Ref: https://developers.falabella.com/v600.0.0/reference/setinvoicepdf
        """
        url = f"{self.base_url}/v1/marketplace-sellers/invoice/pdf"
        params_for_signature = {
            "Action": "SetInvoicePDF",
            "Format": "JSON",
            "Service": "Invoice",
            "Timestamp": _iso8601_timestamp(),
            "UserID": self.user_id,
            "Version": "1.0",
        }
        signature = _build_signature(params_for_signature, self.api_key)
        headers = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Action": "SetInvoicePDF",
            "Format": "JSON",
            "Service": "Invoice",
            "Timestamp": params_for_signature["Timestamp"],
            "UserID": self.user_id,
            "Version": "1.0",
            "Signature": quote(signature, safe=""),
        }
        body = {
            "orderItemIds": [str(x) for x in order_item_ids],
            "invoiceNumber": str(invoice_number),
            "invoiceDate": str(invoice_date),
            "invoiceType": invoice_type.strip().upper(),
            "operatorCode": operator_code.strip().upper(),
            "invoiceDocumentFormat": "pdf",
            "invoiceDocument": pdf_base64,
        }
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            data = resp.json() if resp.content else {}
            if not resp.ok:
                return {
                    "success": False,
                    "error": data.get("message", data.get("ErrorMessage", resp.text or str(resp.status_code))),
                    "response": data,
                }
            return {"success": True, "data": data}
        except requests.RequestException as e:
            logger.exception("Falabella SetInvoicePDF error: %s", e)
            return {"success": False, "error": str(e), "response": {}}
        except ValueError:
            return {"success": False, "error": "Invalid JSON response", "response": {}}


def parse_order_items_response(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrae lista de OrderItem desde la respuesta de GetOrderItems."""
    if not result.get("success"):
        return []
    body = result.get("data", {}).get("Body") or result.get("data", {})
    if isinstance(body, dict) and "OrderItems" in body:
        items = body["OrderItems"]
        if isinstance(items, dict) and "OrderItem" in items:
            order_item_list = items["OrderItem"]
            if not isinstance(order_item_list, list):
                order_item_list = [order_item_list]
            return order_item_list
        if isinstance(items, list):
            return items
    return []
