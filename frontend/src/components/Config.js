import React, { useState, useEffect } from 'react';
import api from '../api/client';
import './Config.css';

export default function Config() {
  const [haulmer, setHaulmer] = useState('');
  const [falabellaUserId, setFalabellaUserId] = useState('');
  const [falabellaEmail, setFalabellaEmail] = useState('');
  const [falabellaToken, setFalabellaToken] = useState('');
  const [haulmerOk, setHaulmerOk] = useState(false);
  const [falabellaOk, setFalabellaOk] = useState(false);
  const [mlOk, setMlOk] = useState(false);
  const [mlUserId, setMlUserId] = useState('');
  const [loadingFalabella, setLoadingFalabella] = useState(false);
  const [loadingHaulmer, setLoadingHaulmer] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('success');

  const loadKeys = () => {
    api.get('/config/keys').then(({ data }) => {
      setHaulmerOk(data.haulmer_configured);
      setFalabellaOk(data.falabella_configured);
      setMlOk(data.mercado_libre_configured);
      setMlUserId(data.ml_user_id || '');
      setFalabellaUserId(data.falabella_user_id || '');
      setFalabellaEmail(data.falabella_user_id || '');
    }).catch(() => {});
  };

  useEffect(() => {
    loadKeys();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const mlConnected = params.get('ml_connected');
    const mlError = params.get('ml_error');
    if (mlConnected === '1') {
      setMessage('Mercado Libre conectado correctamente.');
      setMessageType('success');
      setMlOk(true);
      loadKeys();
      window.history.replaceState({}, '', window.location.pathname);
    } else if (mlError) {
      const messages = {
        server_config: 'El servidor no tiene configurado ML_CLIENT_ID / ML_REDIRECT_URI.',
        no_code: 'Mercado Libre no devolvió código de autorización.',
        token_exchange: 'Error al obtener tokens de Mercado Libre.',
        no_tokens: 'Mercado Libre no devolvió tokens.',
        invalid_state: 'Sesión inválida. Vuelve a iniciar sesión y conecta ML.',
        user_not_found: 'Usuario no encontrado.',
      };
      setMessage(messages[mlError] || `Error: ${mlError}`);
      setMessageType('error');
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  const handleConnectMercadoLibre = () => {
    setMessage('');
    api.get('/mercado-libre/auth-url')
      .then(({ data }) => {
        if (data.url) window.location.href = data.url;
        else {
          setMessage('No se obtuvo la URL de autorización.');
          setMessageType('error');
        }
      })
      .catch((err) => {
        setMessage(err.response?.status === 401 ? 'Sesión expirada. Vuelve a iniciar sesión.' : 'No se pudo conectar con Mercado Libre.');
        setMessageType('error');
      });
  };

  const handleDisconnectMercadoLibre = () => {
    if (!window.confirm('¿Desconectar Mercado Libre? Tendrás que autorizar de nuevo para volver a conectar.')) return;
    setMessage('');
    api.post('/mercado-libre/disconnect')
      .then(() => {
        setMlOk(false);
        setMlUserId('');
        setMessage('Mercado Libre desconectado.');
        setMessageType('success');
      })
      .catch((err) => {
        setMessage(err.response?.data?.error || 'Error al desconectar');
        setMessageType('error');
      });
  };

  const handleSubmitFalabella = async (e) => {
    e.preventDefault();
    setMessage('');
    setLoadingFalabella(true);
    try {
      const body = {};
      if (falabellaUserId.trim()) body.falabella_user_id = falabellaUserId.trim();
      if (falabellaToken.trim()) body.falabella_api_key = falabellaToken.trim();
      await api.put('/config/keys', body);
      setFalabellaOk(!!(falabellaUserId.trim() && (falabellaToken.trim() || falabellaOk)));
      setFalabellaToken('');
      setMessage('Datos de Falabella guardados.');
      setMessageType('success');
    } catch (err) {
      setMessage(err.response?.data?.error || 'Error al guardar');
      setMessageType('error');
    } finally {
      setLoadingFalabella(false);
    }
  };

  const handleSubmitHaulmer = async (e) => {
    e.preventDefault();
    setMessage('');
    setLoadingHaulmer(true);
    try {
      const body = {};
      if (haulmer.trim()) body.haulmer_api_key = haulmer.trim();
      await api.put('/config/keys', body);
      setHaulmerOk(!!(haulmer.trim() || haulmerOk));
      setHaulmer('');
      setMessage('API Key de Haulmer guardada.');
      setMessageType('success');
    } catch (err) {
      setMessage(err.response?.data?.error || 'Error al guardar');
      setMessageType('error');
    } finally {
      setLoadingHaulmer(false);
    }
  };

  return (
    <div className="config-page">
      <header className="config-banner">
        <h1 className="config-banner-title">INTEGRACIONES</h1>
      </header>

      {message && (
        <div className={`config-message ${messageType === 'error' ? 'config-message-error' : ''}`}>
          {message}
        </div>
      )}

      {/* Card: Mercado Libre (bloque superior) */}
      <section className="config-card config-card-ml">
        <h2 className="config-card-title">Mercado Libre</h2>
        <p className="config-card-instructions">
          Para integrar Mercado Libre debe contar con una tienda registrada. Abra su sesión de Mercado Libre; para otra tienda, cierre sesión en ML e inicie con la siguiente cuenta.
        </p>
        <div className="config-ml-block">
          <div className="config-ml-row">
            <span className="config-ml-label">Nombre de tienda</span>
            <span className="config-ml-value">{mlOk ? 'Cuenta principal' : '—'}</span>
          </div>
          <div className="config-ml-row">
            <span className="config-ml-label">ID de tienda</span>
            <span className="config-ml-value">{mlOk ? (mlUserId || '—') : '—'}</span>
          </div>
          <div className="config-ml-actions">
            {mlOk ? (
              <>
                <button type="button" className="config-btn-icon" onClick={loadKeys} title="Actualizar">↻</button>
                <button type="button" className="config-btn-ml config-btn-ml-disconnect" onClick={handleDisconnectMercadoLibre}>
                  Desconectar
                </button>
              </>
            ) : (
              <button type="button" className="config-btn-ml config-btn-ml-plus" onClick={handleConnectMercadoLibre} title="Vincular con Mercado Libre">
                + Conectar Mercado Libre
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Card: Falabella */}
      <section className="config-card">
        <h2 className="config-card-title config-card-title-falabella">
          <span className="config-falabella-logo">F</span> Integración Falabella
        </h2>
        <form onSubmit={handleSubmitFalabella} className="config-form config-form-inline">
          <div className="config-form-row">
            <label>
              Tienda
              <select className="config-input" value="Principal" readOnly>
                <option>Principal</option>
              </select>
            </label>
            <label>
              User ID
              <input
                type="text"
                className="config-input"
                placeholder="tu-email@sellercenter.falabella.com"
                value={falabellaUserId}
                onChange={(e) => { setFalabellaUserId(e.target.value); setFalabellaEmail(e.target.value); }}
              />
            </label>
            <label>
              Email
              <input
                type="text"
                className="config-input"
                placeholder="tu-email@ejemplo.com"
                value={falabellaEmail}
                onChange={(e) => { setFalabellaEmail(e.target.value); setFalabellaUserId(e.target.value); }}
              />
            </label>
            <label>
              Token
              <input
                type="password"
                className="config-input"
                placeholder="Dejar en blanco para no cambiar"
                value={falabellaToken}
                onChange={(e) => setFalabellaToken(e.target.value)}
              />
            </label>
            <div className="config-form-actions">
              <button type="submit" className="config-btn-send" disabled={loadingFalabella}>
                {loadingFalabella ? 'Guardando…' : 'ENVIAR DATOS'}
              </button>
            </div>
          </div>
        </form>
      </section>

      {/* Card: Haulmer */}
      <section className="config-card">
        <h2 className="config-card-title">Integración Haulmer</h2>
        <p className="config-card-desc">API Key de Haulmer para emisión de boletas y facturas. Las credenciales se guardan encriptadas.</p>
        <form onSubmit={handleSubmitHaulmer} className="config-form config-form-inline">
          <div className="config-form-row">
            <label>
              API Key
              <input
                type="password"
                className="config-input config-input-wide"
                placeholder="Dejar en blanco para no cambiar"
                value={haulmer}
                onChange={(e) => setHaulmer(e.target.value)}
              />
            </label>
            <div className="config-form-actions">
              <button type="submit" className="config-btn-send" disabled={loadingHaulmer || !haulmer.trim()}>
                {loadingHaulmer ? 'Guardando…' : 'ENVIAR DATOS'}
              </button>
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
