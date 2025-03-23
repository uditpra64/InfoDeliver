import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../../services/api';
import { addMessage } from './chatSlice';
import { setState } from './sessionSlice';
import { Message } from '../../types';
interface RequiredFile {
  name: string;
  description: string;
  required: boolean;
  output: boolean;
}

interface Task {
  task_id: string;
  name: string;
  description: string;
  required_files: RequiredFile[];
  status: string;
}

interface TaskState {
  tasks: Task[];
  selectedTaskId: string | null;
  loading: boolean;
  error: string | null;
}

const initialState: TaskState = {
  tasks: [],
  selectedTaskId: null,
  loading: false,
  error: null,
};

export const fetchAllTasks = createAsyncThunk(
  'tasks/fetchAllTasks',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/tasks');
      return response.data.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to fetch tasks');
    }
  }
);

export const selectTask = createAsyncThunk(
  'tasks/selectTask',
  async (taskId: string, { dispatch, rejectWithValue }) => {
    try {
      console.log(`Calling API to select task: ${taskId}`);
      const response = await api.post(`/tasks/${taskId}/select`);
      
      console.log('Task selection response:', response.data);
      
      // Extract response data
      const responseData = response.data.data;
      
      // Update session state if available
      if (responseData.state) {
        dispatch(setState(responseData.state));
      }
      
      // Add files message to chat if available
      if (responseData.files_message) {
        dispatch(addMessage({
          role: 'assistant',
          content: responseData.files_message,
          timestamp: new Date().toISOString(),
          is_html: false
        } as Message));
      }
      
      
      return { 
        taskId, 
        sessionId: responseData.session_id, 
        state: responseData.state 
      };
    } catch (error: unknown) {
      console.error('Task selection error:', error);
      
      const errorResponse = error as { response?: { data?: { message?: string } } };
      const errorMessage = errorResponse.response?.data?.message || 'Unknown error';
      
      dispatch(addMessage({
        role: 'system',
        content: `タスク選択中にエラーが発生しました: ${errorMessage}`,
        timestamp: new Date().toISOString(),
        is_html: false
      } as Message));
      
      return rejectWithValue(errorMessage);
    }
  }
);

const taskSlice = createSlice({
  name: 'tasks',
  initialState,
  reducers: {
    clearSelectedTask: (state) => {
      state.selectedTaskId = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchAllTasks.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchAllTasks.fulfilled, (state, action) => {
        state.loading = false;
        state.tasks = action.payload;
      })
      .addCase(fetchAllTasks.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      .addCase(selectTask.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(selectTask.fulfilled, (state, action) => {
        state.loading = false;
        state.selectedTaskId = action.payload.taskId;
      })
      .addCase(selectTask.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearSelectedTask } = taskSlice.actions;
export default taskSlice.reducer;