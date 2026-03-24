import { Link } from 'react-router-dom';
import { ShoppingCart, Package, Users, BarChart3 } from 'lucide-react';

const features = [
  {
    icon: ShoppingCart,
    title: 'Ventas rapidas',
    description: 'Punto de venta intuitivo para agilizar cada transaccion.',
  },
  {
    icon: Package,
    title: 'Inventario en vivo',
    description: 'Control de stock en tiempo real con alertas automaticas.',
  },
  {
    icon: Users,
    title: 'Cuentas abiertas',
    description: 'Gestiona cuentas fiadas y pagos pendientes facilmente.',
  },
  {
    icon: BarChart3,
    title: 'Reportes claros',
    description: 'Visualiza ventas, ganancias y tendencias al instante.',
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Hero */}
      <section className="bg-premier-700 flex-1 flex flex-col items-center justify-center text-white px-4 py-24">
        <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight text-center">
          PREMIER PADEL BGA
        </h1>
        <p className="mt-4 text-xl md:text-2xl font-medium text-white/90 text-center">
          Sistema de Inventario
        </p>
        <p className="mt-6 max-w-xl text-center text-white/80 text-lg">
          Control total de tu cafeteria. Ventas, inventario y reportes en tiempo real.
        </p>
        <Link
          to="/login"
          className="mt-10 inline-block rounded-xl bg-white text-premier-700 font-semibold px-8 py-3 text-lg shadow-lg hover:bg-gray-100 transition-colors"
        >
          Iniciar Sesion
        </Link>
      </section>

      {/* Features */}
      <section className="bg-gray-50 py-20 px-4">
        <div className="max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-white rounded-2xl shadow-md p-6 flex flex-col items-center text-center"
            >
              <div className="bg-premier-700/10 rounded-xl p-3 mb-4">
                <f.icon className="w-8 h-8 text-premier-700" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">{f.title}</h3>
              <p className="mt-2 text-sm text-gray-500">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white border-t py-6 text-center text-sm text-gray-400">
        &copy; {new Date().getFullYear()} Premier Padel BGA. Todos los derechos reservados.
      </footer>
    </div>
  );
}
