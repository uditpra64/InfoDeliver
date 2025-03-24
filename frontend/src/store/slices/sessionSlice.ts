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
      console.log(`Using existing session: ${state.session.currentSessionId}`);
      return { session_id: state.session.currentSessionId };
    }
    
    try {
      // Use a dedicated session creation endpoint if available
      const response = await api.post('/session/reset');
      
      // Alternatively, if you must use the chat endpoint, be explicit about it
      // const response = await api.post('/chat', {
      //   message: '_SESSION_INIT_', // Use a special message that backend can identify
      //   is_system_message: true // Add a flag to indicate this is not a user message
      // });
      
      // Extract session data
      const sessionData = response.data.data;
      
      // Store session ID in localStorage for persistence across refreshes
      if (sessionData.session_id) {
        localStorage.setItem(SESSION_ID_KEY, sessionData.session_id);
        console.log(`Session created and stored: ${sessionData.session_id}`);
      }
      
      // If there's a welcome message but you don't want to show it yet,
      // you can choose not to dispatch it to chat
      if (sessionData.welcome_message) {
        dispatch(addMessage({
          role: 'assistant',
          content: sessionData.welcome_message,
          timestamp: new Date().toISOString(),
          is_html: false
        }as Message));
      }
      
      return sessionData;
    } catch (error) {
      console.error('Session creation failed:', error);
      
      // Extract error message with proper type handling
      const errorResponse = error as { response?: { data?: { message?: string } } };
      const errorMessage = errorResponse.response?.data?.message || 'Failed to create session';
      
      // Notify user about the error
      dispatch(addMessage({
        role: 'system',
        content: `セッション作成エラー: ${errorMessage}`,
        timestamp: new Date().toISOString(),
        is_html: false
      }as Message));
      
      return rejectWithValue(errorMessage);
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