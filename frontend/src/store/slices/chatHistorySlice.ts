import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api from '../../services/api';
import { setMessages } from './chatSlice';
import { Message } from '../../types';

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
    } catch (error: unknown) {
      console.error('Error fetching chat history:', error);
      const errorResponse = error as { response?: { data?: { message?: string } } };
      return rejectWithValue(errorResponse.response?.data?.message || 'Failed to fetch chat history');
    }
  }
);

export const selectChat = createAsyncThunk(
  'chatHistory/selectChat',
  async (index: number, { dispatch, getState, rejectWithValue }) => {
    try {
      const state = getState() as { chatHistory: { history: Array<{ id: string }> } };
      
      if (index === -1) {
        // Current chat - clear selected chat
        console.log('Selecting current chat');
        return { index };
      }
      
      if (index < 0 || index >= state.chatHistory.history.length) {
        throw new Error('Invalid chat index');
      }
      
      const chatId = state.chatHistory.history[index].id;
      console.log(`Fetching history for chat: ${chatId}`);
      
      // Load chat messages
      const response = await api.get(`/session/${chatId}/history`);
      console.log('Chat messages response:', response.data);
      
      const historyMessages = response.data.data.history;
      
      // Format messages for chat display
      const formattedMessages = historyMessages.map((msg: {
        role: string;
        content: string;
        timestamp: string;
      }) => ({
        role: msg.role as 'user' | 'assistant' | 'system',
        content: msg.content,
        timestamp: msg.timestamp,
        is_html: msg.content.includes('class="dataframe">')
      }));
      
      // Update chat messages in store
      dispatch(setMessages(formattedMessages));
      
      return { index, history: historyMessages };
    } catch (error: unknown) {
      console.error('Error selecting chat history:', error);
      const errorResponse = error as { response?: { data?: { message?: string } } };
      return rejectWithValue(errorResponse.response?.data?.message || 'Failed to select chat');
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