import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    // Log outgoing requests
    const method = config.method?.toUpperCase();
    const url = config.url;
    const data = config.data ? 
      (config.data instanceof FormData ? 'FormData' : JSON.stringify(config.data)) : 
      null;
    
    console.log(`API Request: ${method} ${url}`, data);
    
    // Add session ID from localStorage if present
    const sessionId = localStorage.getItem('payroll_session_id');
    if (sessionId) {
      config.headers['x-session-id'] = sessionId;
    }
    
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for debugging
api.interceptors.response.use(
  (response) => {
    // Log successful responses
    console.log(`API Response [${response.status}]:`, response.data);
    
    // If response contains a session ID, store it
    if (response.data?.data?.session_id) {
      localStorage.setItem('payroll_session_id', response.data.data.session_id);
    }
    
    return response;
  },
  (error) => {
    // Log error responses
    console.error('API Response Error:', error.response?.status, error.response?.data);
    
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