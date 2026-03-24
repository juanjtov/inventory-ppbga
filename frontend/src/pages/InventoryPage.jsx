import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Search, PackagePlus, PackageMinus, ArrowRight } from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import { useProductRealtime } from '../hooks/useRealtime';
import StockBadge from '../components/shared/StockBadge';
import Spinner from '../components/ui/Spinner';

export default function InventoryPage() {
  const { user } = useAuth();
  const { addToast } = useToast();

  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [loading, setLoading] = useState(true);

  const isPrivileged = user?.role === 'owner' || user?.role === 'admin';

  useEffect(() => {
    (async () => {
      try {
        const [prodRes, catRes] = await Promise.all([
          api.get('/products'),
          api.get('/categories'),
        ]);
        setProducts(prodRes.data);
        setCategories(catRes.data);
      } catch {
        addToast('Error cargando inventario', 'error');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleRealtimeUpdate = useCallback((updated) => {
    setProducts(prev => prev.map(p => (p.id === updated.id ? { ...p, ...updated } : p)));
  }, []);
  useProductRealtime(handleRealtimeUpdate);

  const filtered = products.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase());
    const matchesCat = !selectedCategory || p.category_id === selectedCategory;
    return matchesSearch && matchesCat;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Inventario</h1>
        {isPrivileged && (
          <div className="flex gap-3">
            <Link
              to="/inventario/ingreso"
              className="inline-flex items-center gap-2 bg-premier-700 text-white text-sm font-semibold rounded-lg px-4 py-2 hover:bg-premier-800 transition-colors"
            >
              <PackagePlus className="w-4 h-4" />
              Registrar Ingreso
            </Link>
            <Link
              to="/inventario/uso-interno"
              className="inline-flex items-center gap-2 bg-white border border-gray-300 text-gray-700 text-sm font-semibold rounded-lg px-4 py-2 hover:bg-gray-50 transition-colors"
            >
              <PackageMinus className="w-4 h-4" />
              Registrar Uso Interno
            </Link>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar producto..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
          />
        </div>
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
        >
          <option value="">Todas las categorias</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 font-medium text-gray-500">Producto</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Categoria</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Proveedor</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Precio Venta</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Stock</th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
                {isPrivileged && (
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Acciones</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">{p.name}</td>
                  <td className="px-4 py-3 text-gray-600">{p.category_name || '-'}</td>
                  <td className="px-4 py-3 text-gray-600">{p.supplier_name || '-'}</td>
                  <td className="px-4 py-3 text-right text-gray-900">{formatCOP(p.sale_price)}</td>
                  <td className="px-4 py-3 text-right text-gray-900">
                    {p.type === 'service' ? '-' : p.stock}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StockBadge product={p} />
                  </td>
                  {isPrivileged && (
                    <td className="px-4 py-3 text-center">
                      <Link
                        to={`/inventario/movimientos/${p.id}`}
                        className="inline-flex items-center gap-1 text-premier-700 hover:text-premier-800 text-xs font-medium"
                      >
                        Ver movimientos
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  )}
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={isPrivileged ? 7 : 6} className="px-4 py-10 text-center text-gray-400">
                    No se encontraron productos.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
