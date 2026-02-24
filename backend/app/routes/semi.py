"""
Flujo semi-automático: subir Excel/CSV, validar, previsualizar, emitir en lote y entregar ZIP.
"""
import io
import zipfile
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import pandas as pd
from app import db
from app.models import User, Sale, Document
from app.crypto_utils import decrypt_value
from app.services.haulmer_client import HaulmerClient

logger = logging.getLogger(__name__)
semi_bp = Blueprint("semi", __name__)

# Columnas esperadas en Excel/CSV
EXPECTED_COLUMNS = {"id_venta", "tipo_documento", "monto"}
COLUMN_ALIASES = {"id_venta": ["id_venta", "id venta", "id"], "tipo_documento": ["tipo_documento", "tipo documento", "tipo_doc", "tipo"], "monto": ["monto", "total", "amount"]}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nombres de columnas a id_venta, tipo_documento, monto."""
    mapping = {}
    for col in df.columns:
        c = str(col).strip().lower()
        for std, aliases in COLUMN_ALIASES.items():
            if c in [a.lower() for a in aliases]:
                mapping[col] = std
                break
    return df.rename(columns=mapping)


def _validate_rows(df: pd.DataFrame):
    """Valida filas: duplicados, montos válidos, tipo correcto. Retorna (rows_ok, errors)."""
    df = _normalize_columns(df)
    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        return [], [f"Faltan columnas: {missing}"]

    rows = []
    errors = []
    seen_ids = set()
    for i, row in df.iterrows():
        id_venta = str(row.get("id_venta", "")).strip()
        tipo = (str(row.get("tipo_documento", "Boleta")).strip() or "Boleta")
        try:
            monto = float(row.get("monto", 0))
        except (TypeError, ValueError):
            monto = 0

        if not id_venta:
            errors.append(f"Fila {i + 2}: id_venta vacío")
            continue
        if id_venta in seen_ids:
            errors.append(f"Fila {i + 2}: id_venta duplicado {id_venta}")
            continue
        seen_ids.add(id_venta)
        if monto <= 0:
            errors.append(f"Fila {i + 2}: monto inválido {row.get('monto')}")
            continue
        if tipo not in ("Boleta", "Factura"):
            errors.append(f"Fila {i + 2}: tipo_documento debe ser Boleta o Factura")
            continue
        rows.append({"id_venta": id_venta, "tipo_documento": tipo, "monto": monto})
    return rows, errors


@semi_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload():
    """
    Recibe archivo Excel o CSV. Valida y devuelve previsualización (lista de filas)
    para que el front muestre tabla y botón OK solo si validación ok.
    """
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user or not user.haulmer_api_key_enc:
        return jsonify({"error": "Configura tu API key de Haulmer en /config/keys"}), 400

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "Envía un archivo (Excel o CSV)"}), 400

    try:
        if file.filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file, encoding="utf-8-sig")
    except Exception as e:
        return jsonify({"error": f"Error leyendo archivo: {e}"}), 400

    rows, errors = _validate_rows(df)
    return jsonify({
        "preview": rows,
        "valid": len(errors) == 0,
        "errors": errors,
    })


@semi_bp.route("/process-batch", methods=["POST"])
@jwt_required()
def process_batch():
    """
    Recibe el body con la lista de filas ya validadas (o re-valida),
    emite en lote vía Haulmer, crea Sales/Documents, y devuelve ZIP con PDFs
    o enlace para descarga. Idempotencia por user_id + id_venta.
    """
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user or not user.haulmer_api_key_enc:
        return jsonify({"error": "Configura tu API key de Haulmer"}), 400

    data = request.get_json() or {}
    rows = data.get("rows", data.get("preview", []))
    if not rows:
        return jsonify({"error": "No hay filas para procesar"}), 400

    haulmer = HaulmerClient(decrypt_value(user.haulmer_api_key_enc))
    results = []
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            id_venta = str(row.get("id_venta", "")).strip()
            tipo_doc = (row.get("tipo_documento") or "Boleta").strip()
            monto = float(row.get("monto", 0))

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
                if not sale.document_date:
                    sale.document_date = datetime.utcnow().date()
                doc = Document(
                    user_id=user.id,
                    sale_id=sale.id,
                    pdf_url=result.get("pdf_url"),
                    xml_url=result.get("xml_url"),
                    haulmer_response=str(result.get("raw", "")),
                )
                db.session.add(doc)
                # Si Haulmer devuelve URL de PDF, podrías descargar y añadir al ZIP; aquí placeholder
                zf.writestr(f"{id_venta}.pdf", b"")  # Reemplazar con contenido real si hay URL
                results.append({"id_venta": id_venta, "status": "Éxito"})
            else:
                sale.status = "Error"
                sale.error_message = result.get("error")
                results.append({"id_venta": id_venta, "status": "Error", "error": result.get("error")})

    db.session.commit()
    zip_buffer.seek(0)

    # Opción 1: devolver JSON con resultados y enlace a ZIP
    # Opción 2: devolver el ZIP directamente
    if request.args.get("format") == "zip":
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="documentos.zip",
        )
    return jsonify({
        "message": "Procesamiento en lote completado",
        "results": results,
        "zip_available": True,
        "download_url": "/semi/download-batch?token=...",  # Implementar token corto si quieres
    })


@semi_bp.route("/download-batch", methods=["GET"])
@jwt_required()
def download_batch():
    """Descarga del ZIP generado en la última ejecución (simplificado: regenerar si necesario)."""
    # Para MVP se puede pedir al cliente que llame a process-batch?format=zip
    return jsonify({"error": "Usa POST /semi/process-batch?format=zip para descargar ZIP"}), 400
