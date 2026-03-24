import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Truck, Box, TrendingDown, TrendingUp } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import Spinner from '../components/ui/Spinner';

const TYPE_STYLES = {
  sale: { label: 'Venta', bg: 'bg-green-100 text-green-700' },
  entry: { label: 'Ingreso', bg: 'bg-blue-100 text-blue-700' },
  internal_use: { label: 'Uso interno', bg: 'bg-orange-100 text-orange-700' },
  void: { label: 'Anulacion', bg: 'bg-red-100 text-red-700' },
};

function formatMovementDetails(m) {
  const d = m.details || {};
  switch (m.type) {
    case 'sale':
      return `Venta — ${m.quantity} uds a ${formatCOP(d.unit_price || 0)} c/u — ${d.payment_method || ''} — por ${d.user_name || ''}`;
    case 'entry':
      return `Ingreso — ${m.quantity} uds — Proveedor: ${d.supplier_name || ''} — Precio confirmado: ${d.price_confirmed ? 'Si' : 'No'}`;
    case 'internal_use':
      return `Uso interno — ${m.quantity} uds — Motivo: ${d.reason || ''} — por ${d.user_name || ''}`;
    case 'void':
      return `Anulacion — +${m.quantity} uds devueltas — por ${d.user_name || ''}`;
    default:
      return `${m.type} — ${m.quantity} uds`;
  }
}

function computeDelta(m) {
  if (m.type === 'entry' || m.type === 'void') return m.quantity;
  if (m.type === 'sale' || m.type === 'internal_use') return -m.quantity;
  return 0;
}

export default function ProductMovementsPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [product, setProduct] = useState(null);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { product_id: productId };
      const [productRes, movementsRes] = await Promise.all([
        api.get(`/products/${productId}`),
        api.get('/inventory/movements', { params }),
      ]);
      setProduct(productRes.data);
      setMovements(movementsRes.data);
    } catch {
      addToast('Error al cargar movimientos', 'error');
    } finally {
      setLoading(false);
    }
  }, [productId, dateFrom, dateTo, addToast]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const formatDate = (d) => {
    if (!d) return '-';
    return new Date(d).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Volver
      </button>

      {/* Product header card */}
      {product && (
        <div className="bg-white rounded-2xl shadow-md p-6 mb-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-gray-900">{product.name}</h1>
              <div className="flex flex-wrap gap-2 mt-3">
                {product.category_name && (
                  <span className="bg-gray-100 text-gray-600 px-2.5 py-0.5 rounded-full text-xs font-medium">
                    {product.category_name}
                  </span>
                )}
                {product.supplier_name && (
                  <span className="bg-blue-50 text-blue-600 px-2.5 py-0.5 rounded-full text-xs font-medium flex items-center gap-1">
                    <Truck className="w-3 h-3" />
                    {product.supplier_name}
                  </span>
                )}
                <span className="bg-purple-50 text-purple-600 px-2.5 py-0.5 rounded-full text-xs font-medium flex items-center gap-1">
                  <Box className="w-3 h-3" />
                  {product.type === 'product' ? 'Producto' : 'Servicio'}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <div className="text-center">
                <span className="text-gray-500 block">Stock</span>
                <span className={`text-2xl font-bold ${
                  product.stock === 0 ? 'text-red-600' : product.is_low_stock ? 'text-yellow-600' : 'text-green-600'
                }`}>
                  {product.stock ?? '-'}
                </span>
              </div>
              <div className="text-center">
                <span className="text-gray-500 block">P. Venta</span>
                <span className="font-semibold text-gray-900">{formatCOP(product.sale_price)}</span>
              </div>
              <div className="text-center">
                <span className="text-gray-500 block">P. Compra</span>
                <span className="font-semibold text-gray-900">{formatCOP(product.purchase_price)}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Date filters */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <h2 className="text-lg font-semibold text-gray-900">Movimientos</h2>
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-xs text-gray-500">Desde</label>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">Hasta</label>
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none"
          />
        </div>
      </div>

      {/* Timeline */}
      {movements.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          No hay movimientos registrados
        </div>
      ) : (
        <div className="relative">
          <div className="absolute left-6 top-0 bottom-0 w-px bg-gray-200" />

          <div className="space-y-4">
            {movements.map((m, idx) => {
              const typeStyle = TYPE_STYLES[m.type] ?? { label: m.type, bg: 'bg-gray-100 text-gray-700' };
              const delta = computeDelta(m);
              const isPositive = delta > 0;

              return (
                <div key={m.id ?? idx} className="relative flex gap-4 pl-12">
                  <div className="absolute left-[18px] top-4 w-3 h-3 rounded-full border-2 border-white bg-gray-300 shadow" />

                  <div className="bg-white rounded-2xl shadow-md p-4 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`${typeStyle.bg} px-2.5 py-0.5 rounded-full text-xs font-medium`}>
                          {typeStyle.label}
                        </span>
                        <span className="text-xs text-gray-400">{formatDate(m.date)}</span>
                      </div>
                      <span className={`text-sm font-bold flex items-center gap-1 ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
                        {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                        {isPositive ? '+' : ''}{delta}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">{formatMovementDetails(m)}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
