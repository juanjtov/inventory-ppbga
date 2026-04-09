import { useState, useEffect, useCallback, useRef } from 'react';
import { Search, Plus, Minus, X, CreditCard, Banknote, ArrowRightLeft, UserCheck, ShoppingCart, Split } from 'lucide-react';
import api from '../api/client';
import { useCart } from '../contexts/CartContext';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import { useProductRealtime } from '../hooks/useRealtime';
import Spinner from '../components/ui/Spinner';
import SplitPaymentEditor from '../components/SplitPaymentEditor';
import { isSplitValid } from '../lib/splitPayment';

const PAYMENT_METHODS = [
  { key: 'efectivo', label: 'Efectivo', icon: Banknote },
  { key: 'datafono', label: 'Datafono', icon: CreditCard },
  { key: 'transferencia', label: 'Transferencia', icon: ArrowRightLeft },
  { key: 'fiado', label: 'Por cobrar', icon: UserCheck },
];

export default function POSPage() {
  const { items, addItem, updateQuantity, removeItem, clearCart, total, itemCount } = useCart();
  const { addToast } = useToast();

  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('efectivo');
  const [clientName, setClientName] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showCart, setShowCart] = useState(false);
  const [todayAccounts, setTodayAccounts] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState(null);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [splitMode, setSplitMode] = useState(false);
  const [splits, setSplits] = useState([]);

  const debounceRef = useRef(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Debounced search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  // Fetch products
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

  // Fetch categories
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/categories');
        setCategories(res.data);
      } catch {
        // silently fail
      }
    })();
  }, []);

  // Fetch today's open fiado accounts when payment method changes
  useEffect(() => {
    if (paymentMethod === 'fiado') {
      // Splits and fiado are mutually exclusive — fiado is settled later.
      setSplitMode(false);
      setSplits([]);
      setLoadingAccounts(true);
      api.get('/sales/pending/today')
        .then(res => setTodayAccounts(res.data))
        .catch(() => setTodayAccounts([]))
        .finally(() => setLoadingAccounts(false));
    } else {
      setTodayAccounts([]);
      setSelectedAccountId(null);
      setClientName('');
    }
  }, [paymentMethod]);

  // Realtime stock updates
  const handleRealtimeUpdate = useCallback((updated) => {
    setProducts(prev => prev.map(p => (p.id === updated.id ? { ...p, ...updated } : p)));
  }, []);
  useProductRealtime(handleRealtimeUpdate);

  // Filter products
  const filtered = products.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(debouncedSearch.toLowerCase());
    const matchesCat = !selectedCategory || p.category_id === selectedCategory;
    return matchesSearch && matchesCat;
  });

  // Keyboard shortcut: Enter to confirm sale
  useEffect(() => {
    function handleKey(e) {
      if (e.key === 'Enter' && itemCount > 0 && !submitting && e.target.tagName !== 'INPUT') {
        handleConfirmSale();
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [itemCount, submitting, paymentMethod, clientName, selectedAccountId, items, total, splitMode, splits]);

  async function handleConfirmSale() {
    if (itemCount === 0) return;
    if (paymentMethod === 'fiado' && !selectedAccountId && !clientName.trim()) {
      addToast('Ingresa el nombre del cliente para venta por cobrar', 'error');
      return;
    }
    if (splitMode && !isSplitValid(splits, total)) {
      addToast('La suma del pago dividido debe ser igual al total', 'error');
      return;
    }

    setSubmitting(true);
    try {
      if (paymentMethod === 'fiado' && selectedAccountId) {
        // Add items to existing account
        await api.post(`/sales/${selectedAccountId}/add-items`, {
          items: items.map((i) => ({
            product_id: i.product_id,
            quantity: i.quantity,
          })),
        });
        addToast('Items agregados a cuenta existente', 'success');
      } else {
        // Create new sale (single method, fiado, or mixto split)
        const body = {
          items: items.map((i) => ({
            product_id: i.product_id,
            quantity: i.quantity,
            unit_price: i.unit_price,
          })),
          payment_method: splitMode ? 'mixto' : paymentMethod,
          client_name: paymentMethod === 'fiado' ? clientName.trim() : null,
          total,
        };
        if (splitMode) {
          body.payments = splits.map(s => ({
            payment_method: s.method,
            amount: Number(s.amount),
          }));
        }
        await api.post('/sales', body);
        addToast('Venta registrada correctamente', 'success');
      }
      clearCart();
      setPaymentMethod('efectivo');
      setClientName('');
      setSelectedAccountId(null);
      setTodayAccounts([]);
      setSplitMode(false);
      setSplits([]);
      setShowCart(false);
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error al registrar venta', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  function toggleSplitMode() {
    if (splitMode) {
      setSplitMode(false);
      setSplits([]);
    } else {
      setSplitMode(true);
      // Pre-populate two empty rows so the editor is immediately useful
      setSplits([
        { method: 'efectivo', amount: '' },
        { method: 'datafono', amount: '' },
      ]);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner />
      </div>
    );
  }

  const cartPanel = (
    <div className="flex flex-col overflow-hidden h-full">
      <div className="p-4 border-b border-gray-100 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">Carrito ({itemCount})</h2>
        <button onClick={() => setShowCart(false)} className="md:hidden text-gray-400 hover:text-gray-600">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Cart items */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {items.length === 0 && (
          <p className="text-gray-400 text-sm text-center py-10">El carrito esta vacio</p>
        )}
        {items.map((item) => (
          <div key={item.product_id} className="flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
              <p className="text-xs text-gray-500">{formatCOP(item.unit_price)}</p>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => updateQuantity(item.product_id, item.quantity - 1)}
                className="w-7 h-7 rounded-lg bg-gray-100 hover:bg-gray-200 flex items-center justify-center"
              >
                <Minus className="w-3.5 h-3.5 text-gray-600" />
              </button>
              <span className="w-8 text-center text-sm font-medium">{item.quantity}</span>
              <button
                onClick={() => updateQuantity(item.product_id, item.quantity + 1)}
                className="w-7 h-7 rounded-lg bg-gray-100 hover:bg-gray-200 flex items-center justify-center"
              >
                <Plus className="w-3.5 h-3.5 text-gray-600" />
              </button>
            </div>
            <p className="text-sm font-semibold text-gray-900 w-20 text-right">
              {formatCOP(item.unit_price * item.quantity)}
            </p>
            <button
              onClick={() => removeItem(item.product_id)}
              className="text-gray-400 hover:text-red-500"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-gray-100 p-4 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500">Total</span>
          <span className="text-xl font-bold text-gray-900">{formatCOP(total)}</span>
        </div>

        {!splitMode && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {PAYMENT_METHODS.map((pm) => (
              <button
                key={pm.key}
                onClick={() => setPaymentMethod(pm.key)}
                className={`flex flex-col items-center gap-1 rounded-lg p-2 text-xs font-medium transition-colors ${
                  paymentMethod === pm.key
                    ? 'bg-premier-700 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <pm.icon className="w-4 h-4" />
                {pm.label}
              </button>
            ))}
          </div>
        )}

        {/* Split payment toggle (disabled when fiado is the chosen intent) */}
        <button
          type="button"
          onClick={toggleSplitMode}
          disabled={paymentMethod === 'fiado'}
          className={`w-full flex items-center justify-center gap-2 rounded-lg py-2 text-xs font-medium transition-colors border ${
            splitMode
              ? 'bg-premier-50 border-premier-300 text-premier-700 hover:bg-premier-100'
              : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <Split className="w-3.5 h-3.5" />
          {splitMode ? 'Cancelar división' : 'Dividir pago'}
        </button>

        {splitMode && (
          <SplitPaymentEditor
            total={total}
            splits={splits}
            onChange={setSplits}
          />
        )}

        {paymentMethod === 'fiado' && (
          <div className="space-y-2">
            {loadingAccounts ? (
              <div className="flex justify-center py-2"><Spinner size="h-5 w-5" /></div>
            ) : todayAccounts.length > 0 ? (
              <>
                <select
                  value={selectedAccountId || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setSelectedAccountId(val || null);
                    if (val) setClientName('');
                  }}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent bg-white"
                >
                  <option value="">-- Nueva cuenta --</option>
                  {todayAccounts.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      {acc.client_name} — {formatCOP(acc.total)}
                    </option>
                  ))}
                </select>
                {!selectedAccountId && (
                  <input
                    type="text"
                    placeholder="Nombre del cliente"
                    value={clientName}
                    onChange={(e) => setClientName(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
                  />
                )}
              </>
            ) : (
              <input
                type="text"
                placeholder="Nombre del cliente"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              />
            )}
          </div>
        )}

        <button
          onClick={handleConfirmSale}
          disabled={itemCount === 0 || submitting || (splitMode && !isSplitValid(splits, total))}
          className="w-full bg-premier-700 text-white font-semibold rounded-lg py-3 text-sm hover:bg-premier-800 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {submitting ? <Spinner size="h-5 w-5" /> : 'Confirmar Venta'}
        </button>
      </div>
    </div>
  );

  return (
    <>
      <div className="flex h-[calc(100vh-4rem)] md:gap-4">
        {/* Left: product grid */}
        <div className="w-full md:w-[60%] flex flex-col overflow-hidden">
          {/* Search + filters */}
          <div className="flex flex-col gap-3 mb-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Buscar producto..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              />
            </div>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setSelectedCategory(null)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  !selectedCategory
                    ? 'bg-premier-700 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Todos
              </button>
              {categories.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelectedCategory(c.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    selectedCategory === c.id
                      ? 'bg-premier-700 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>

          {/* Products grid */}
          <div className="flex-1 overflow-y-auto grid grid-cols-2 md:grid-cols-3 gap-3 content-start pb-4">
            {filtered.map((product) => {
              const outOfStock = product.type === 'product' && product.stock === 0;
              return (
                <button
                  key={product.id}
                  disabled={outOfStock}
                  onClick={() => addItem(product)}
                  className={`text-left rounded-xl border p-3 md:p-4 transition-all ${
                    outOfStock
                      ? 'opacity-50 cursor-not-allowed bg-gray-50 border-gray-200'
                      : 'bg-white border-gray-200 hover:border-premier-700 hover:shadow-md cursor-pointer'
                  }`}
                >
                  <p className="font-semibold text-gray-900 text-sm truncate">{product.name}</p>
                  <p className="text-premier-700 font-bold mt-1">{formatCOP(product.sale_price)}</p>
                  <div className="flex items-center justify-between mt-2">
                    {product.type === 'product' ? (
                      <span className="text-xs text-gray-500">Stock: {product.stock}</span>
                    ) : (
                      <span className="text-xs text-blue-600 font-medium">Servicio</span>
                    )}
                    {product.category_name && (
                      <span className="text-xs bg-gray-100 text-gray-500 rounded-full px-2 py-0.5 hidden md:inline">
                        {product.category_name}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
            {filtered.length === 0 && (
              <p className="col-span-full text-center text-gray-400 py-10 text-sm">
                No se encontraron productos.
              </p>
            )}
          </div>
        </div>

        {/* Right: cart (desktop) */}
        <div className="hidden md:flex w-[40%] bg-white rounded-2xl border border-gray-200 shadow-sm flex-col overflow-hidden">
          {cartPanel}
        </div>
      </div>

      {/* Mobile cart FAB */}
      <button
        onClick={() => setShowCart(true)}
        className="md:hidden fixed bottom-20 right-6 z-30 bg-premier-700 text-white rounded-full w-14 h-14 flex items-center justify-center shadow-lg hover:bg-premier-800 transition-colors"
      >
        <ShoppingCart className="w-6 h-6" />
        {itemCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
            {itemCount}
          </span>
        )}
      </button>

      {/* Mobile cart drawer */}
      {showCart && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/50"
          onClick={() => setShowCart(false)}
        >
          <div
            className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {cartPanel}
          </div>
        </div>
      )}
    </>
  );
}
