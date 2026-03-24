import { useState, useEffect } from 'react';
import { Users, Plus, Pencil, ToggleLeft, ToggleRight, Shield, Trash2 } from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import Modal from '../components/ui/Modal';
import Spinner from '../components/ui/Spinner';

const ROLE_LABELS = { owner: 'Propietario', admin: 'Administrador', worker: 'Trabajador' };
const ROLE_COLORS = {
  owner: 'bg-purple-50 text-purple-700',
  admin: 'bg-blue-50 text-blue-700',
  worker: 'bg-gray-100 text-gray-700',
};

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const { addToast } = useToast();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteModal, setDeleteModal] = useState({ open: false, user: null });

  // Create form
  const [createForm, setCreateForm] = useState({ full_name: '', email: '', password: '', role: 'worker' });
  // Edit form
  const [editForm, setEditForm] = useState({ full_name: '', role: '' });

  useEffect(() => {
    fetchUsers();
  }, []);

  async function fetchUsers() {
    try {
      const res = await api.get('/users');
      setUsers(res.data);
    } catch {
      addToast('Error al cargar usuarios', 'error');
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setCreateForm({ full_name: '', email: '', password: '', role: 'worker' });
    setShowCreateModal(true);
  }

  function openEdit(u) {
    if (u.id === currentUser?.id) return;
    setEditingUser(u);
    setEditForm({ name: u.full_name || '', role: u.role || 'worker' });
    setShowEditModal(true);
  }

  async function handleCreate(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post('/users', createForm);
      addToast('Usuario creado exitosamente', 'success');
      setShowCreateModal(false);
      fetchUsers();
    } catch (err) {
      addToast((() => { const d = err.response?.data?.detail; return typeof d === 'string' ? d : Array.isArray(d) ? d.map(e => e.msg).join(', ') : 'Error al crear usuario'; })(), 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handleEdit(e) {
    e.preventDefault();
    if (!editingUser) return;
    setSaving(true);
    try {
      await api.put(`/users/${editingUser.id}`, editForm);
      addToast('Usuario actualizado', 'success');
      setShowEditModal(false);
      fetchUsers();
    } catch (err) {
      addToast((() => { const d = err.response?.data?.detail; return typeof d === 'string' ? d : Array.isArray(d) ? d.map(e => e.msg).join(', ') : 'Error al actualizar usuario'; })(), 'error');
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(u) {
    if (u.id === currentUser?.id) return;
    try {
      await api.put(`/users/${u.id}`, { is_active: !u.is_active });
      setUsers(prev =>
        prev.map(item => (item.id === u.id ? { ...item, is_active: !item.is_active } : item))
      );
      addToast(u.is_active ? 'Usuario desactivado' : 'Usuario activado', 'success');
    } catch {
      addToast('Error al cambiar estado', 'error');
    }
  }

  async function handleDelete() {
    const u = deleteModal.user;
    if (!u) return;
    setSaving(true);
    try {
      await api.delete(`/users/${u.id}`);
      addToast('Usuario eliminado', 'success');
      setDeleteModal({ open: false, user: null });
      fetchUsers();
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 400 && typeof detail === 'string') {
        addToast(detail, 'error');
      } else {
        addToast('Error al eliminar usuario', 'error');
      }
    } finally {
      setSaving(false);
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
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Users className="w-6 h-6 text-premier-700" />
          <h1 className="text-xl font-bold text-gray-900">Gestion de Usuarios</h1>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-1.5 text-sm bg-premier-700 text-white rounded-lg px-4 py-2 font-medium hover:bg-premier-800 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Agregar Usuario
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs text-gray-500 uppercase tracking-wider">
              <th className="px-4 py-3">Nombre</th>
              <th className="px-4 py-3 hidden md:table-cell">Email</th>
              <th className="px-4 py-3">Rol</th>
              <th className="px-4 py-3 text-center hidden md:table-cell">Estado</th>
              <th className="px-4 py-3 hidden lg:table-cell">Fecha</th>
              <th className="px-4 py-3 text-center">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => {
              const isSelf = u.id === currentUser?.id;
              return (
                <tr
                  key={u.id}
                  className={`border-b border-gray-50 hover:bg-gray-50 ${!u.is_active ? 'opacity-50' : ''}`}
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
                    <div className="flex items-center gap-2">
                      {u.full_name || '—'}
                      {isSelf && (
                        <span className="text-xs bg-premier-50 text-premier-700 px-1.5 py-0.5 rounded">Tu</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600 hidden md:table-cell">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[u.role] || ROLE_COLORS.worker}`}>
                      {ROLE_LABELS[u.role] || u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center hidden md:table-cell">
                    {isSelf ? (
                      <span className="text-xs text-green-600">Activo</span>
                    ) : (
                      <button onClick={() => toggleActive(u)} className="inline-flex">
                        {u.is_active
                          ? <ToggleRight className="w-6 h-6 text-premier-700" />
                          : <ToggleLeft className="w-6 h-6 text-gray-400" />
                        }
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs hidden lg:table-cell">
                    {u.created_at
                      ? new Date(u.created_at).toLocaleDateString('es-CO')
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      {!isSelf && (
                        <button
                          onClick={() => openEdit(u)}
                          className="text-gray-400 hover:text-premier-700"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                      )}
                      {!isSelf && u.role !== 'owner' && (
                        <button
                          onClick={() => setDeleteModal({ open: true, user: u })}
                          className="text-gray-400 hover:text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {users.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  No hay usuarios registrados
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => !saving && setShowCreateModal(false)}
        title="Agregar Usuario"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
            <input
              type="text"
              value={createForm.full_name}
              onChange={(e) => setCreateForm(prev => ({ ...prev, full_name: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={createForm.email}
              onChange={(e) => setCreateForm(prev => ({ ...prev, email: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Contrasena temporal</label>
            <input
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm(prev => ({ ...prev, password: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              required
              minLength={6}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
            <select
              value={createForm.role}
              onChange={(e) => setCreateForm(prev => ({ ...prev, role: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
            >
              <option value="admin">Administrador</option>
              <option value="worker">Trabajador</option>
            </select>
            <p className="mt-1 text-xs text-gray-500 flex items-center gap-1">
              <Shield className="w-3 h-3" /> No es posible crear usuarios propietario
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setShowCreateModal(false)}
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
              {saving ? <Spinner size="h-4 w-4" /> : 'Crear Usuario'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModal.open}
        onClose={() => !saving && setDeleteModal({ open: false, user: null })}
        title="Eliminar Usuario"
      >
        <p className="text-sm text-gray-600 mb-6">
          Estas seguro de eliminar a <span className="font-semibold">{deleteModal.user?.full_name}</span>?
        </p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => setDeleteModal({ open: false, user: null })}
            disabled={saving}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={saving}
            className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 disabled:opacity-50 flex items-center gap-2"
          >
            {saving ? <Spinner size="h-4 w-4" /> : 'Eliminar'}
          </button>
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={() => !saving && setShowEditModal(false)}
        title="Editar Usuario"
      >
        <form onSubmit={handleEdit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
            <input
              type="text"
              value={editForm.full_name}
              onChange={(e) => setEditForm(prev => ({ ...prev, full_name: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
            <select
              value={editForm.role}
              onChange={(e) => setEditForm(prev => ({ ...prev, role: e.target.value }))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
            >
              <option value="admin">Administrador</option>
              <option value="worker">Trabajador</option>
            </select>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setShowEditModal(false)}
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
              {saving ? <Spinner size="h-4 w-4" /> : 'Guardar Cambios'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
