// src/store/slices/sessionSlice.ts
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api from '../../services/api';

interface SessionState {
  currentSessionId: string | null;
  state: string;
  loading: boolean;
  error: string | null;
}

const SESSION_ID_KEY = 'payroll_session_id';

const getInitialState = (): SessionState => {
  return {
    currentSessionId: localStorage.getItem(SESSION_ID_KEY),
    state: 'chat',
    loading: false,
    error: null,
  };
};

export const createSession = createAsyncThunk(
  'session/createSession',
  async (_, { rejectWithValue }) => {
    try {
      // First message will automatically create a session
      const response = await api.post('/chat', {
        message: 'Hello',
      });
      
      return response.data.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to create session');
    }
  }
);

const sessionSlice = createSlice({
  name: 'session',
  initialState: getInitialState(),
  reducers: {
    setSessionId: (state, action: PayloadAction<string>) => {
      state.currentSessionId = action.payload;
      localStorage.setItem(SESSION_ID_KEY, action.payload);
    },
    setState: (state, action: PayloadAction<string>) => {
      state.state = action.payload;
    },
    clearSession: (state) => {
      state.currentSessionId = null;
      localStorage.removeItem(SESSION_ID_KEY);
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(createSession.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(createSession.fulfilled, (state, action) => {
        state.loading = false;
        state.currentSessionId = action.payload.session_id;
        state.state = action.payload.state;
        localStorage.setItem(SESSION_ID_KEY, action.payload.session_id);
      })
      .addCase(createSession.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
  },
});

export const { setSessionId, setState, clearSession } = sessionSlice.actions;
export default sessionSlice.reducer;