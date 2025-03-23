import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api from '../../services/api';
import { addMessage } from './chatSlice';
import { Message } from '../../types';

interface SessionState {
  currentSessionId: string | null;
  state: string;
  loading: boolean;
  error: string | null;
  sessionCreationInProgress: boolean; // Added flag to prevent multiple creations
}

const SESSION_ID_KEY = 'payroll_session_id';

const getInitialState = (): SessionState => {
  return {
    currentSessionId: localStorage.getItem(SESSION_ID_KEY),
    state: 'chat',
    loading: false,
    error: null,
    sessionCreationInProgress: false,
  };
};

export const setSessionId = createAsyncThunk(
  'session/setSessionId',
  async (sessionId: string, { dispatch }) => {
    localStorage.setItem(SESSION_ID_KEY, sessionId);
    console.log(`Session ID set in localStorage: ${sessionId}`);
    return sessionId;
  }
);

export const createSession = createAsyncThunk(
  'session/createSession',
  async (_, { dispatch, getState, rejectWithValue }) => {
    // Get current state to check if creation is already in progress
    const state = getState() as { session: SessionState };
    
    // If we already have a session ID or creation is in progress, don't create another
    if (state.session.currentSessionId || state.session.sessionCreationInProgress) {
      return { session_id: state.session.currentSessionId };
    }
    
    try {
      // Call API to create session
      const response = await api.post('/chat', {
        message: 'Hello' // Initial message to trigger session creation
      });
      
      // Extract session data
      const sessionData = response.data.data;
      
      // If there's a response message, add it to chat
      if (sessionData.response) {
        dispatch(addMessage({
          role: 'assistant',
          content: sessionData.response,
          timestamp: new Date().toISOString(),
          is_html: sessionData.is_html || false
        } as Message));
      }
      
      return sessionData;
    } catch (error: unknown) {
      const errorResponse = error as { response?: { data?: { message?: string } } };
      return rejectWithValue(errorResponse.response?.data?.message || 'Failed to create session');
    }
  }
);

export const resetSession = createAsyncThunk(
  'session/resetSession',
  async (_, { dispatch, getState, rejectWithValue }) => {
    try {
      const state = getState() as { session: { currentSessionId: string } };
      const currentSessionId = state.session.currentSessionId;
      
      if (!currentSessionId) {
        return rejectWithValue('No active session to reset');
      }
      
      const response = await api.post('/session/reset');
      
      // If there's a welcome message in the response, add it to chat
      if (response.data?.data?.welcome_message) {
        dispatch(addMessage({
          role: 'assistant',
          content: response.data.data.welcome_message,
          timestamp: new Date().toISOString(),
          is_html: false
        } as Message));
      }
      
      return response.data;
    } catch (error: unknown) {
      const errorResponse = error as { response?: { data?: { message?: string } } };
      return rejectWithValue(errorResponse.response?.data?.message || 'Failed to reset session');
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
        state.sessionCreationInProgress = true; // Set flag when starting creation
      })
      .addCase(createSession.fulfilled, (state, action) => {
        state.loading = false;
        state.currentSessionId = action.payload.session_id;
        state.state = action.payload.state;
        state.sessionCreationInProgress = false; // Reset flag
        localStorage.setItem(SESSION_ID_KEY, action.payload.session_id);
      })
      .addCase(createSession.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
        state.sessionCreationInProgress = false; // Reset flag even on error
      });
  },
});

export const {setState, clearSession } = sessionSlice.actions;
export default sessionSlice.reducer;