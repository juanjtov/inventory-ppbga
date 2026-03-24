import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { PackagePlus, Search, ArrowLeft } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import Spinner from '../components/ui/Spinner';

export default function InventoryEntryPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [productSearch, setProductSearch] = useState('');

  const [selectedProduct, setSelectedProduct] = useState(null);
  const [quantity, setQuantity] = useState('');
  const [priceKept, setPriceKept] = useState(true);
  const [newPrice, setNewPrice] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/products');
        setProducts(res.data);
      } catch {
        addToast('Error cargando productos', 'error');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filteredProducts = products.filter((p) =>
    p.type === 'product' && p.name.toLowerCase().includes(productSearch.toLowerCase())
  );

  function handleSelectProduct(product) {
    setSelectedProduct(product);
    setProductSearch('');
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!selectedProduct) {
      addToast('Selecciona un producto', 'error');
      return;
    }
    if (!quantity || Number(quantity) <= 0) {
      addToast('Ingresa una cantidad valida', 'error');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/inventory/entry', {
        product_id: selectedProduct.id,
        quantity: Number(quantity),
        supplier_id: selectedProduct.supplier_id,
        price_confirmed: priceKept,
        actual_price: priceKept ? null : Number(newPrice),
      });
      addToast('Ingreso registrado correctamente', 'success');
      navigate('/inventario');
    } catch (err) {
      addToast(err.response?.data?.error || 'Error al registrar ingreso', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto">
      <Link
        to="/inventario"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Volver al Inventario
      </Link>

      <div className="flex items-center gap-3 mb-6">
        <div className="bg-premier-700/10 rounded-xl p-2.5">
          <PackagePlus className="w-6 h-6 text-premier-700" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Registrar Ingreso</h1>
          <p className="text-sm text-gray-500">Agrega stock a un producto existente</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-5">
        {/* Product selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Producto</label>
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
                  <div>
                    <span className="font-medium text-gray-900">{p.name}</span>
                    <span className="text-xs text-gray-400 ml-2">{p.supplier_name || 'Sin proveedor'}</span>
                  </div>
                  <div className="text-right text-xs text-gray-500">
                    <span>Stock: {p.stock}</span>
                    <span className="ml-3">{formatCOP(p.purchase_price)}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Selected product info */}
        {selectedProduct && (
          <div className="bg-gray-50 rounded-lg p-4 flex items-center justify-between text-sm">
            <div>
              <p className="font-medium text-gray-900">{selectedProduct.name}</p>
              <p className="text-gray-500">Proveedor: {selectedProduct.supplier_name || 'N/A'}</p>
            </div>
            <div className="text-right">
              <p className="text-gray-500">Stock actual: <span className="font-semibold text-gray-900">{selectedProduct.stock}</span></p>
              <p className="text-gray-500">Precio compra: <span className="font-semibold text-gray-900">{formatCOP(selectedProduct.purchase_price)}</span></p>
            </div>
          </div>
        )}

        {/* Quantity */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Cantidad</label>
          <input
            type="number"
            min="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="0"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
          />
        </div>

        {/* Price kept toggle */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            El precio se mantuvo?
          </label>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setPriceKept(true)}
              className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
                priceKept
                  ? 'bg-premier-700 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Si
            </button>
            <button
              type="button"
              onClick={() => setPriceKept(false)}
              className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
                !priceKept
                  ? 'bg-premier-700 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              No
            </button>
          </div>
        </div>

        {/* New price input */}
        {!priceKept && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Nuevo precio de compra
            </label>
            <input
              type="number"
              min="0"
              value={newPrice}
              onChange={(e) => setNewPrice(e.target.value)}
              placeholder="0"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
            />
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-premier-700 text-white font-semibold rounded-lg py-3 text-sm hover:bg-premier-800 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {submitting ? <Spinner size="h-5 w-5" /> : 'Registrar Ingreso'}
        </button>
      </form>
    </div>
  );
}
