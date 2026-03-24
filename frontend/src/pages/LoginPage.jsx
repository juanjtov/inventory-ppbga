import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Spinner from '../components/ui/Spinner';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate('/pos');
    } catch (err) {
      const msg = err.message || '';
      if (!err.response && (msg === 'Network Error' || msg.includes('network'))) {
        setError('No se pudo conectar con el servidor. Intenta de nuevo.');
      } else if (msg.toLowerCase().includes('invalid login credentials')) {
        setError('Correo o contraseña incorrectos');
      } else {
        setError('Credenciales inválidas');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-premier-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-8">
        {/* Logo area */}
        <div className="flex flex-col items-center mb-8">
          <div className="bg-premier-700 text-white font-extrabold text-2xl rounded-xl w-14 h-14 flex items-center justify-center">
            PP
          </div>
          <h1 className="mt-4 text-xl font-bold text-gray-900">Premier Padel BGA</h1>
          <p className="text-sm text-gray-500">Sistema de Inventario</p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm p-3">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Correo electronico
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              placeholder="tu@correo.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Contrasena
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              placeholder="********"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-premier-700 text-white font-semibold rounded-lg py-2.5 text-sm hover:bg-premier-800 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? <Spinner size="h-5 w-5" /> : 'Iniciar Sesion'}
          </button>
        </form>
      </div>
    </div>
  );
}
