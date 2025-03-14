// src/store/slices/chatHistorySlice.ts
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api from '../../services/api';

interface ChatSummary {
  id: string;
  title: string;
  lastUpdate: string;
}

interface ChatHistoryState {
  history: ChatSummary[];
  selectedChatIndex: number;
  loading: boolean;
  error: string | null;
}

const initialState: ChatHistoryState = {
  history: [],
  selectedChatIndex: -1,  // -1 means current chat is selected
  loading: false,
  error: null,
};

export const fetchChatHistory = createAsyncThunk(
  'chatHistory/fetchChatHistory',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/session/history');
      return response.data.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to fetch chat history');
    }
  }
);

export const selectChat = createAsyncThunk(
  'chatHistory/selectChat',
  async (index: number, { rejectWithValue, getState }) => {
    try {
      const state = getState() as { chatHistory: ChatHistoryState };
      
      if (index === -1) {
        // Current chat
        return { index };
      }
      
      if (index < 0 || index >= state.chatHistory.history.length) {
        throw new Error('Invalid chat index');
      }
      
      const chatId = state.chatHistory.history[index].id;
      
      // Load chat messages
      const response = await api.get(`/session/${chatId}/history`);
      
      return { index, history: response.data.data.history };
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to select chat');
    }
  }
);

const chatHistorySlice = createSlice({
  name: 'chatHistory',
  initialState,
  reducers: {
    addHistory: (state, action: PayloadAction<ChatSummary>) => {
      state.history.push(action.payload);
    },
    clearHistory: (state) => {
      state.history = [];
      state.selectedChatIndex = -1;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchChatHistory.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchChatHistory.fulfilled, (state, action) => {
        state.loading = false;
        state.history = action.payload;
      })
      .addCase(fetchChatHistory.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      .addCase(selectChat.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(selectChat.fulfilled, (state, action) => {
        state.loading = false;
        state.selectedChatIndex = action.payload.index;
      })
      .addCase(selectChat.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
  },
});

export const { addHistory, clearHistory } = chatHistorySlice.actions;
export default chatHistorySlice.reducer;