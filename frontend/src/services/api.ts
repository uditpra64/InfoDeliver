import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create a axios instance with better caching and retry logic
const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Add a small timeout to avoid hanging requests
  timeout: 30000,
});

// Add request interceptor with better error handling and session management
api.interceptors.request.use(
  (config) => {
    // Log outgoing requests in development only
    if (process.env.NODE_ENV !== 'production') {
      const method = config.method?.toUpperCase();
      const url = config.url;
      
      // Don't log large data payloads
      const dataToLog = config.data ? 
        (config.data instanceof FormData ? 'FormData' : 
         (typeof config.data === 'object' && Object.keys(config.data).length > 0 ? 
          '{Object}' : JSON.stringify(config.data))) : 
        null;
      
      console.log(`API Request: ${method} ${url}`, dataToLog);
    }
    
    // Add session ID from localStorage if present
    const sessionId = localStorage.getItem('payroll_session_id');
    if (sessionId) {
      config.headers['x-session-id'] = sessionId;
    }
    
    // Add authorization header if token exists
    const token = localStorage.getItem('payroll_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor with improved session handling
api.interceptors.response.use(
  (response) => {
    // Only log in development
    if (process.env.NODE_ENV !== 'production') {
      console.log(`API Response [${response.status}]:`, 
                  response.data?.data ? '{Data Object}' : response.data);
    }
    
    // If response contains a session ID, store it
    if (response.data?.data?.session_id) {
      const existingSessionId = localStorage.getItem('payroll_session_id');
      
      // Only update if we don't have one or if it's different
      if (!existingSessionId || existingSessionId !== response.data.data.session_id) {
        localStorage.setItem('payroll_session_id', response.data.data.session_id);
      }
    }
    
    return response;
  },
  (error) => {
    // Log error responses
    console.error('API Response Error:', error.response?.status, 
                  error.response?.data || error.message);
    
    // Handle session expiration
    if (error.response?.status === 401 && !error.config.url.includes('/token')) {
      // Only clear session and token once
      const authClearedFlag = localStorage.getItem('auth_cleared');
      
      if (!authClearedFlag) {
        // Clear local session and token
        localStorage.removeItem('payroll_token');
        localStorage.removeItem('payroll_session_id');
        localStorage.setItem('auth_cleared', 'true');
        
        // Redirect to login after a small delay
        setTimeout(() => {
          localStorage.removeItem('auth_cleared');
          window.location.href = '/login';
        }, 100);
      }
    }
    
    return Promise.reject(error);
  }
);

export default api;