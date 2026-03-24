import { useState, useEffect, useCallback } from 'react';
import { Package, Plus, Upload, Search, ToggleLeft, ToggleRight, Pencil, Trash2 } from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import Modal from '../components/ui/Modal';
import Spinner from '../components/ui/Spinner';

const EMPTY_FORM = {
  name: '',
  category_id: '',
  supplier_id: '',
  type: 'product',
  sale_price: '',
  purchase_price: '',
  stock: 0,
  min_stock_alert: '',
  is_active: true,
};

export default function CatalogPage() {
  const { user } = useAuth();
  const { addToast } = useToast();

  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [showModal, setShowModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // New category/supplier inline creation
  const [newCategory, setNewCategory] = useState('');
  const [showNewCategory, setShowNewCategory] = useState(false);
  const [newSupplier, setNewSupplier] = useState('');
  const [showNewSupplier, setShowNewSupplier] = useState(false);

  // Delete modal
  const [deleteModal, setDeleteModal] = useState({ open: false, productId: null, productName: '' });
  const [deleting, setDeleting] = useState(false);

  // CSV import
  const [showCsvModal, setShowCsvModal] = useState(false);
  const [csvFile, setCsvFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const isOwner = user?.role === 'owner';

  const fetchAll = useCallback(async () => {
    try {
      const [prodRes, catRes, supRes] = await Promise.all([
        api.get('/products'),
        api.get('/categories'),
        api.get('/suppliers'),
      ]);
      setProducts(prodRes.data);
      setCategories(catRes.data);
      setSuppliers(supRes.data);
    } catch {
      addToast('Error al cargar datos', 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  function openCreate() {
    setEditingProduct(null);
    setForm(EMPTY_FORM);
    setShowNewCategory(false);
    setShowNewSupplier(false);
    setNewCategory('');
    setNewSupplier('');
    setShowModal(true);
  }

  function openEdit(product) {
    if (!isOwner) return;
    setEditingProduct(product);
    setForm({
      name: product.name || '',
      category_id: product.category_id || '',
      supplier_id: product.supplier_id || '',
      type: product.type || 'product',
      sale_price: product.sale_price ?? '',
      purchase_price: product.purchase_price ?? '',
      stock: product.stock ?? 0,
      min_stock_alert: product.min_stock_alert ?? '',
      is_active: product.is_active !== false,
    });
    setShowNewCategory(false);
    setShowNewSupplier(false);
    setNewCategory('');
    setNewSupplier('');
    setShowModal(true);
  }

  function updateForm(field, value) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);

    try {
      let categoryId = form.category_id;
      let supplierId = form.supplier_id;

      // Create new category if needed
      if (showNewCategory && newCategory.trim()) {
        const res = await api.post('/categories', { name: newCategory.trim() });
        categoryId = res.data.id;
        setCategories(prev => [...prev, res.data]);
      }

      // Create new supplier if needed
      if (showNewSupplier && newSupplier.trim()) {
        const res = await api.post('/suppliers', { name: newSupplier.trim() });
        supplierId = res.data.id;
        setSuppliers(prev => [...prev, res.data]);
      }

      const payload = {
        name: form.name,
        category_id: categoryId || null,
        supplier_id: supplierId || null,
        type: form.type,
        sale_price: Number(form.sale_price) || 0,
        purchase_price: Number(form.purchase_price) || 0,
        stock: form.type === 'service' ? 0 : Number(form.stock) || 0,
        min_stock_alert: Number(form.min_stock_alert) || 0,
        is_active: form.is_active,
      };

      if (editingProduct) {
        await api.put(`/products/${editingProduct.id}`, payload);
        addToast('Producto actualizado', 'success');
      } else {
        await api.post('/products', payload);
        addToast('Producto creado', 'success');
      }

      setShowModal(false);
      fetchAll();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error al guardar', 'error');
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(product) {
    if (!isOwner) return;
    try {
      await api.put(`/products/${product.id}`, { is_active: !product.is_active });
      setProducts(prev =>
        prev.map(p => (p.id === product.id ? { ...p, is_active: !p.is_active } : p))
      );
      addToast(
        product.is_active ? 'Producto desactivado' : 'Producto activado',
        'success'
      );
    } catch {
      addToast('Error al cambiar estado', 'error');
    }
  }

  function openDeleteModal(product) {
    setDeleteModal({ open: true, productId: product.id, productName: product.name });
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.delete(`/products/${deleteModal.productId}`);
      addToast('Producto eliminado', 'success');
      setDeleteModal({ open: false, productId: null, productName: '' });
      fetchAll();
    } catch (err) {
      if (err.response?.status === 400) {
        addToast(err.response.data?.detail || 'No se puede eliminar este producto', 'error');
      } else {
        addToast('Error al eliminar producto', 'error');
      }
    } finally {
      setDeleting(false);
    }
  }

  async function handleCsvImport() {
    if (!csvFile) return;
    setImporting(true);
    setImportResult(null);

    const formData = new FormData();
    formData.append('file', csvFile);

    try {
      const res = await api.post('/products/import-csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setImportResult(res.data);
      addToast('Importacion completada', 'success');
      fetchAll();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error al importar CSV', 'error');
    } finally {
      setImporting(false);
    }
  }

  const filtered = products.filter(p =>
    p.name?.toLowerCase().includes(search.toLowerCase())
  );

  const getCategoryName = (id) => categories.find(c => c.id === id)?.name || '—';
  const getSupplierName = (id) => suppliers.find(s => s.id === id)?.name || '—';

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
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Package className="w-6 h-6 text-premier-700" />
          <h1 className="text-xl font-bold text-gray-900">Catalogo de Productos</h1>
        </div>
        <div className="flex items-center gap-2">
          {isOwner && (
            <button
              onClick={() => { setCsvFile(null); setImportResult(null); setShowCsvModal(true); }}
              className="flex items-center gap-1.5 text-sm border border-gray-300 rounded-lg px-3 py-2 hover:bg-gray-50 transition-colors"
            >
              <Upload className="w-4 h-4" />
              Importar CSV
            </button>
          )}
          <button
            onClick={openCreate}
            className="flex items-center gap-1.5 text-sm bg-premier-700 text-white rounded-lg px-4 py-2 font-medium hover:bg-premier-800 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Agregar Producto
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="mb-4 relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar producto..."
          className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs text-gray-500 uppercase tracking-wider">
              <th className="px-4 py-3">Nombre</th>
              <th className="px-4 py-3">Categoria</th>
              <th className="px-4 py-3">Proveedor</th>
              <th className="px-4 py-3">Tipo</th>
              <th className="px-4 py-3 text-right">P. Venta</th>
              <th className="px-4 py-3 text-right">P. Compra</th>
              <th className="px-4 py-3 text-center">Stock</th>
              <th className="px-4 py-3 text-center">Umbral</th>
              <th className="px-4 py-3 text-center">Activo</th>
              {isOwner && <th className="px-4 py-3 text-center">Acciones</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map(p => (
              <tr
                key={p.id}
                className={`border-b border-gray-50 hover:bg-gray-50 ${isOwner ? 'cursor-pointer' : ''} ${!p.is_active ? 'opacity-50' : ''}`}
                onClick={() => isOwner && openEdit(p)}
              >
                <td className="px-4 py-3 font-medium text-gray-900">{p.name}</td>
                <td className="px-4 py-3 text-gray-600">{getCategoryName(p.category_id)}</td>
                <td className="px-4 py-3 text-gray-600">{getSupplierName(p.supplier_id)}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    p.type === 'service'
                      ? 'bg-blue-50 text-blue-700'
                      : 'bg-green-50 text-green-700'
                  }`}>
                    {p.type === 'service' ? 'Servicio' : 'Producto'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-gray-900">{formatCOP(p.sale_price)}</td>
                <td className="px-4 py-3 text-right text-gray-600">{formatCOP(p.purchase_price)}</td>
                <td className="px-4 py-3 text-center">
                  {p.type === 'service' ? '—' : (
                    <span className={p.stock <= (p.min_stock_alert || 0) ? 'text-red-600 font-bold' : ''}>
                      {p.stock}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-center text-gray-500">{p.min_stock_alert ?? '—'}</td>
                <td className="px-4 py-3 text-center">
                  {isOwner ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleActive(p); }}
                      className="inline-flex"
                    >
                      {p.is_active
                        ? <ToggleRight className="w-6 h-6 text-premier-700" />
                        : <ToggleLeft className="w-6 h-6 text-gray-400" />
                      }
                    </button>
                  ) : (
                    <span className={`text-xs ${p.is_active ? 'text-green-600' : 'text-gray-400'}`}>
                      {p.is_active ? 'Si' : 'No'}
                    </span>
                  )}
                </td>
                {isOwner && (
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); openEdit(p); }}
                        className="text-gray-400 hover:text-premier-700"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); openDeleteModal(p); }}
                        className="text-red-400 hover:text-red-600"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={isOwner ? 10 : 9} className="px-4 py-8 text-center text-gray-400">
                  No se encontraron productos
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => !saving && setShowModal(false)}
        title={editingProduct ? 'Editar Producto' : 'Agregar Producto'}
        maxWidth="max-w-xl"
      >
        <form onSubmit={handleSave} className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateForm('name', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              required
            />
          </div>

          {/* Category */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Categoria</label>
            {showNewCategory ? (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  placeholder="Nombre nueva categoria"
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => { setShowNewCategory(false); setNewCategory(''); }}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Cancelar
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <select
                  value={form.category_id}
                  onChange={(e) => updateForm('category_id', e.target.value)}
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
                >
                  <option value="">Sin categoria</option>
                  {categories.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setShowNewCategory(true)}
                  className="text-sm text-premier-700 hover:text-premier-800 whitespace-nowrap font-medium"
                >
                  + Crear nueva
                </button>
              </div>
            )}
          </div>

          {/* Supplier */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Proveedor</label>
            {showNewSupplier ? (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newSupplier}
                  onChange={(e) => setNewSupplier(e.target.value)}
                  placeholder="Nombre nuevo proveedor"
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => { setShowNewSupplier(false); setNewSupplier(''); }}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Cancelar
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <select
                  value={form.supplier_id}
                  onChange={(e) => updateForm('supplier_id', e.target.value)}
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
                >
                  <option value="">Sin proveedor</option>
                  {suppliers.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => setShowNewSupplier(true)}
                  className="text-sm text-premier-700 hover:text-premier-800 whitespace-nowrap font-medium"
                >
                  + Crear nueva
                </button>
              </div>
            )}
          </div>

          {/* Type toggle */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tipo</label>
            <div className="flex rounded-lg border border-gray-300 overflow-hidden">
              <button
                type="button"
                onClick={() => updateForm('type', 'product')}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  form.type === 'product'
                    ? 'bg-premier-700 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                Producto
              </button>
              <button
                type="button"
                onClick={() => updateForm('type', 'service')}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  form.type === 'service'
                    ? 'bg-premier-700 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                Servicio
              </button>
            </div>
          </div>

          {/* Prices */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Precio Venta</label>
              <input
                type="number"
                min={0}
                value={form.sale_price}
                onChange={(e) => updateForm('sale_price', e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Precio Compra</label>
              <input
                type="number"
                min={0}
                value={form.purchase_price}
                onChange={(e) => updateForm('purchase_price', e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              />
            </div>
          </div>

          {/* Stock & Threshold */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Stock</label>
              <input
                type="number"
                min={0}
                value={form.stock}
                onChange={(e) => updateForm('stock', e.target.value)}
                disabled={form.type === 'service'}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent disabled:bg-gray-100 disabled:text-gray-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Umbral minimo</label>
              <input
                type="number"
                min={0}
                value={form.min_stock_alert}
                onChange={(e) => updateForm('min_stock_alert', e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              />
            </div>
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setShowModal(false)}
              disabled={saving}
              className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm rounded-lg bg-premier-700 text-white font-medium hover:bg-premier-800 disabled:opacity-50 flex items-center gap-2"
            >
              {saving ? <Spinner size="h-4 w-4" /> : (editingProduct ? 'Guardar Cambios' : 'Crear Producto')}
            </button>
          </div>
        </form>
      </Modal>

      {/* CSV Import Modal */}
      <Modal
        isOpen={showCsvModal}
        onClose={() => !importing && setShowCsvModal(false)}
        title="Importar Productos desde CSV"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Archivo CSV</label>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
              className="w-full text-sm text-gray-600 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-premier-50 file:text-premier-700 hover:file:bg-premier-100"
            />
          </div>

          {importResult && (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm space-y-1">
              <p className="text-green-700">Creados: {importResult.created ?? 0}</p>
              <p className="text-yellow-700">Actualizados: {importResult.updated ?? 0}</p>
              {importResult.errors?.length > 0 && (
                <div className="text-red-600">
                  <p>Errores: {importResult.errors.length}</p>
                  <ul className="list-disc ml-4 mt-1">
                    {importResult.errors.slice(0, 5).map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button
              onClick={() => setShowCsvModal(false)}
              disabled={importing}
              className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Cerrar
            </button>
            <button
              onClick={handleCsvImport}
              disabled={importing || !csvFile}
              className="px-4 py-2 text-sm rounded-lg bg-premier-700 text-white font-medium hover:bg-premier-800 disabled:opacity-50 flex items-center gap-2"
            >
              {importing ? <Spinner size="h-4 w-4" /> : (
                <>
                  <Upload className="w-4 h-4" />
                  Importar
                </>
              )}
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModal.open}
        onClose={() => !deleting && setDeleteModal({ open: false, productId: null, productName: '' })}
        title="Eliminar Producto"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Estas seguro de eliminar este producto? <span className="font-medium text-gray-900">{deleteModal.productName}</span>
          </p>
          <div className="flex justify-end gap-3">
            <button
              onClick={() => setDeleteModal({ open: false, productId: null, productName: '' })}
              disabled={deleting}
              className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-50 flex items-center gap-2"
            >
              {deleting ? <Spinner size="h-4 w-4" /> : 'Eliminar'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
