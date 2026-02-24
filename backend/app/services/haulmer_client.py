"""
Cliente para API Haulmer (OpenFactura) - emisión de boletas/facturas.
Documentación: https://docsapi-openfactura.haulmer.com/
En MVP se usan endpoints típicos; ajustar según documentación real de Haulmer.
"""
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class HaulmerClient:
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = (base_url or "https://docsapi-openfactura.haulmer.com").rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def emit_document(self, tipo_doc: str, id_venta: str, monto: float, **kwargs) -> Dict[str, Any]:
        """
        Emite boleta o factura. tipo_doc: 'Boleta' | 'Factura'.
        Retorna dict con pdf_url, xml_url, o error.
        """
        # Payload típico según documentación Haulmer; adaptar a su API real
        payload = {
            "tipo": "boleta" if tipo_doc.lower() == "boleta" else "factura",
            "folio": None,
            "descripcion": f"Venta {id_venta}",
            "monto": round(monto, 2),
            **kwargs,
        }
        try:
            # Endpoint de ejemplo; revisar docs Haulmer para el correcto
            url = f"{self.base_url}/v2/dte/document"
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return {
                "success": True,
                "pdf_url": data.get("pdf_url") or data.get("pdf"),
                "xml_url": data.get("xml_url") or data.get("xml"),
                "raw": data,
            }
        except requests.RequestException as e:
            logger.exception("Haulmer API error: %s", e)
            return {
                "success": False,
                "error": str(e),
                "pdf_url": None,
                "xml_url": None,
            }
