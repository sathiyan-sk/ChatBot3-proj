import axios from 'axios';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add Basic Auth for admin endpoints and the admin-only preview.
apiClient.interceptors.request.use(
  (config) => {
    const isAdminRequest =
      config.url.startsWith('/admin') ||
      config.url === '/client/chat/preview/messages';
    if (isAdminRequest) {
      const session = localStorage.getItem('oceanrag_admin_session');
      if (session) {
        try {
          const { username, password } = JSON.parse(session);
          if (username && password) {
            const credentials = btoa(`${username}:${password}`);
            config.headers.Authorization = `Basic ${credentials}`;
          }
        } catch (e) {
          console.error('Failed to parse admin session', e);
        }
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default apiClient;