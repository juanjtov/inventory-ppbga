import { useState, useEffect } from 'react';
import { CreditCard, ChevronDown, ChevronUp, CheckCircle, AlertTriangle } from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import Spinner from '../components/ui/Spinner';
import Modal from '../components/ui/Modal';

export default function OpenAccountsPage() {
  const { user } = useAuth();
  const { addToast } = useToast();

  const [sales, setSales] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [expandedData, setExpandedData] = useState({});
  const [confirmSale, setConfirmSale] = useState(null);
  const [paying, setPaying] = useState(false);

  const isOwnerOrAdmin = user?.role === 'owner' || user?.role === 'admin';

  useEffect(() => {
    fetchPending();
  }, []);

  async function fetchPending() {
    try {
      const res = await api.get('/sales/pending');
      setSales(res.data);
    } catch {
      addToast('Error al cargar cuentas pendientes', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function handleMarkPaid(saleId) {
    setPaying(true);
    try {
      await api.post(`/sales/${saleId}/pay`);
      addToast('Cuenta marcada como pagada', 'success');
      setSales(prev => prev.filter(s => s.id !== saleId));
      setConfirmSale(null);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error al marcar como pagado', 'error');
    } finally {
      setPaying(false);
    }
  }

  function getDaysSince(dateStr) {
    const created = new Date(dateStr);
    const now = new Date();
    return Math.floor((now - created) / (1000 * 60 * 60 * 24));
  }

  function getRowClasses(dateStr) {
    const days = getDaysSince(dateStr);
    if (days > 7) return 'bg-red-50 border-red-200';
    if (days >= 3) return 'bg-yellow-50 border-yellow-200';
    return 'bg-white border-gray-100';
  }

  const totalPendiente = sales.reduce((sum, s) => sum + (s.total || 0), 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <CreditCard className="w-6 h-6 text-premier-700" />
          <h1 className="text-xl font-bold text-gray-900">Cuentas Abiertas (Por cobrar)</h1>
        </div>
      </div>

      {/* Total pendiente */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-6 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-600">Total pendiente</span>
        <span className="text-lg font-bold text-red-600">{formatCOP(totalPendiente)}</span>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mb-4 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-100 border border-red-300" /> Mas de 7 dias
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-yellow-100 border border-yellow-300" /> 3–7 dias
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-white border border-gray-300" /> Menos de 3 dias
        </span>
      </div>

      {sales.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center">
          <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-3" />
          <p className="text-gray-500">No hay cuentas pendientes</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sales.map(sale => {
            const isExpanded = expandedId === sale.id;
            const days = getDaysSince(sale.created_at);
            const saleItems = expandedData[sale.id]?.items || sale.items || [];
            const itemsSummary = saleItems
              .slice(0, 3)
              .map(i => i.product_name || i.name)
              .join(', ');
            const extra = saleItems.length > 3 ? ` +${saleItems.length - 3} mas` : '';

            return (
              <div
                key={sale.id}
                className={`rounded-xl border shadow-sm overflow-hidden ${getRowClasses(sale.created_at)}`}
              >
                {/* Main row */}
                <div className="flex items-center justify-between p-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-gray-900 truncate">
                        {sale.client_name || 'Sin nombre'}
                      </span>
                      {days > 7 && (
                        <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
                      )}
                    </div>
                    <p className="text-xs text-gray-500">
                      {new Date(sale.created_at).toLocaleDateString('es-CO')} — {days} dia{days !== 1 ? 's' : ''}
                    </p>
                    <p className="text-xs text-gray-400 truncate mt-0.5">
                      {itemsSummary}{extra}
                    </p>
                  </div>

                  <div className="flex items-center gap-3 ml-4">
                    <span className="font-bold text-gray-900 whitespace-nowrap">
                      {formatCOP(sale.total)}
                    </span>

                    <button
                      onClick={async () => {
                        if (isExpanded) {
                          setExpandedId(null);
                        } else {
                          setExpandedId(sale.id);
                          if (!expandedData[sale.id]) {
                            try {
                              const res = await api.get(`/sales/${sale.id}`);
                              setExpandedData(prev => ({ ...prev, [sale.id]: res.data }));
                            } catch {}
                          }
                        }
                      }}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {/* Expanded items */}
                {isExpanded && (
                  <div className="border-t px-4 py-3 bg-white/60">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-gray-500">
                          <th className="pb-1">Producto</th>
                          <th className="pb-1 text-center">Cant.</th>
                          <th className="pb-1 text-right">Subtotal</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(expandedData[sale.id]?.items || sale.items || []).map((item, idx) => (
                          <tr key={idx} className="border-t border-gray-100">
                            <td className="py-1 text-gray-700">{item.product_name || item.name}</td>
                            <td className="py-1 text-center text-gray-600">{item.quantity}</td>
                            <td className="py-1 text-right text-gray-700">{formatCOP(item.subtotal || item.quantity * item.unit_price)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {isOwnerOrAdmin && (
                      <div className="mt-3 flex justify-end">
                        <button
                          onClick={() => setConfirmSale(sale)}
                          className="bg-premier-700 text-white text-sm font-medium rounded-lg px-4 py-2 hover:bg-premier-800 transition-colors flex items-center gap-2"
                        >
                          <CheckCircle className="w-4 h-4" />
                          Marcar como Pagado
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Confirm Dialog */}
      <Modal
        isOpen={!!confirmSale}
        onClose={() => !paying && setConfirmSale(null)}
        title="Confirmar Pago"
      >
        <p className="text-sm text-gray-600 mb-4">
          Confirmar que <strong>{confirmSale?.client_name || 'el cliente'}</strong> ha pagado{' '}
          <strong>{confirmSale ? formatCOP(confirmSale.total) : ''}</strong>?
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={() => setConfirmSale(null)}
            disabled={paying}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            onClick={() => handleMarkPaid(confirmSale.id)}
            disabled={paying}
            className="px-4 py-2 text-sm rounded-lg bg-premier-700 text-white font-medium hover:bg-premier-800 disabled:opacity-50 flex items-center gap-2"
          >
            {paying ? <Spinner size="h-4 w-4" /> : 'Confirmar'}
          </button>
        </div>
      </Modal>
    </div>
  );
}
