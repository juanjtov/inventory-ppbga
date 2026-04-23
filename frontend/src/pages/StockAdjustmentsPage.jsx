import { useState, useEffect, useCallback } from 'react';
import { ClipboardCheck, Save } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../contexts/ToastContext';
import Spinner from '../components/ui/Spinner';

export default function StockAdjustmentsPage() {
  const { addToast } = useToast();
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [counted, setCounted] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    api.get('/products')
      .then(res => {
        const list = (res.data || []).filter(p => p.is_active && p.type === 'product');
        setProducts(list);
      })
      .catch(() => addToast('Error cargando productos', 'error'));
  }, [addToast]);

  const fetchHistory = useCallback(async (productId) => {
    setLoadingHistory(true);
    try {
      const res = await api.get('/stock-adjustments', {
        params: productId ? { product_id: productId, limit: 50 } : { limit: 50 },
      });
      setHistory(res.data || []);
    } catch {
      addToast('Error cargando historial', 'error');
    } finally {
      setLoadingHistory(false);
    }
  }, [addToast]);

  useEffect(() => {
    fetchHistory(selectedProduct?.id);
  }, [fetchHistory, selectedProduct]);

  const currentStock = selectedProduct?.stock ?? 0;
  const countedNum = Number(counted);
  const difference = counted === '' || isNaN(countedNum) ? null : countedNum - currentStock;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!selectedProduct) {
      addToast('Selecciona un producto', 'error');
      return;
    }
    if (counted === '' || isNaN(countedNum) || countedNum < 0) {
      addToast('Ingresa una cantidad contada válida', 'error');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/stock-adjustments', {
        product_id: selectedProduct.id,
        counted_quantity: countedNum,
        reason: reason.trim() || null,
      });
      addToast('Ajuste guardado', 'success');
      // Refresh product (stock updated), history, reset form
      const res = await api.get(`/products/${selectedProduct.id}`);
      setSelectedProduct(res.data);
      setProducts(prev => prev.map(p => p.id === res.data.id ? res.data : p));
      setCounted('');
      setReason('');
      fetchHistory(selectedProduct.id);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error al guardar ajuste', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center gap-2 mb-6">
        <ClipboardCheck className="w-6 h-6 text-premier-700" />
        <h1 className="text-xl font-bold text-gray-900">Ajustes de Stock</h1>
      </div>

      <p className="text-sm text-gray-500 mb-6">
        Ingresa el conteo físico de un producto para sincronizar el stock del sistema con lo que hay en bodega.
      </p>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Producto</label>
          <select
            value={selectedProduct?.id || ''}
            onChange={(e) => setSelectedProduct(products.find(p => p.id === e.target.value) || null)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700"
          >
            <option value="">— Selecciona —</option>
            {products.map(p => (
              <option key={p.id} value={p.id}>
                {p.name} (stock actual: {p.stock ?? 0})
              </option>
            ))}
          </select>
        </div>

        {selectedProduct && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Stock en sistema</label>
                <input
                  type="number"
                  value={currentStock}
                  disabled
                  className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Cantidad contada</label>
                <input
                  type="number"
                  min="0"
                  value={counted}
                  onChange={(e) => setCounted(e.target.value)}
                  placeholder="0"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700"
                  required
                />
              </div>
            </div>

            {difference !== null && (
              <div className={`rounded-lg border p-3 ${
                difference === 0 ? 'bg-green-50 border-green-200' :
                difference < 0 ? 'bg-red-50 border-red-200' :
                'bg-yellow-50 border-yellow-200'
              }`}>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Diferencia</span>
                  <span className={`font-bold ${
                    difference === 0 ? 'text-green-700' :
                    difference < 0 ? 'text-red-700' :
                    'text-yellow-700'
                  }`}>
                    {difference > 0 ? `+${difference}` : difference}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {difference === 0 ? 'El conteo coincide con el sistema.' :
                   difference < 0 ? 'Faltan unidades respecto al sistema (merma / robo / error).' :
                   'Hay más unidades de las registradas.'}
                </p>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Motivo (opcional)</label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                placeholder="Conteo semanal, inventario anual, etc."
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={submitting || counted === ''}
              className="w-full bg-premier-700 text-white font-semibold rounded-lg py-2.5 text-sm hover:bg-premier-800 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {submitting ? <Spinner size="h-5 w-5" /> : (
                <>
                  <Save className="w-4 h-4" />
                  Guardar ajuste
                </>
              )}
            </button>
          </>
        )}
      </form>

      {/* History */}
      <div className="mt-8 bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-5 py-3 border-b">
          <h3 className="font-semibold text-gray-900 text-sm">
            Historial de ajustes{selectedProduct ? ` — ${selectedProduct.name}` : ' (todos los productos)'}
          </h3>
        </div>
        {loadingHistory ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : history.length === 0 ? (
          <div className="text-center py-10 text-gray-400 text-sm">Sin ajustes registrados</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-left">
                <tr>
                  <th className="px-5 py-2 font-medium">Fecha</th>
                  <th className="px-5 py-2 font-medium">Producto</th>
                  <th className="px-5 py-2 font-medium">Usuario</th>
                  <th className="px-5 py-2 font-medium text-right">Sistema</th>
                  <th className="px-5 py-2 font-medium text-right">Contado</th>
                  <th className="px-5 py-2 font-medium text-right">Diferencia</th>
                  <th className="px-5 py-2 font-medium">Motivo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {history.map(a => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-5 py-2 whitespace-nowrap">
                      {new Date(a.adjusted_at).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td className="px-5 py-2">{a.product_name ?? '-'}</td>
                    <td className="px-5 py-2">{a.user_name ?? '-'}</td>
                    <td className="px-5 py-2 text-right">{a.system_quantity}</td>
                    <td className="px-5 py-2 text-right">{a.counted_quantity}</td>
                    <td className={`px-5 py-2 text-right font-medium ${
                      a.difference === 0 ? 'text-gray-700' :
                      a.difference < 0 ? 'text-red-600' : 'text-yellow-600'
                    }`}>
                      {a.difference > 0 ? `+${a.difference}` : a.difference}
                    </td>
                    <td className="px-5 py-2 text-gray-600">{a.reason || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
