import { useEffect } from 'react';

const PING_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

const healthUrl =
  import.meta.env.VITE_API_BASE_URL.replace(/\/api\/v1\/?$/, '') + '/health';

export function useKeepAlive() {
  useEffect(() => {
    const ping = () => fetch(healthUrl).catch(() => {});

    ping();
    const id = setInterval(ping, PING_INTERVAL_MS);

    return () => clearInterval(id);
  }, []);
}
