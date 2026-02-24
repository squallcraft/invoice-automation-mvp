import React, { useState, useEffect } from 'react';
import api from '../api/client';
import './Dashboard.css';

export default function Dashboard() {
  const [sales, setSales] = useState([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchSales = async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      const { data } = await api.get(`/dashboard/sales?${params}`);
      setSales(data.sales);
      setTotal(data.total);
    } catch (err) {
      setError(err.response?.data?.error || 'Error al cargar ventas');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSales();
  }, [statusFilter]);

  const retrySale = async (saleId) => {
    try {
      await api.post(`/dashboard/sales/${saleId}/retry`);
      fetchSales();
    } catch (err) {
      alert(err.response?.data?.error || 'Error al reintentar');
    }
  };

  const statusClass = (s) => {
    if (s === 'Éxito') return 'status-ok';
    if (s === 'Error') return 'status-error';
    return 'status-pending';
  };

  return (
    <div className="dashboard">
      <h1>Historial de ventas</h1>
      <div className="dashboard-toolbar">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">Todos</option>
          <option value="Éxito">Éxito</option>
          <option value="Error">Error</option>
          <option value="Pendiente">Pendiente</option>
        </select>
        <button type="button" onClick={fetchSales}>Actualizar</button>
      </div>
      {error && <div className="dashboard-error">{error}</div>}
      {loading ? (
        <p>Cargando...</p>
      ) : (
        <div className="dashboard-table-wrap">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th>ID Venta</th>
                <th>Monto</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th>Fecha</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sales.length === 0 ? (
                <tr>
                  <td colSpan={6}>No hay ventas. Usa el flujo automático o sube un Excel/CSV.</td>
                </tr>
              ) : (
                sales.map((s) => (
                  <tr key={s.id}>
                    <td>{s.id_venta}</td>
                    <td>${Number(s.monto).toLocaleString()}</td>
                    <td>{s.tipo_doc}</td>
                    <td>
                      <span className={statusClass(s.status)}>{s.status}</span>
                      {s.error_message && (
                        <small title={s.error_message}> ({s.error_message.slice(0, 30)}…)</small>
                      )}
                    </td>
                    <td>{s.created_at ? new Date(s.created_at).toLocaleString() : '-'}</td>
                    <td>
                      {s.status === 'Error' && (
                        <button
                          type="button"
                          className="btn-retry"
                          onClick={() => retrySale(s.id)}
                        >
                          Reintentar
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <p className="dashboard-total">Total: {total} ventas</p>
        </div>
      )}
    </div>
  );
}
