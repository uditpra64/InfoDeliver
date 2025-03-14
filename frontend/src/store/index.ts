import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import chatReducer from './slices/chatSlice';
import chatHistoryReducer from './slices/chatHistorySlice';
import fileReducer from './slices/fileSlice';
import taskReducer from './slices/taskSlice';
import sessionReducer from './slices/sessionSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    chat: chatReducer,
    chatHistory: chatHistoryReducer,
    files: fileReducer,
    tasks: taskReducer,
    session: sessionReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;