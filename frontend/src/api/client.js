import axios from 'axios';
import { supabase } from '../lib/supabaseClient';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

api.interceptors.request.use(async (config) => {
  // Ensure trailing slash to avoid CORS-breaking 307 redirects
  if (config.url && !config.url.endsWith('/') && !config.url.includes('?')) {
    config.url = config.url + '/';
  }
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      supabase.auth.signOut();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
