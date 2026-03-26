import { useState, useEffect, useCallback, Fragment } from 'react';
import { Download, ChevronDown, ChevronUp, XCircle, CheckCircle, ShoppingCart, Ban, Clock } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import { todayStr } from '../lib/dateUtils';
import Modal from '../components/ui/Modal';
import Spinner from '../components/ui/Spinner';

const STATUS_OPTIONS = [
  { value: '', label: 'Todas' },
  { value: 'completed', label: 'Completadas' },
  { value: 'pending', label: 'Pendientes' },
  { value: 'voided', label: 'Anuladas' },
];

const PAYMENT_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'datafono', label: 'Datafono' },
  { value: 'transferencia', label: 'Transferencia' },
  { value: 'fiado', label: 'Por cobrar' },
];

const LIMIT = 20;

function StatusBadge({ status }) {
  const map = {
    completed: { bg: 'bg-green-100 text-green-700', label: 'Completada' },
    pending: { bg: 'bg-yellow-100 text-yellow-700', label: 'Pendiente' },
    voided: { bg: 'bg-red-100 text-red-700', label: 'Anulada' },
  };
  const s = map[status] || { bg: 'bg-gray-100 text-gray-700', label: status };
  return <span className={`${s.bg} px-2.5 py-0.5 rounded-full text-xs font-medium`}>{s.label}</span>;
}

export default function SalesHistoryPage() {
  const { addToast } = useToast();
  const [dateFrom, setDateFrom] = useState(todayStr());
  const [dateTo, setDateTo] = useState(todayStr());
  const [status, setStatus] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [sales, setSales] = useState([]);
  const [summary, setSummary] = useState({ total_count: 0, total_amount: 0, voided_count: 0, fiado_pending: 0 });
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [expandedIds, setExpandedIds] = useState(new Set());
  const [expandedSaleData, setExpandedSaleData] = useState({});
  const [voidModal, setVoidModal] = useState({ open: false, saleId: null });
  const [voidReason, setVoidReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const fetchSales = useCallback(async (newOffset = 0) => {
    setLoading(true);
    try {
      const params = {
        date_from: dateFrom,
        date_to: dateTo,
        limit: LIMIT,
        offset: newOffset,
      };
      if (status) params.status = status;
      if (paymentMethod) params.payment_method = paymentMethod;

      const res = await api.get('/sales', { params });
      const salesData = Array.isArray(res.data) ? res.data : (res.data.sales ?? res.data.items ?? []);
      setSales(salesData);
      // Compute summary client-side
      const total_count = salesData.length;
      const total_amount = salesData.filter(s => s.status !== 'voided').reduce((sum, s) => sum + s.total, 0);
      const voided_count = salesData.filter(s => s.status === 'voided').length;
      const fiado_pending = salesData.filter(s => s.status === 'pending').reduce((sum, s) => sum + s.total, 0);
      setSummary({ total_count, total_amount, voided_count, fiado_pending });
      setHasMore(salesData.length === LIMIT);
      setOffset(newOffset);
    } catch {
      addToast('Error al cargar ventas', 'error');
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, status, paymentMethod, addToast]);

  useEffect(() => { fetchSales(0); }, [fetchSales]);

  const handleVoid = async () => {
    if (!voidReason.trim()) {
      addToast('Debes ingresar un motivo', 'error');
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/sales/${voidModal.saleId}/void`, { reason: voidReason });
      addToast('Venta anulada correctamente', 'success');
      setVoidModal({ open: false, saleId: null });
      setVoidReason('');
      fetchSales(offset);
    } catch {
      addToast('Error al anular la venta', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleMarkPaid = async (saleId) => {
    try {
      await api.post(`/sales/${saleId}/pay`);
      addToast('Marcada como pagada', 'success');
      fetchSales(offset);
    } catch {
      addToast('Error al marcar como pagada', 'error');
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = { date_from: dateFrom, date_to: dateTo };
      if (status) params.status = status;
      if (paymentMethod) params.payment_method = paymentMethod;
      const res = await api.get('/reports/export/sales', { params, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `ventas_${dateFrom}_${dateTo}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      addToast('CSV exportado correctamente', 'success');
    } catch {
      addToast('Error al exportar CSV', 'error');
    } finally {
      setExporting(false);
    }
  };

  const formatDate = (d) => {
    if (!d) return '-';
    return new Date(d).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' });
  };

  return (
    <div className="max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Historial de Ventas</h1>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 mb-6">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Desde</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Hasta</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Estado</label>
          <select value={status} onChange={e => setStatus(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none">
            {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Metodo de pago</label>
          <select value={paymentMethod} onChange={e => setPaymentMethod(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none">
            {PAYMENT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <button onClick={handleExport} disabled={exporting}
          className="ml-auto flex items-center gap-2 bg-premier-700 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-premier-700/90 disabled:opacity-50 transition-colors">
          <Download className="w-4 h-4" />
          {exporting ? 'Exportando...' : 'Exportar CSV'}
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <SummaryCard icon={ShoppingCart} label="Total ventas" value={summary.total_count} />
        <SummaryCard icon={CheckCircle} label="Monto total" value={formatCOP(summary.total_amount)} />
        <SummaryCard icon={Ban} label="Anuladas" value={summary.voided_count} accent="red" />
        <SummaryCard icon={Clock} label="Por cobrar pendiente" value={formatCOP(summary.fiado_pending)} accent="yellow" />
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-20"><Spinner /></div>
      ) : sales.length === 0 ? (
        <div className="text-center py-20 text-gray-400">No se encontraron ventas</div>
      ) : (
        <div className="bg-white rounded-2xl shadow-md overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-left">
                <tr>
                  <th className="px-4 py-3 font-medium w-8"></th>
                  <th className="px-4 py-3 font-medium">Fecha</th>
                  <th className="px-4 py-3 font-medium hidden lg:table-cell">Vendedor</th>
                  <th className="px-4 py-3 font-medium hidden md:table-cell">Productos</th>
                  <th className="px-4 py-3 font-medium text-right">Total</th>
                  <th className="px-4 py-3 font-medium hidden md:table-cell">Metodo</th>
                  <th className="px-4 py-3 font-medium">Estado</th>
                  <th className="px-4 py-3 font-medium">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sales.map(sale => {
                  const isExpanded = expandedIds.has(sale.id);
                  const saleDetail = expandedSaleData[sale.id];
                  const itemsList = saleDetail?.items || sale.items;
                  const productsSummary = itemsList
                    ? itemsList.slice(0, 2).map(i => i.product_name ?? i.name).join(', ') + (itemsList.length > 2 ? ` +${itemsList.length - 2}` : '')
                    : `${sale.total > 0 ? '...' : '-'}`;

                  return (
                    <Fragment key={sale.id}>
                      <tr
                        className="hover:bg-gray-50 cursor-pointer"
                        onClick={async () => {
                          const newSet = new Set(expandedIds);
                          if (isExpanded) {
                            newSet.delete(sale.id);
                          } else {
                            newSet.add(sale.id);
                            if (!expandedSaleData[sale.id]) {
                              try {
                                const detailRes = await api.get(`/sales/${sale.id}`);
                                setExpandedSaleData(prev => ({ ...prev, [sale.id]: detailRes.data }));
                              } catch {}
                            }
                          }
                          setExpandedIds(newSet);
                        }}
                      >
                        <td className="px-4 py-3 text-gray-400">
                          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </td>
                        <td className="px-4 py-3">{formatDate(sale.created_at)}</td>
                        <td className="px-4 py-3 hidden lg:table-cell">{sale.user_name ?? '-'}</td>
                        <td className="px-4 py-3 max-w-[200px] truncate hidden md:table-cell">{productsSummary}</td>
                        <td className="px-4 py-3 text-right font-medium">{formatCOP(sale.total)}</td>
                        <td className="px-4 py-3 capitalize hidden md:table-cell">{sale.payment_method}</td>
                        <td className="px-4 py-3"><StatusBadge status={sale.status} /></td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                            {(sale.status === 'completed' || sale.status === 'pending') && (
                              <button
                                onClick={() => { setVoidModal({ open: true, saleId: sale.id }); setVoidReason(''); }}
                                className="text-red-600 hover:text-red-800 text-xs font-medium"
                              >
                                Anular
                              </button>
                            )}
                            {sale.status === 'pending' && (
                              <button
                                onClick={() => handleMarkPaid(sale.id)}
                                className="text-premier-700 hover:text-premier-700/80 text-xs font-medium"
                              >
                                Marcar pagado
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {isExpanded && (expandedSaleData[sale.id]?.items || sale.items) && (
                        <tr>
                          <td colSpan={8} className="bg-gray-50 px-8 py-4">
                            <table className="w-full text-xs">
                              <thead className="text-gray-500">
                                <tr>
                                  <th className="text-left py-1">Producto</th>
                                  <th className="text-right py-1">Cantidad</th>
                                  <th className="text-right py-1">Precio</th>
                                  <th className="text-right py-1">Subtotal</th>
                                </tr>
                              </thead>
                              <tbody>
                                {(expandedSaleData[sale.id]?.items || sale.items).map((item, idx) => (
                                  <tr key={idx}>
                                    <td className="py-1">{item.product_name ?? item.name}</td>
                                    <td className="text-right py-1">{item.quantity}</td>
                                    <td className="text-right py-1">{formatCOP(item.unit_price)}</td>
                                    <td className="text-right py-1">{formatCOP(item.subtotal)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-6 py-4 border-t">
            <button
              onClick={() => fetchSales(Math.max(0, offset - LIMIT))}
              disabled={offset === 0}
              className="text-sm text-premier-700 font-medium disabled:text-gray-300"
            >
              Anterior
            </button>
            <span className="text-sm text-gray-500">
              Mostrando {offset + 1} - {offset + sales.length}
            </span>
            <button
              onClick={() => fetchSales(offset + LIMIT)}
              disabled={!hasMore}
              className="text-sm text-premier-700 font-medium disabled:text-gray-300"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}

      {/* Void modal */}
      <Modal isOpen={voidModal.open} onClose={() => setVoidModal({ open: false, saleId: null })} title="Anular venta">
        <div className="space-y-4">
          <p className="text-sm text-gray-600">Ingresa el motivo de la anulacion:</p>
          <textarea
            value={voidReason}
            onChange={e => setVoidReason(e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none resize-none"
            placeholder="Motivo de anulacion..."
          />
          <div className="flex justify-end gap-3">
            <button
              onClick={() => setVoidModal({ open: false, saleId: null })}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
            >
              Cancelar
            </button>
            <button
              onClick={handleVoid}
              disabled={submitting}
              className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Anulando...' : 'Confirmar anulacion'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value, accent }) {
  const colors = {
    red: 'border-red-400 bg-red-50',
    yellow: 'border-yellow-400 bg-yellow-50',
  };
  const style = accent ? colors[accent] : 'border-transparent bg-white';

  return (
    <div className={`rounded-2xl shadow-md p-5 border-l-4 ${style}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-gray-400" />
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className="text-xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

