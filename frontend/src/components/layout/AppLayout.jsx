import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { CartProvider } from '../../contexts/CartContext';

export default function AppLayout() {
  return (
    <CartProvider>
      <div className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 bg-gray-50 min-h-screen px-4 pb-4 pt-18 md:p-8">
          <div className="max-w-[1200px] mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </CartProvider>
  );
}
