import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ToastProvider } from './contexts/ToastContext';
import { useKeepAlive } from './hooks/useKeepAlive';
import ProtectedRoute from './components/layout/ProtectedRoute';
import AppLayout from './components/layout/AppLayout';
import RoleGuard from './components/layout/RoleGuard';

import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import POSPage from './pages/POSPage';
import InventoryPage from './pages/InventoryPage';
import InventoryEntryPage from './pages/InventoryEntryPage';
import InternalUsePage from './pages/InternalUsePage';
import OpenAccountsPage from './pages/OpenAccountsPage';
import CashClosingPage from './pages/CashClosingPage';
import ReportsPage from './pages/ReportsPage';
import CatalogPage from './pages/CatalogPage';
import UsersPage from './pages/UsersPage';
import AlertsPage from './pages/AlertsPage';
import SalesHistoryPage from './pages/SalesHistoryPage';
import ProductMovementsPage from './pages/ProductMovementsPage';
import StockAdjustmentsPage from './pages/StockAdjustmentsPage';

function App() {
  useKeepAlive();

  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route index element={<Navigate to="/pos" />} />
                <Route path="/pos" element={<POSPage />} />
                <Route path="/inventario" element={<InventoryPage />} />
                <Route path="/cuentas" element={<OpenAccountsPage />} />

                <Route path="/inventario/ingreso" element={<RoleGuard roles={['owner','admin']}><InventoryEntryPage /></RoleGuard>} />
                <Route path="/inventario/uso-interno" element={<RoleGuard roles={['owner','admin']}><InternalUsePage /></RoleGuard>} />
                <Route path="/inventario/ajustes" element={<RoleGuard roles={['owner']}><StockAdjustmentsPage /></RoleGuard>} />
                <Route path="/corte-caja" element={<RoleGuard roles={['owner','admin']}><CashClosingPage /></RoleGuard>} />
                <Route path="/ventas" element={<RoleGuard roles={['owner','admin']}><SalesHistoryPage /></RoleGuard>} />
                <Route path="/inventario/movimientos/:productId" element={<RoleGuard roles={['owner','admin']}><ProductMovementsPage /></RoleGuard>} />
                <Route path="/catalogo" element={<RoleGuard roles={['owner','admin']}><CatalogPage /></RoleGuard>} />
                <Route path="/alertas" element={<RoleGuard roles={['owner','admin']}><AlertsPage /></RoleGuard>} />

                <Route path="/reportes" element={<RoleGuard roles={['owner']}><ReportsPage /></RoleGuard>} />
                <Route path="/usuarios" element={<RoleGuard roles={['owner']}><UsersPage /></RoleGuard>} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}

export default App;
