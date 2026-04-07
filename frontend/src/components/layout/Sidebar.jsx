import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useState, useEffect } from 'react';
import api from '../../api/client';
import {
  ShoppingCart, Package, Users, Calculator, BarChart3,
  BookOpen, UserCog, AlertTriangle, ReceiptText, LogOut,
  Menu, X,
} from 'lucide-react';

const navItems = [
  { path: '/pos', label: 'POS', icon: ShoppingCart, roles: ['owner', 'admin', 'worker'] },
  { path: '/inventario', label: 'Inventario', icon: Package, roles: ['owner', 'admin', 'worker'] },
  { path: '/cuentas', label: 'Cuentas Abiertas', icon: Users, roles: ['owner', 'admin', 'worker'] },
  { path: '/corte-caja', label: 'Corte de Caja', icon: Calculator, roles: ['owner', 'admin'] },
  { path: '/ventas', label: 'Historial de Ventas', icon: ReceiptText, roles: ['owner', 'admin'] },
  { path: '/reportes', label: 'Reportes', icon: BarChart3, roles: ['owner'] },
  { path: '/catalogo', label: 'Catalogo', icon: BookOpen, roles: ['owner', 'admin'] },
  { path: '/usuarios', label: 'Usuarios', icon: UserCog, roles: ['owner'] },
  { path: '/alertas', label: 'Alertas', icon: AlertTriangle, roles: ['owner', 'admin'], hasBadge: true },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [alertCount, setAlertCount] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    api.get('/products/low-stock')
      .then(res => setAlertCount(res.data.length))
      .catch(() => {});
  }, [location.pathname]);

  // Close drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const filteredItems = navItems.filter(item => item.roles.includes(user?.role));

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="p-5 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-premier-700 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            PP
          </div>
          <span className="text-premier-700 font-bold text-sm">PREMIER PADEL</span>
        </div>
        <button
          onClick={() => setMobileOpen(false)}
          className="md:hidden text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {filteredItems.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-premier-700 text-white'
                  : 'text-gray-600 hover:bg-premier-50 hover:text-premier-700'
              }`
            }
          >
            <item.icon className="w-5 h-5" />
            {item.label}
            {item.hasBadge && alertCount > 0 && (
              <span className="ml-auto bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {alertCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User info */}
      <div className="p-4 border-t border-gray-100">
        <div className="text-sm font-medium text-gray-900">{user?.full_name}</div>
        <div className="flex items-center justify-between mt-1">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            user?.role === 'owner' ? 'bg-premier-100 text-premier-700' :
            user?.role === 'admin' ? 'bg-blue-100 text-blue-700' :
            'bg-gray-100 text-gray-600'
          }`}>
            {user?.role === 'owner' ? 'Propietario' : user?.role === 'admin' ? 'Admin' : 'Trabajador'}
          </span>
          <button
            onClick={handleLogout}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            title="Cerrar sesion"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-30 bg-white border-b border-gray-200 flex items-center gap-3 px-4 h-14">
        <button onClick={() => setMobileOpen(true)} className="text-gray-600">
          <Menu className="w-6 h-6" />
        </button>
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-premier-700 rounded-lg flex items-center justify-center text-white font-bold text-xs">
            PP
          </div>
          <span className="text-premier-700 font-bold text-sm">PREMIER PADEL</span>
        </div>
      </div>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/50"
          onClick={() => setMobileOpen(false)}
        >
          <aside
            className="w-72 bg-white flex flex-col h-full"
            onClick={(e) => e.stopPropagation()}
          >
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-60 bg-white border-r border-gray-200 flex-col min-h-screen">
        {sidebarContent}
      </aside>
    </>
  );
}
