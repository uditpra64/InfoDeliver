// src/services/api.ts
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to add session ID to headers
api.interceptors.request.use((config) => {
  const sessionId = localStorage.getItem('payroll_session_id');
  if (sessionId) {
    config.headers['x-session-id'] = sessionId;
  }
  return config;
});

// Add response interceptor to handle common errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle session expiration
    if (error.response?.status === 401 && !error.config.url.includes('/token')) {
      // Clear local session and token
      localStorage.removeItem('payroll_token');
      localStorage.removeItem('payroll_session_id');
      // Redirect to login
      window.location.href = '/login';
    }
    
    return Promise.reject(error);
  }
);

export default api;