// src/store/slices/chatSlice.ts
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api from '../../services/api';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

interface ChatState {
  messages: Message[];
  loading: boolean;
  error: string | null;
}

const initialState: ChatState = {
  messages: [],
  loading: false,
  error: null,
};

export const sendMessage = createAsyncThunk(
  'chat/sendMessage',
  async ({ message, sessionId }: { message: string, sessionId?: string }, { rejectWithValue }) => {
    try {
      const response = await api.post('/chat', { message, session_id: sessionId });
      return response.data.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to send message');
    }
  }
);

export const startNewChat = createAsyncThunk(
  'chat/startNewChat',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.post('/session/reset');
      return response.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to start new chat');
    }
  }
);

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    clearMessages: (state) => {
      state.messages = [];
    },
    addMessage: (state, action: PayloadAction<Message>) => {
      state.messages.push(action.payload);
    },
    setMessages: (state, action: PayloadAction<Message[]>) => {
      state.messages = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendMessage.pending, (state, action) => {
        state.loading = true;
        state.error = null;
        // Add user message immediately to UI
        state.messages.push({
          role: 'user',
          content: action.meta.arg.message,
          timestamp: new Date().toISOString(),
        });
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.loading = false;
        // Add assistant response
        state.messages.push({
          role: 'assistant',
          content: action.payload.response,
          timestamp: action.payload.timestamp,
        });
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      .addCase(startNewChat.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(startNewChat.fulfilled, (state) => {
        state.loading = false;
        state.messages = [];
        // Add system welcome message
        state.messages.push({
          role: 'assistant',
          content: 'ようこそ！\n私は給与計算タスク管理エージェントです！すべてのタスクを紹介し、それぞれのタスクとその処理ルールを詳しく説明することができます。その後、どのタスクに取り組むかを選択するお手伝いをします。',
          timestamp: new Date().toISOString(),
        });
      })
      .addCase(startNewChat.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearMessages, addMessage, setMessages } = chatSlice.actions;
export default chatSlice.reducer;