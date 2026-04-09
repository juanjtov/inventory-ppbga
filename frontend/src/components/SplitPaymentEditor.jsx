import { Banknote, CreditCard, ArrowRightLeft, X, Plus, Check } from 'lucide-react';
import { formatCOP } from '../lib/formatCurrency';

const SPLIT_METHODS = [
  { value: 'efectivo', label: 'Efectivo', icon: Banknote },
  { value: 'datafono', label: 'Datafono', icon: CreditCard },
  { value: 'transferencia', label: 'Transferencia', icon: ArrowRightLeft },
];

const METHOD_BY_VALUE = Object.fromEntries(SPLIT_METHODS.map(m => [m.value, m]));

/**
 * SplitPaymentEditor — controlled list of {method, amount} entries.
 *
 * Props:
 *   total: number — the sale total the splits must sum to
 *   splits: Array<{method: string, amount: string|number}>
 *   onChange: (newSplits) => void
 *
 * Validation rules (also enforced server-side):
 *   - At least 2 entries
 *   - Each method must be unique
 *   - Each amount must be > 0
 *   - Sum of amounts must equal total
 */
export default function SplitPaymentEditor({ total, splits, onChange }) {
  const sum = splits.reduce((acc, s) => acc + (Number(s.amount) || 0), 0);
  const remaining = total - sum;
  const remainingZero = remaining === 0 && splits.length >= 2 && splits.every(s => Number(s.amount) > 0);

  // Methods that haven't been used yet
  function availableMethods(forIndex) {
    const used = new Set(splits.map((s, i) => (i === forIndex ? null : s.method)));
    return SPLIT_METHODS.filter(m => !used.has(m.value));
  }

  function updateSplit(index, patch) {
    const next = splits.map((s, i) => (i === index ? { ...s, ...patch } : s));
    onChange(next);
  }

  function addSplit() {
    if (splits.length >= SPLIT_METHODS.length) return;
    // pick the first available method
    const used = new Set(splits.map(s => s.method));
    const next = SPLIT_METHODS.find(m => !used.has(m.value));
    if (!next) return;
    onChange([...splits, { method: next.value, amount: '' }]);
  }

  function removeSplit(index) {
    onChange(splits.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-2">
      <div className="space-y-2">
        {splits.map((split, index) => {
          const options = availableMethods(index);
          const Icon = METHOD_BY_VALUE[split.method]?.icon || Banknote;
          return (
            <div key={index} className="flex items-center gap-2">
              <Icon className="w-4 h-4 text-gray-500 flex-shrink-0" />
              <select
                value={split.method}
                onChange={(e) => updateSplit(index, { method: e.target.value })}
                className="flex-1 rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent bg-white"
              >
                {options.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <input
                type="number"
                inputMode="numeric"
                min="0"
                placeholder="0"
                value={split.amount}
                onChange={(e) => updateSplit(index, { amount: e.target.value })}
                className="w-28 rounded-lg border border-gray-300 px-2 py-1.5 text-sm text-right focus:outline-none focus:ring-2 focus:ring-premier-700 focus:border-transparent"
              />
              {splits.length > 2 && (
                <button
                  type="button"
                  onClick={() => removeSplit(index)}
                  className="text-gray-400 hover:text-red-500"
                  aria-label="Eliminar método"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      <button
        type="button"
        onClick={addSplit}
        disabled={splits.length >= SPLIT_METHODS.length}
        className="flex items-center gap-1 text-xs text-premier-700 hover:text-premier-800 font-medium disabled:text-gray-300 disabled:cursor-not-allowed"
      >
        <Plus className="w-3 h-3" /> Agregar método
      </button>

      <div
        className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium border ${
          remainingZero
            ? 'bg-green-50 border-green-200 text-green-700'
            : 'bg-yellow-50 border-yellow-200 text-yellow-700'
        }`}
      >
        <span>Restante</span>
        <span className="flex items-center gap-1">
          {formatCOP(remaining)}
          {remainingZero && <Check className="w-4 h-4" />}
        </span>
      </div>
    </div>
  );
}

