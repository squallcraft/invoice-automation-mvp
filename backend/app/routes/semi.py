"""
Flujo semi-automático: subir Excel/CSV, validar, previsualizar y emitir en lote.
"""
import io
import logging
import zipfile
from datetime import datetime
from typing import List, Tuple

import pandas as pd
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.crypto_utils import decrypt_value
from app.models import Document, Sale, User
from app.services.haulmer_client import HaulmerClient
from app.utils import err, require_user

logger = logging.getLogger(__name__)
semi_bp = Blueprint("semi", __name__)

_EXPECTED = {"id_venta", "tipo_documento", "monto"}
_ALIASES  = {
    "id_venta":       ["id_venta", "id venta", "id"],
    "tipo_documento": ["tipo_documento", "tipo documento", "tipo_doc", "tipo"],
    "monto":          ["monto", "total", "amount"],
}


# ── Validación de archivo ──────────────────────────────────────────────────

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        c = str(col).strip().lower()
        for std, aliases in _ALIASES.items():
            if c in aliases:
                mapping[col] = std
                break
    return df.rename(columns=mapping)


def _validate_rows(df: pd.DataFrame) -> Tuple[List[dict], List[str]]:
    df      = _normalize_columns(df)
    missing = _EXPECTED - set(df.columns)
    if missing:
        return [], [f"Faltan columnas: {missing}"]

    rows, errors, seen = [], [], set()
    for i, row in df.iterrows():
        id_venta = str(row.get("id_venta", "")).strip()
        tipo     = (str(row.get("tipo_documento", "Boleta")).strip() or "Boleta")
        try:
            monto = float(row.get("monto", 0))
        except (TypeError, ValueError):
            monto = 0.0

        linea = i + 2
        if not id_venta:
            errors.append(f"Fila {linea}: id_venta vacío"); continue
        if id_venta in seen:
            errors.append(f"Fila {linea}: id_venta duplicado ({id_venta})"); continue
        seen.add(id_venta)
        if monto <= 0:
            errors.append(f"Fila {linea}: monto inválido ({row.get('monto')})"); continue
        if tipo not in ("Boleta", "Factura"):
            errors.append(f"Fila {linea}: tipo_documento debe ser Boleta o Factura"); continue

        rows.append({"id_venta": id_venta, "tipo_documento": tipo, "monto": monto})
    return rows, errors


# ── Rutas ──────────────────────────────────────────────────────────────────

@semi_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """Recibe Excel/CSV, valida y devuelve previsualización."""
    user, error = require_user()
    if error:
        return error
    if not user.haulmer_api_key_enc:
        return err("Configura tu API key de Haulmer en /config/keys")

    file = request.files.get("file")
    if not file or file.filename == "":
        return err("Envía un archivo (Excel o CSV)")

    try:
        fname = (file.filename or "").lower()
        df    = pd.read_excel(file) if fname.endswith((".xlsx", ".xls")) else pd.read_csv(file, encoding="utf-8-sig")
    except Exception as e:
        return err(f"Error leyendo archivo: {e}")

    rows, errors = _validate_rows(df)
    return jsonify({"preview": rows, "valid": len(errors) == 0, "errors": errors})


@semi_bp.route("/process-batch", methods=["POST"])
@jwt_required()
def process_batch():
    """
    Emite en lote los documentos de la lista validada.
    Query param: format=zip → devuelve ZIP de PDFs en lugar de JSON.
    """
    user, error = require_user()
    if error:
        return error
    if not user.haulmer_api_key_enc:
        return err("Configura tu API key de Haulmer")

    data = request.get_json() or {}
    rows = data.get("rows") or data.get("preview") or []
    if not rows:
        return err("No hay filas para procesar")

    haulmer    = HaulmerClient(decrypt_value(user.haulmer_api_key_enc))
    results    = []
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            id_venta = str(row.get("id_venta", "")).strip()
            tipo_doc = (row.get("tipo_documento") or "Boleta").strip()
            monto    = float(row.get("monto", 0))

            sale = Sale.query.filter_by(user_id=user.id, id_venta=id_venta).first()
            if sale and sale.status == "Éxito":
                results.append({"id_venta": id_venta, "status": "Éxito", "skipped": True})
                continue

            if not sale:
                sale = Sale(
                    user_id=user.id,
                    id_venta=id_venta,
                    monto=monto,
                    tipo_doc=tipo_doc,
                    status="Pendiente",
                    platform="Manual",
                    document_date=datetime.utcnow().date(),
                )
                db.session.add(sale)
                db.session.flush()

            result = haulmer.emit_document(tipo_doc=tipo_doc, id_venta=id_venta, monto=monto)

            if result.get("success"):
                sale.status = "Éxito"
                sale.document_date = sale.document_date or datetime.utcnow().date()
                db.session.add(Document(
                    user_id=user.id,
                    sale_id=sale.id,
                    pdf_url=result.get("pdf_url"),
                    xml_url=result.get("xml_url"),
                    haulmer_response=str(result.get("raw", ""))[:4000],
                ))
                zf.writestr(f"{id_venta}.pdf", b"")  # placeholder; reemplazar con PDF real
                results.append({"id_venta": id_venta, "status": "Éxito"})
            else:
                sale.status        = "Error"
                sale.error_message = result.get("error")
                results.append({"id_venta": id_venta, "status": "Error", "error": result.get("error")})

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.exception("process_batch commit: %s", e)
        return err(f"Error al guardar: {e}", 500)

    zip_buffer.seek(0)

    if request.args.get("format") == "zip":
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="documentos.zip",
        )

    return jsonify({
        "message":      "Procesamiento en lote completado",
        "results":      results,
        "zip_available": True,
        "download_url": "/semi/process-batch?format=zip",
    })


@semi_bp.route("/download-batch", methods=["GET"])
@jwt_required()
def download_batch():
    """Para descargar el ZIP llama a POST /semi/process-batch?format=zip."""
    return err("Usa POST /semi/process-batch?format=zip para descargar el ZIP")
