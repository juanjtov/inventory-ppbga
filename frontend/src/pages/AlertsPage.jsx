import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Package, Plus, AlertTriangle } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../contexts/ToastContext';
import Spinner from '../components/ui/Spinner';

export default function AlertsPage() {
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/products/low-stock');
        setProducts(res.data);
      } catch {
        addToast('Error al cargar alertas de stock', 'error');
      } finally {
        setLoading(false);
      }
    })();
  }, [addToast]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner />
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Alertas de Stock</h1>
        <div className="flex flex-col items-center justify-center py-24 text-gray-400">
          <Package className="w-16 h-16 mb-4" />
          <p className="text-lg font-medium">Sin alertas</p>
          <p className="text-sm mt-1">Todos los productos tienen stock suficiente</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Alertas de Stock</h1>
        <span className="bg-red-100 text-red-700 px-3 py-1 rounded-full text-sm font-medium">
          {products.length} {products.length === 1 ? 'alerta' : 'alertas'}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {products.map(product => {
          const isOutOfStock = product.stock === 0;
          const borderColor = isOutOfStock ? 'border-red-400' : 'border-yellow-400';
          const bgColor = isOutOfStock ? 'bg-red-50' : 'bg-yellow-50';
          const iconColor = isOutOfStock ? 'text-red-500' : 'text-yellow-500';

          return (
            <div
              key={product.id}
              className={`${bgColor} border-l-4 ${borderColor} rounded-2xl shadow-md p-5 flex flex-col gap-3`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle className={`w-5 h-5 ${iconColor}`} />
                  <h3 className="font-semibold text-gray-900">{product.name}</h3>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-gray-500">Stock actual</span>
                  <p className={`font-bold text-lg ${isOutOfStock ? 'text-red-600' : 'text-yellow-600'}`}>
                    {product.stock}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">Minimo</span>
                  <p className="font-bold text-lg text-gray-700">{product.min_stock}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 text-xs">
                {product.supplier && (
                  <span className="bg-white/70 text-gray-600 px-2 py-0.5 rounded-full">
                    {product.supplier}
                  </span>
                )}
                {product.category && (
                  <span className="bg-white/70 text-gray-600 px-2 py-0.5 rounded-full">
                    {product.category}
                  </span>
                )}
              </div>

              <button
                onClick={() => navigate(`/inventario/ingreso?product=${product.id}`)}
                className="mt-auto flex items-center justify-center gap-2 bg-premier-700 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-premier-700/90 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Registrar Ingreso
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
