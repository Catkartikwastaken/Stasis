import axios from 'axios';

const isLocalFile = typeof window !== 'undefined' && window.location.protocol === 'file:';
const serverUrl = isLocalFile ? 'http://localhost:5000/api/v1' : '/api/v1';

const api = axios.create({
  baseURL: serverUrl,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' }
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API]', error.message);
    return Promise.reject(error);
  }
);

export default api;
