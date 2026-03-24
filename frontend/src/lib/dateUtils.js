/**
 * Returns today's date as YYYY-MM-DD in Colombia timezone (UTC-5).
 * Prevents the "next day" bug caused by new Date().toISOString() using UTC.
 */
export function todayStr() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
}
