/**
 * Returns true when the splits array is a valid payload for the API.
 *
 * Rules (mirrored server-side in `_validate_split`):
 *   - At least 2 entries
 *   - Each method must be unique
 *   - Each amount must be > 0
 *   - Sum of amounts must equal total
 */
export function isSplitValid(splits, total) {
  if (!splits || splits.length < 2) return false;
  const seen = new Set();
  let sum = 0;
  for (const s of splits) {
    if (!s.method) return false;
    const amt = Number(s.amount);
    if (!Number.isFinite(amt) || amt <= 0) return false;
    if (seen.has(s.method)) return false;
    seen.add(s.method);
    sum += amt;
  }
  return sum === total;
}
