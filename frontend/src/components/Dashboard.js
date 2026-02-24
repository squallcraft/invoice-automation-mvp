import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/client';
import './Dashboard.css';

const PER_PAGE = 30;

export default function Dashboard() {
  const [sales, setSales] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [platformFilter, setPlatformFilter] = useState('');
  const [documentStatusFilter, setDocumentStatusFilter] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [searchSent, setSearchSent] = useState('');
  const [sortBy, setSortBy] = useState('document_date');
  const [sortOrder, setSortOrder] = useState('desc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(false);
  const [processResult, setProcessResult] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());

  const fetchSales = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('per_page', String(PER_PAGE));
      params.set('sort_by', sortBy);
      params.set('sort_order', sortOrder);
      if (platformFilter) params.set('platform', platformFilter);
      if (documentStatusFilter) params.set('document_status', documentStatusFilter);
      if (searchSent) params.set('search', searchSent);
      const { data } = await api.get(`/dashboard/sales?${params}`);
      setSales(data.sales);
      setTotal(data.total);
      setTotalPages(data.total_pages || Math.ceil((data.total || 0) / PER_PAGE));
    } catch (err) {
      setError(err.response?.data?.error || 'Error al cargar ventas');
    } finally {
      setLoading(false);
    }
  }, [page, sortBy, sortOrder, platformFilter, documentStatusFilter, searchSent]);

  useEffect(() => {
    fetchSales();
  }, [fetchSales]);

  const handleSort = (key) => {
    if (sortBy === key) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const handleSearch = () => {
    setSearchSent(searchInput.trim());
    setPage(1);
  };

  const docEstado = (s) => s.documento || (s.documento_cargado ? 'Cargado' : s.status === 'Éxito' ? 'Emitido' : 'Por emitir');
  const canSelect = (s) => docEstado(s) !== 'Cargado';

  const toggleSelect = (s) => {
    if (!canSelect(s)) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(s.id)) next.delete(s.id);
      else next.add(s.id);
      return next;
    });
  };

  const selectAll = () => {
    const selectable = sales.filter(canSelect);
    const allSelected = selectable.length > 0 && selectable.every((s) => selectedIds.has(s.id));
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(selectable.map((s) => s.id)));
    }
  };

  const runProcessSelected = async () => {
    const selected = sales.filter((s) => selectedIds.has(s.id));
    if (selected.length === 0) return;
    setProcessing(true);
    setProcessResult(null);
    setError('');
    try {
      const orders = selected.map((s) => ({
        id_venta: s.id_venta,
        monto: Number(s.monto),
        tipo_documento: s.tipo_doc,
        platform: s.platform || 'Manual',
      }));
      const { data } = await api.post('/auto/process', { orders });
      setProcessResult({
        ok: data.processed > 0,
        message: data.message,
        processed: data.processed,
        errors: data.errors,
      });
      setSelectedIds(new Set());
      fetchSales();
    } catch (err) {
      setProcessResult({
        ok: false,
        message: err.response?.data?.error || 'Error al procesar',
      });
    } finally {
      setProcessing(false);
    }
  };

  const retrySale = async (sale) => {
    try {
      const { data } = await api.post('/auto/process', {
        orders: [{
          id_venta: sale.id_venta,
          monto: Number(sale.monto),
          tipo_documento: sale.tipo_doc,
          platform: sale.platform || 'Manual',
        }],
        retry: true,
      });
      setProcessResult(data.processed > 0 ? { ok: true, message: data.message } : { ok: false, message: data.message, errors: data.errors });
      fetchSales();
    } catch (err) {
      setProcessResult({ ok: false, message: err.response?.data?.error || 'Error al reintentar' });
    }
  };

  const statusClass = (s) => {
    if (s === 'Éxito') return 'status-ok';
    if (s === 'Error') return 'status-error';
    return 'status-pending';
  };

  const sortIcon = (key) => {
    if (sortBy !== key) return ' ↕';
    return sortOrder === 'asc' ? ' ↑' : ' ↓';
  };

  return (
    <div className="dashboard">
      <h1>Ventas</h1>
      <div className="dashboard-toolbar">
        <input
          type="text"
          className="dashboard-search"
          placeholder="Buscar por ID de venta o ID de orden..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        />
        <button type="button" onClick={handleSearch}>Buscar</button>
        <select
          value={platformFilter}
          onChange={(e) => { setPlatformFilter(e.target.value); setPage(1); }}
          aria-label="Filtrar por plataforma"
        >
          <option value="">Todas las plataformas</option>
          <option value="Falabella">Falabella</option>
          <option value="Mercado Libre">Mercado Libre</option>
          <option value="Manual">Manual</option>
        </select>
        <select
          value={documentStatusFilter}
          onChange={(e) => { setDocumentStatusFilter(e.target.value); setPage(1); }}
          aria-label="Filtrar por estado de documento"
        >
          <option value="">Todos los documentos</option>
          <option value="Por emitir">Por emitir</option>
          <option value="Emitido">Emitido</option>
          <option value="Cargado">Cargado</option>
        </select>
        <button type="button" onClick={fetchSales}>Actualizar</button>
        {selectedIds.size > 0 && (
          <button
            type="button"
            className="dashboard-btn-process"
            onClick={runProcessSelected}
            disabled={loading || processing}
          >
            {processing ? 'Procesando…' : `Procesar (${selectedIds.size})`}
          </button>
        )}
      </div>
      {processResult && (
        <div className={`dashboard-result ${processResult.ok ? 'dashboard-result-ok' : 'dashboard-result-error'}`}>
          {processResult.message}
          {processResult.errors?.length > 0 && (
            <span className="dashboard-result-errors"> ({processResult.errors.length} error/es)</span>
          )}
        </div>
      )}
      {error && <div className="dashboard-error">{error}</div>}
      {loading ? (
        <p>Cargando...</p>
      ) : (
        <div className="dashboard-table-wrap">
          <table className="dashboard-table">
            <thead>
              <tr>
                <th className="th-checkbox">
                  <input
                    type="checkbox"
                    checked={sales.filter(canSelect).length > 0 && sales.filter(canSelect).every((s) => selectedIds.has(s.id))}
                    disabled={sales.filter(canSelect).length === 0}
                    onChange={selectAll}
                    title="Seleccionar solo ventas sin documento cargado"
                  />
                </th>
                <th className="th-sortable" onClick={() => handleSort('document_date')}>Fecha de venta{sortIcon('document_date')}</th>
                <th className="th-sortable" onClick={() => handleSort('platform')}>Plataforma{sortIcon('platform')}</th>
                <th className="th-sortable" onClick={() => handleSort('id_venta')}>ID de venta{sortIcon('id_venta')}</th>
                <th>ID de orden</th>
                <th className="th-sortable" onClick={() => handleSort('status')}>Estado de la orden{sortIcon('status')}</th>
                <th className="th-sortable" onClick={() => handleSort('documento')}>Documento{sortIcon('documento')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sales.length === 0 ? (
                <tr>
                  <td colSpan={8}>No hay ventas. La sincronización trae ventas automáticamente desde Falabella y Mercado Libre.</td>
                </tr>
              ) : (
                sales.map((s) => {
                  const documento = docEstado(s);
                  const isSelectable = canSelect(s);
                  return (
                    <tr key={s.id} className={selectedIds.has(s.id) ? 'row-selected' : ''}>
                      <td className="td-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(s.id)}
                          disabled={!isSelectable}
                          onChange={() => toggleSelect(s)}
                          title={isSelectable ? 'Seleccionar para procesar' : 'Ya tiene documento cargado'}
                        />
                      </td>
                      <td>{s.document_date ? new Date(s.document_date).toLocaleDateString() : '-'}</td>
                      <td>{s.platform || 'Manual'}</td>
                      <td>{s.id_venta}</td>
                      <td>{s.id_orden || s.id_venta}</td>
                      <td>
                        <span className={statusClass(s.status)}>{s.status}</span>
                        {s.error_message && (
                          <small title={s.error_message}> ({s.error_message.slice(0, 30)}…)</small>
                        )}
                      </td>
                      <td>{documento}</td>
                      <td>
                        {s.status === 'Error' && (
                          <button type="button" className="btn-retry" onClick={() => retrySale(s)}>Reintentar</button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          <div className="dashboard-pagination">
            <span className="dashboard-total">Total: {total} ventas</span>
            {totalPages > 1 && (
              <div className="dashboard-pagination-controls">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Anterior
                </button>
                <span>Página {page} de {totalPages}</span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Siguiente
                </button>
              </div>
            )}
          </div>
          <p className="dashboard-legend">
            Documento: <strong>Por emitir</strong> = pendiente · <strong>Emitido</strong> = emitido en Haulmer · <strong>Cargado</strong> = subido en la plataforma (Falabella / Mercado Libre). No se reemite si ya está cargado.
          </p>
        </div>
      )}
    </div>
  );
}
