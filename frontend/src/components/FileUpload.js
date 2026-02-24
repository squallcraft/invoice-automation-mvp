import React, { useState, useCallback } from 'react';
import api from '../api/client';
import './FileUpload.css';

export default function FileUpload() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [valid, setValid] = useState(false);
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(async (fileObj) => {
    if (!fileObj || (!fileObj.name?.toLowerCase().endsWith('.csv') && !fileObj.name?.toLowerCase().match(/\.xlsx?$/))) {
      setPreview(null);
      setValid(false);
      setErrors(['Usa un archivo Excel (.xlsx, .xls) o CSV']);
      return;
    }
    setFile(fileObj);
    setResult(null);
    setLoading(true);
    setErrors([]);
    try {
      const formData = new FormData();
      formData.append('file', fileObj);
      const { data } = await api.post('/semi/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setPreview(data.preview || []);
      setValid(data.valid === true);
      setErrors(data.errors || []);
    } catch (err) {
      setPreview(null);
      setValid(false);
      setErrors([err.response?.data?.error || 'Error al validar archivo']);
    } finally {
      setLoading(false);
    }
  }, []);

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) handleFile(f);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const onDragLeave = () => setDragOver(false);

  const onInputChange = (e) => {
    const f = e.target?.files?.[0];
    if (f) handleFile(f);
  };

  const handleProcessBatch = async () => {
    if (!preview?.length || !valid) return;
    setProcessing(true);
    setResult(null);
    try {
      const { data } = await api.post('/semi/process-batch', { rows: preview });
      setResult(data);
    } catch (err) {
      setResult({ error: err.response?.data?.error || 'Error al procesar' });
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="file-upload">
      <h1>Subir Excel / CSV</h1>
      <p className="file-upload-desc">
        Columnas esperadas: <strong>id_venta</strong>, <strong>tipo_documento</strong> (Boleta o Factura), <strong>monto</strong>.
      </p>

      <div
        className={`dropzone ${dragOver ? 'dropzone-active' : ''}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
      >
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={onInputChange}
          className="dropzone-input"
        />
        {loading ? (
          <span>Validando...</span>
        ) : (
          <span>Arrastra un archivo aquí o haz clic para seleccionar</span>
        )}
      </div>

      {errors.length > 0 && (
        <ul className="file-upload-errors">
          {errors.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      )}

      {preview && preview.length > 0 && (
        <>
          <h2>Vista previa</h2>
          <div className="preview-table-wrap">
            <table className="preview-table">
              <thead>
                <tr>
                  <th>ID Venta</th>
                  <th>Tipo documento</th>
                  <th>Monto</th>
                </tr>
              </thead>
              <tbody>
                {preview.map((row, i) => (
                  <tr key={i}>
                    <td>{row.id_venta}</td>
                    <td>{row.tipo_documento}</td>
                    <td>${Number(row.monto).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="preview-valid">
            {valid ? '✓ Archivo válido. Puedes procesar.' : '✗ Corrige los errores antes de procesar.'}
          </p>
          <button
            type="button"
            className="btn-process"
            disabled={!valid || processing}
            onClick={handleProcessBatch}
          >
            {processing ? 'Procesando...' : 'Emitir en lote y generar ZIP'}
          </button>
        </>
      )}

      {result && (
        <div className="file-upload-result">
          <h3>Resultado</h3>
          {result.error ? (
            <p className="result-error">{result.error}</p>
          ) : (
            <>
              <p>{result.message}</p>
              {result.results?.length > 0 && (
                <ul>
                  {result.results.slice(0, 10).map((r, i) => (
                    <li key={i}>{r.id_venta}: {r.status}</li>
                  ))}
                  {result.results.length > 10 && <li>… y {result.results.length - 10} más</li>}
                </ul>
              )}
              {result.download_url && (
                <p><a href={result.download_url} target="_blank" rel="noreferrer">Descargar ZIP</a></p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
