import { useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';

export function useProductRealtime(onUpdate) {
  useEffect(() => {
    const channel = supabase
      .channel('products-changes')
      .on('postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'products' },
        (payload) => onUpdate(payload.new)
      )
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [onUpdate]);
}
