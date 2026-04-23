import { useState, useEffect, useCallback } from 'react';
import { Download, DollarSign, Receipt, CreditCard, Clock, Package, AlertTriangle, PackageMinus, Banknote, ArrowRightLeft, TrendingUp } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '../api/client';
import { useToast } from '../contexts/ToastContext';
import { formatCOP } from '../lib/formatCurrency';
import { todayStr } from '../lib/dateUtils';
import Spinner from '../components/ui/Spinner';

const TABS = ['Ventas', 'Inventario', 'Reconciliacion'];
const PERIODS = ['Dia', 'Semana', 'Mes', 'Rango'];
const PERIOD_MAP = { dia: 'day', semana: 'week', mes: 'month', rango: 'range' };
const FIADO_COLORS = ['#facc15', '#f97316', '#ef4444'];

function getDateRange(period, date, dateFrom, dateTo) {
  const mapped = PERIOD_MAP[period.toLowerCase()] || 'day';
  if (mapped === 'range') {
    return { date_from: dateFrom, date_to: dateTo };
  }
  const d = new Date(date + 'T12:00:00');
  if (mapped === 'day') {
    return { date_from: date, date_to: date };
  } else if (mapped === 'week') {
    const dayOfWeek = d.getDay();
    const start = new Date(d);
    start.setDate(d.getDate() - ((dayOfWeek + 6) % 7));
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return { date_from: start.toISOString().split('T')[0], date_to: end.toISOString().split('T')[0] };
  } else {
    const start = new Date(d.getFullYear(), d.getMonth(), 1);
    const end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
    return { date_from: start.toISOString().split('T')[0], date_to: end.toISOString().split('T')[0] };
  }
}

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState('Ventas');

  return (
    <div className="max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Reportes</h1>

      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-8 w-fit overflow-x-auto">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'bg-premier-700 text-white shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'Ventas' && <VentasTab />}
      {activeTab === 'Inventario' && <InventarioTab />}
      {activeTab === 'Reconciliacion' && <ReconciliacionTab />}
    </div>
  );
}

/* --- Ventas Tab --- */
function VentasTab() {
  const { addToast } = useToast();
  const [period, setPeriod] = useState('Dia');
  const [date, setDate] = useState(todayStr());
  const [dateFrom, setDateFrom] = useState(todayStr());
  const [dateTo, setDateTo] = useState(todayStr());
  const [kpis, setKpis] = useState(null);
  const [topSellers, setTopSellers] = useState([]);
  const [fiadoAging, setFiadoAging] = useState(null);
  const [dailyBreakdown, setDailyBreakdown] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const isRange = period === 'Rango';

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const mappedPeriod = PERIOD_MAP[period.toLowerCase()] || 'day';
      const range = getDateRange(period, date, dateFrom, dateTo);
      const topSellersParams = isRange
        ? { period: 'range', date: range.date_from, date_from: range.date_from, date_to: range.date_to }
        : { period: mappedPeriod, date };
      const requests = [
        api.get('/reports/daily-summary', { params: { date, date_from: range.date_from, date_to: range.date_to } }),
        api.get('/reports/top-sellers', { params: topSellersParams }),
        api.get('/reports/fiado-aging', { params: { as_of: range.date_to } }),
      ];
      if (isRange) {
        requests.push(api.get('/reports/daily-breakdown', { params: { date_from: range.date_from, date_to: range.date_to } }));
      }
      const responses = await Promise.all(requests);
      setKpis(responses[0].data);
      setTopSellers(responses[1].data);
      setFiadoAging(responses[2].data);
      setDailyBreakdown(isRange ? responses[3].data : []);
    } catch {
      addToast('Error al cargar reportes de ventas', 'error');
    } finally {
      setLoading(false);
    }
  }, [period, date, dateFrom, dateTo, isRange, addToast]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const range = getDateRange(period, date, dateFrom, dateTo);
      const res = await api.get('/reports/export/sales', {
        params: range,
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `ventas_${range.date_from}_${range.date_to}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      addToast('CSV exportado correctamente', 'success');
    } catch {
      addToast('Error al exportar CSV', 'error');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-20"><Spinner /></div>;
  }

  const chartData = topSellers.slice(0, 10).map(p => ({
    name: p.product_name?.length > 15 ? p.product_name.slice(0, 15) + '...' : p.product_name,
    cantidad: p.units_sold,
  }));

  const fiadoBuckets = fiadoAging?.buckets || [];
  const byMethod = kpis?.by_payment_method || {};

  return (
    <div className="space-y-8">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {PERIODS.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                period === p ? 'bg-white shadow text-premier-700' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
        {!isRange && (
          <input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none"
          />
        )}
        {isRange && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">Desde</label>
              <input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">Hasta</label>
              <input
                type="date"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none"
              />
            </div>
          </div>
        )}
        <button
          onClick={handleExport}
          disabled={exporting}
          className="ml-auto flex items-center gap-2 bg-premier-700 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-premier-700/90 disabled:opacity-50 transition-colors"
        >
          <Download className="w-4 h-4" />
          {exporting ? 'Exportando...' : 'Exportar CSV'}
        </button>
      </div>

      {/* KPI Cards — top row: headline numbers */}
      {kpis && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard icon={DollarSign} label="Total ventas" value={formatCOP(kpis.total_sales ?? 0)} />
            <KpiCard icon={Receipt} label="Ticket promedio" value={formatCOP(kpis.avg_ticket ?? 0)} />
            <KpiCard icon={Clock} label="Por cobrar" value={formatCOP(kpis.fiado_pending ?? 0)} accent />
            <KpiCard icon={TrendingUp} label="Cobrado de fiado" value={formatCOP(kpis.fiado_settled_in_range ?? 0)} subtitle="Fiados liquidados en el rango" />
          </div>

          {/* KPI Cards — cash-flow by method */}
          <div>
            <p className="text-xs text-gray-500 mb-2">Dinero recibido por canal — incluye fiados cobrados en el rango</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <KpiCard icon={Banknote} label="Efectivo" value={formatCOP(byMethod.efectivo ?? 0)} />
              <KpiCard icon={CreditCard} label="Datáfono" value={formatCOP(byMethod.datafono ?? 0)} />
              <KpiCard icon={ArrowRightLeft} label="Transferencia" value={formatCOP(byMethod.transferencia ?? 0)} />
              <KpiCard icon={PackageMinus} label="Uso interno" value={kpis.internal_use_count ?? 0} />
            </div>
          </div>
        </>
      )}

      {/* Per-day breakdown (only visible when Rango is active) */}
      {isRange && dailyBreakdown.length > 0 && (
        <div className="bg-white rounded-2xl shadow-md overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h3 className="font-semibold text-gray-900">Detalle por día</h3>
            <p className="text-xs text-gray-500 mt-1">Un registro por fecha con total de ventas y desglose por canal de cobro.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-left">
                <tr>
                  <th className="px-6 py-3 font-medium">Fecha</th>
                  <th className="px-6 py-3 font-medium text-right">Ventas</th>
                  <th className="px-6 py-3 font-medium text-right">Efectivo</th>
                  <th className="px-6 py-3 font-medium text-right">Datáfono</th>
                  <th className="px-6 py-3 font-medium text-right">Transferencia</th>
                  <th className="px-6 py-3 font-medium text-right">Por cobrar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {[...dailyBreakdown].sort((a, b) => b.date.localeCompare(a.date)).map(row => {
                  const m = row.by_payment_method || {};
                  return (
                    <tr key={row.date} className="hover:bg-gray-50">
                      <td className="px-6 py-3 font-medium text-gray-900">{row.date}</td>
                      <td className="px-6 py-3 text-right">{formatCOP(row.total_sales ?? 0)}</td>
                      <td className="px-6 py-3 text-right text-gray-700">{formatCOP(m.efectivo ?? 0)}</td>
                      <td className="px-6 py-3 text-right text-gray-700">{formatCOP(m.datafono ?? 0)}</td>
                      <td className="px-6 py-3 text-right text-gray-700">{formatCOP(m.transferencia ?? 0)}</td>
                      <td className="px-6 py-3 text-right text-yellow-700">{formatCOP(row.fiado_pending ?? 0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Top sellers table */}
      {topSellers.length > 0 && (
        <div className="bg-white rounded-2xl shadow-md overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h3 className="font-semibold text-gray-900">Top productos vendidos</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-left">
                <tr>
                  <th className="px-6 py-3 font-medium">#</th>
                  <th className="px-6 py-3 font-medium">Producto</th>
                  <th className="px-6 py-3 font-medium text-right">Cantidad</th>
                  <th className="px-6 py-3 font-medium text-right">Ingresos</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {topSellers.map((s, i) => (
                  <tr key={s.product_id ?? i} className="hover:bg-gray-50">
                    <td className="px-6 py-3 text-gray-400">{i + 1}</td>
                    <td className="px-6 py-3 font-medium text-gray-900">{s.product_name}</td>
                    <td className="px-6 py-3 text-right">{s.units_sold}</td>
                    <td className="px-6 py-3 text-right">{formatCOP(s.revenue ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Bar chart */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-2xl shadow-md p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Productos mas vendidos</h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="cantidad" fill="#006300" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Por cobrar aging */}
      {fiadoBuckets.length > 0 && (
        <div>
          <h3 className="font-semibold text-gray-900 mb-4">Envejecimiento de cuentas por cobrar</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {fiadoBuckets.map((b, i) => (
              <div
                key={b.label}
                className="rounded-2xl p-5 shadow-md"
                style={{ backgroundColor: `${FIADO_COLORS[i]}20`, borderLeft: `4px solid ${FIADO_COLORS[i]}` }}
              >
                <p className="text-sm font-medium text-gray-600">{b.label}</p>
                <p className="text-2xl font-bold mt-1" style={{ color: FIADO_COLORS[i] }}>{b.count}</p>
                <p className="text-sm text-gray-500 mt-1">{formatCOP(b.total)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, accent, subtitle }) {
  return (
    <div className={`bg-white rounded-2xl shadow-md p-5 ${accent ? 'border-l-4 border-yellow-400' : ''}`}>
      <div className="flex items-center gap-3 mb-2">
        <div className="bg-premier-700/10 rounded-lg p-2">
          <Icon className="w-5 h-5 text-premier-700" />
        </div>
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <p className="text-lg font-bold text-gray-900 break-words">{value}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
}

/* --- Inventario Tab --- */
function InventarioTab() {
  const { addToast } = useToast();
  const [items, setItems] = useState([]);
  const [grandTotalSale, setGrandTotalSale] = useState(0);
  const [grandTotalPurchase, setGrandTotalPurchase] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/reports/inventory-value');
        setItems(res.data.items || []);
        setGrandTotalSale(res.data.grand_total_sale || 0);
        setGrandTotalPurchase(res.data.grand_total_purchase || 0);
      } catch {
        addToast('Error al cargar reporte de inventario', 'error');
      } finally {
        setLoading(false);
      }
    })();
  }, [addToast]);

  if (loading) {
    return <div className="flex justify-center py-20"><Spinner /></div>;
  }

  return (
    <div className="bg-white rounded-2xl shadow-md overflow-hidden">
      <div className="px-6 py-4 border-b">
        <h3 className="font-semibold text-gray-900">Valor del inventario</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-left">
            <tr>
              <th className="px-6 py-3 font-medium">Producto</th>
              <th className="px-6 py-3 font-medium text-right">Stock</th>
              <th className="px-6 py-3 font-medium text-right hidden md:table-cell">Precio Venta</th>
              <th className="px-6 py-3 font-medium text-right hidden md:table-cell">Precio Compra</th>
              <th className="px-6 py-3 font-medium text-right">Valor Venta Total</th>
              <th className="px-6 py-3 font-medium text-right hidden md:table-cell">Valor Compra Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map(p => (
              <tr key={p.product_id} className={`hover:bg-gray-50 ${p.stock === 0 ? 'bg-red-50 text-red-700' : ''}`}>
                <td className="px-6 py-3 font-medium">{p.name}</td>
                <td className={`px-6 py-3 text-right font-semibold ${p.stock === 0 ? 'text-red-600' : ''}`}>{p.stock}</td>
                <td className="px-6 py-3 text-right hidden md:table-cell">{formatCOP(p.sale_price)}</td>
                <td className="px-6 py-3 text-right hidden md:table-cell">{formatCOP(p.purchase_price)}</td>
                <td className="px-6 py-3 text-right">{formatCOP(p.total_sale_value)}</td>
                <td className="px-6 py-3 text-right hidden md:table-cell">{formatCOP(p.total_purchase_value)}</td>
              </tr>
            ))}
            <tr className="bg-gray-100 font-bold">
              <td className="px-6 py-3 md:hidden" colSpan={2}>Total</td>
              <td className="px-6 py-3 hidden md:table-cell" colSpan={4}>Total</td>
              <td className="px-6 py-3 text-right">{formatCOP(grandTotalSale)}</td>
              <td className="px-6 py-3 text-right hidden md:table-cell">{formatCOP(grandTotalPurchase)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* --- Reconciliacion Tab --- */
function ReconciliacionTab() {
  const { addToast } = useToast();
  const [dateFrom, setDateFrom] = useState(todayStr());
  const [dateTo, setDateTo] = useState(todayStr());
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/reports/reconciliation', {
        params: { date_from: dateFrom, date_to: dateTo },
      });
      setData(res.data);
    } catch {
      addToast('Error al cargar reconciliacion', 'error');
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, addToast]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">Desde</label>
          <input
            type="date"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">Hasta</label>
          <input
            type="date"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-premier-700 focus:border-premier-700 outline-none"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Spinner /></div>
      ) : (
        <div className="bg-white rounded-2xl shadow-md overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-left">
                <tr>
                  <th className="px-6 py-3 font-medium">Producto</th>
                  <th className="px-6 py-3 font-medium text-right hidden md:table-cell">Vendido</th>
                  <th className="px-6 py-3 font-medium text-right hidden md:table-cell">Ingresado</th>
                  <th className="px-6 py-3 font-medium text-right hidden lg:table-cell">Uso Interno</th>
                  <th className="px-6 py-3 font-medium text-right hidden lg:table-cell">Ajustes</th>
                  <th className="px-6 py-3 font-medium text-right hidden md:table-cell">Stock Esperado</th>
                  <th className="px-6 py-3 font-medium text-right">Stock Actual</th>
                  <th className="px-6 py-3 font-medium text-right">Diferencia</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.map(r => (
                  <tr key={r.product_id ?? r.name} className={`hover:bg-gray-50 ${r.difference !== 0 ? 'bg-yellow-50' : ''}`}>
                    <td className="px-6 py-3 font-medium text-gray-900">{r.name}</td>
                    <td className="px-6 py-3 text-right hidden md:table-cell">{r.total_sold}</td>
                    <td className="px-6 py-3 text-right hidden md:table-cell">{r.total_entered}</td>
                    <td className="px-6 py-3 text-right hidden lg:table-cell">{r.total_internal_use}</td>
                    <td className={`px-6 py-3 text-right hidden lg:table-cell ${
                      (r.total_adjustments ?? 0) < 0 ? 'text-red-600' :
                      (r.total_adjustments ?? 0) > 0 ? 'text-yellow-700' : ''
                    }`}>
                      {r.total_adjustments ?? 0}
                    </td>
                    <td className="px-6 py-3 text-right hidden md:table-cell">{r.expected_stock}</td>
                    <td className="px-6 py-3 text-right">{r.actual_stock}</td>
                    <td className={`px-6 py-3 text-right font-semibold ${
                      r.difference === 0 ? 'text-green-600' :
                      r.difference < 0 ? 'text-red-600' : 'text-yellow-700'
                    }`}>
                      {r.difference > 0 ? `+${r.difference}` : r.difference}
                    </td>
                  </tr>
                ))}
                {data.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-gray-400">
                      No hay datos para el rango seleccionado
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
