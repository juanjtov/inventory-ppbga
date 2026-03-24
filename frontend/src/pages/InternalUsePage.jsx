import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Package, Minus, ArrowLeft, Search } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../contexts/ToastContext';
import Spinner from '../components/ui/Spinner';

export default function InternalUsePage() {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [productSearch, setProductSearch] = useState('');

  const [selectedProduct, setSelectedProduct] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState('');

  useEffect(() => {
    fetchProducts();
  }, []);

  async function fetchProducts() {
    try {
      const res = await api.get('/products?type=product');
      setProducts(res.data);
    } catch {
      addToast('Error al cargar productos', 'error');
    } finally {
      setLoading(false);
    }
  }

  const filteredProducts = products.filter((p) =>
    p.name.toLowerCase().includes(productSearch.toLowerCase())
  );

  function handleSelectProduct(product) {
    setSelectedProduct(product);
    setProductSearch('');
    setQuantity(1);
  }

  async function handleSubmit(e) {
    e.preventDefault();

    if (!selectedProduct) {
      addToast('Selecciona un producto', 'error');
      return;
    }
    if (reason.trim().length < 5) {
      addToast('La razon debe tener al menos 5 caracteres', 'error');
      return;
    }
    if (quantity < 1 || quantity > (selectedProduct?.stock ?? 0)) {
      addToast('Cantidad invalida', 'error');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/inventory/internal-use', {
        product_id: selectedProduct.id,
        quantity,
        reason: reason.trim(),
      });
      addToast('Uso interno registrado exitosamente', 'success');
      navigate('/inventario');
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error al registrar uso interno', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto">
      {/* Back button */}
      <Link
        to="/inventario"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Volver al Inventario
      </Link>

      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="bg-premier-700/10 rounded-xl p-2.5">
          <Minus className="w-6 h-6 text-premier-700" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Registrar Uso Interno</h1>
          <p className="text-sm text-gray-500">Descontar stock por uso interno</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-5">
        {/* Product searchable selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Producto
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar producto..."
              value={productSearch}
              onChange={(e) => {
                setProductSearch(e.target.value);
                if (selectedProduct) {
                  setSelectedProduct(null);
                }
              }}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
            />
          </div>
          <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg mt-1">
            {filteredProducts.length === 0 ? (
              <p className="px-4 py-3 text-sm text-gray-400">Sin resultados</p>
            ) : (
              filteredProducts.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => handleSelectProduct(p)}
                  className={`w-full text-left px-4 py-2.5 hover:bg-gray-50 flex items-center justify-between text-sm border-b border-gray-100 last:border-b-0 ${
                    selectedProduct?.id === p.id
                      ? 'bg-premier-50 border-l-2 border-l-premier-500'
                      : ''
                  }`}
                >
                  <span className="font-medium text-gray-900">{p.name}</span>
                  <span className="text-xs text-gray-500">Stock: {p.stock}</span>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Selected product info */}
        {selectedProduct && (
          <div className="flex items-center gap-2 bg-gray-50 rounded-lg p-3">
            <Package className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-600">
              {selectedProduct.name} — Stock actual: <span className="font-semibold text-gray-900">{selectedProduct.stock}</span> unidades
            </span>
          </div>
        )}

        {/* Quantity */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Cantidad
          </label>
          <input
            type="number"
            min={1}
            max={selectedProduct?.stock ?? 1}
            value={quantity}
            onChange={(e) => setQuantity(Math.max(1, Math.min(Number(e.target.value), selectedProduct?.stock ?? 1)))}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
            required
          />
          {selectedProduct && (
            <p className="mt-1 text-xs text-gray-500">Maximo: {selectedProduct.stock}</p>
          )}
        </div>

        {/* Reason */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Razon
          </label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Ej: Grips para palas del club"
            minLength={5}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
            required
          />
          <p className="mt-1 text-xs text-gray-500">Minimo 5 caracteres</p>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting || !selectedProduct || reason.trim().length < 5}
          className="w-full bg-premier-700 text-white font-semibold rounded-lg py-2.5 text-sm hover:bg-premier-800 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {submitting ? <Spinner size="h-5 w-5" /> : 'Registrar Uso Interno'}
        </button>
      </form>
    </div>
  );
}
