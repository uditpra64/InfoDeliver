// src/store/slices/authSlice.ts
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../../services/api';
import { jwtDecode } from 'jwt-decode';

interface JwtPayload {
  sub: string;
  scopes: string[];
  exp: number;
}

interface User {
  username: string;
  scopes: string[];
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
}

const TOKEN_KEY = 'payroll_token';

const getInitialState = (): AuthState => {
  const token = localStorage.getItem(TOKEN_KEY);
  let user = null;
  let isAuthenticated = false;
  
  if (token) {
    try {
      const decodedToken = jwtDecode<JwtPayload>(token);
      // Check if token is expired
      const isExpired = decodedToken.exp * 1000 < Date.now();
      
      if (!isExpired) {
        user = {
          username: decodedToken.sub,
          scopes: decodedToken.scopes,
        };
        isAuthenticated = true;
        
        // Set token in API headers for all subsequent requests
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      } else {
        // Token expired, clear it
        localStorage.removeItem(TOKEN_KEY);
      }
    } catch (error) {
      // Invalid token, clear it
      localStorage.removeItem(TOKEN_KEY);
    }
  }
  
  return {
    token,
    user,
    isAuthenticated,
    loading: false,
    error: null,
  };
};

export const login = createAsyncThunk(
  'auth/login',
  async ({ username, password }: { username: string, password: string }, { rejectWithValue }) => {
    try {
      const response = await api.post('/token', new URLSearchParams({
        username,
        password,
      }), {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });
      
      const { access_token, token_type, expires_at } = response.data;
      
      // Store token in localStorage
      localStorage.setItem(TOKEN_KEY, access_token);
      
      // Set token in API headers for all subsequent requests
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      // Decode token to get user info
      const decodedToken = jwtDecode<JwtPayload>(access_token);
      
      return {
        token: access_token,
        user: {
          username: decodedToken.sub,
          scopes: decodedToken.scopes,
        },
      };
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Login failed');
    }
  }
);

export const logout = createAsyncThunk(
  'auth/logout',
  async (_, { dispatch }) => {
    localStorage.removeItem(TOKEN_KEY);
    delete api.defaults.headers.common['Authorization'];
    return true;
  }
);

const authSlice = createSlice({
  name: 'auth',
  initialState: getInitialState(),
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(login.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(login.fulfilled, (state, action) => {
        state.loading = false;
        state.token = action.payload.token;
        state.user = action.payload.user;
        state.isAuthenticated = true;
      })
      .addCase(login.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
        state.isAuthenticated = false;
        state.user = null;
        state.token = null;
      })
      .addCase(logout.fulfilled, (state) => {
        state.token = null;
        state.user = null;
        state.isAuthenticated = false;
        state.error = null;
      });
  },
});

export const { clearError } = authSlice.actions;
export default authSlice.reducer;