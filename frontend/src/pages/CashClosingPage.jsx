import { useState, useEffect } from 'react';
import { Calculator, Save, Lock } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import { todayStr } from '../lib/dateUtils';
import Spinner from '../components/ui/Spinner';

export default function CashClosingPage() {
  const { addToast } = useToast();

  const [date, setDate] = useState(todayStr);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [data, setData] = useState(null);
  const [physicalCash, setPhysicalCash] = useState('');
  const [notes, setNotes] = useState('');
  const [readOnly, setReadOnly] = useState(false);

  useEffect(() => {
    fetchData();
  }, [date]);

  async function fetchData() {
    setLoading(true);
    try {
      const res = await api.get(`/reports/cash-closing?date=${date}`);
      if (res.data.existing) {
        // Merge closing data to top level so summary rows can read it
        setData({ ...res.data.closing, existing: true });
        setReadOnly(true);
        setPhysicalCash(res.data.closing?.physical_cash ?? '');
        setNotes(res.data.closing?.notes ?? '');
      } else {
        setData(res.data);
        setReadOnly(false);
        setPhysicalCash('');
        setNotes('');
      }
    } catch {
      addToast('Error al cargar datos del corte', 'error');
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (physicalCash === '' || isNaN(Number(physicalCash))) {
      addToast('Ingresa el efectivo fisico contado', 'error');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/reports/cash-closing', {
        closing_date: date,
        physical_cash: Number(physicalCash),
        notes: notes.trim() || null,
      });
      addToast('Corte de caja guardado exitosamente', 'success');
      fetchData();
    } catch (err) {
      addToast(err.response?.data?.detail || 'Error al guardar corte', 'error');
    } finally {
      setSubmitting(false);
    }
  }

  const totalCash = data?.total_cash ?? 0;
  const difference = physicalCash !== '' && !isNaN(Number(physicalCash))
    ? Number(physicalCash) - totalCash
    : null;

  function getDiffColor() {
    if (difference === null) return 'text-gray-500';
    if (difference === 0) return 'text-green-600';
    if (difference < 0) return 'text-red-600';
    return 'text-yellow-600';
  }

  function getDiffBg() {
    if (difference === null) return 'bg-gray-50';
    if (difference === 0) return 'bg-green-50 border-green-200';
    if (difference < 0) return 'bg-red-50 border-red-200';
    return 'bg-yellow-50 border-yellow-200';
  }

  const summaryRows = data ? [
    { label: 'Total Ventas', value: data.total_sales },
    { label: 'Efectivo', value: data.total_cash },
    { label: 'Datafono', value: data.total_datafono },
    { label: 'Transferencia', value: data.total_transfer },
    { label: 'Fiado', value: data.total_fiado },
    { label: 'Anuladas', value: data.total_voided },
    { label: 'Uso Interno', value: data.total_internal_use },
  ] : [];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-2 mb-6">
        <Calculator className="w-6 h-6 text-premier-700" />
        <h1 className="text-xl font-bold text-gray-900">Corte de Caja</h1>
        {readOnly && (
          <span className="ml-2 flex items-center gap-1 text-xs bg-gray-100 text-gray-500 rounded-full px-2 py-0.5">
            <Lock className="w-3 h-3" /> Guardado
          </span>
        )}
      </div>

      {/* Date selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-1">Fecha</label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
        />
      </div>

      {!data ? (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center text-gray-500">
          No hay datos para esta fecha
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Summary */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Resumen del Dia</h2>
            <div className="space-y-2">
              {summaryRows.map(row => (
                <div key={row.label} className="flex justify-between text-sm">
                  <span className="text-gray-600">{row.label}</span>
                  <span className="font-medium text-gray-900">{formatCOP(row.value ?? 0)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Physical cash input */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Efectivo fisico contado
            </label>
            <input
              type="number"
              value={physicalCash}
              onChange={(e) => setPhysicalCash(e.target.value)}
              disabled={readOnly}
              placeholder="0"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
              required
            />

            {/* Difference */}
            {difference !== null && (
              <div className={`mt-3 rounded-lg border p-3 ${getDiffBg()}`}>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Diferencia</span>
                  <span className={`text-lg font-bold ${getDiffColor()}`}>
                    {formatCOP(difference)}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {difference === 0
                    ? 'El efectivo cuadra perfectamente'
                    : difference < 0
                    ? 'Faltante de efectivo'
                    : 'Sobrante de efectivo'}
                </p>
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Notas
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={readOnly}
              rows={3}
              placeholder="Observaciones del cierre..."
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent resize-none disabled:bg-gray-50 disabled:text-gray-500"
            />
          </div>

          {/* Submit */}
          {!readOnly && (
            <button
              type="submit"
              disabled={submitting || physicalCash === ''}
              className="w-full bg-premier-700 text-white font-semibold rounded-lg py-2.5 text-sm hover:bg-premier-800 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {submitting ? <Spinner size="h-5 w-5" /> : (
                <>
                  <Save className="w-4 h-4" />
                  Guardar Corte
                </>
              )}
            </button>
          )}
        </form>
      )}
    </div>
  );
}
