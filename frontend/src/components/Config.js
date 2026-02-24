import React, { useState, useEffect } from 'react';
import api from '../api/client';
import './Config.css';

export default function Config() {
  const [haulmer, setHaulmer] = useState('');
  const [falabellaUserId, setFalabellaUserId] = useState('');
  const [falabella, setFalabella] = useState('');
  const [haulmerOk, setHaulmerOk] = useState(false);
  const [falabellaOk, setFalabellaOk] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get('/config/keys').then(({ data }) => {
      setHaulmerOk(data.haulmer_configured);
      setFalabellaOk(data.falabella_configured);
      setFalabellaUserId(data.falabella_user_id || '');
    }).catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage('');
    setLoading(true);
    try {
      const body = {};
      if (haulmer.trim()) body.haulmer_api_key = haulmer.trim();
      if (falabellaUserId.trim()) body.falabella_user_id = falabellaUserId.trim();
      if (falabella.trim()) body.falabella_api_key = falabella.trim();
      const { data } = await api.put('/config/keys', body);
      setHaulmerOk(data.haulmer_configured);
      setFalabellaOk(data.falabella_configured);
      setHaulmer('');
      setFalabella('');
      setMessage('Credenciales actualizadas correctamente.');
    } catch (err) {
      setMessage(err.response?.data?.error || 'Error al guardar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="config">
      <h1>Configuración de APIs</h1>
      <p className="config-desc">
        Guarda tus API keys de Haulmer y Falabella de forma segura (encriptadas). No compartas estas claves.
      </p>
      <div className="config-status">
        <span>Haulmer: {haulmerOk ? '✓ Configurado' : 'No configurado'}</span>
        <span>Falabella: {falabellaOk ? '✓ Configurado' : 'No configurado'}</span>
      </div>
      <form onSubmit={handleSubmit} className="config-form">
        <label>
          API Key Haulmer (dejar en blanco para no cambiar)
          <input
            type="password"
            placeholder="••••••••"
            value={haulmer}
            onChange={(e) => setHaulmer(e.target.value)}
          />
        </label>
        <label>
          Falabella Seller Center: User ID (email)
          <input
            type="text"
            placeholder="tu-email@sellercenter.falabella.com"
            value={falabellaUserId}
            onChange={(e) => setFalabellaUserId(e.target.value)}
          />
        </label>
        <label>
          Falabella Seller Center: API Key (dejar en blanco para no cambiar)
          <input
            type="password"
            placeholder="••••••••"
            value={falabella}
            onChange={(e) => setFalabella(e.target.value)}
          />
        </label>
        {message && <div className="config-message">{message}</div>}
        <button type="submit" disabled={loading || (!haulmer.trim() && !falabella.trim() && !falabellaUserId.trim())}>
          {loading ? 'Guardando...' : 'Guardar'}
        </button>
      </form>
    </div>
  );
}
