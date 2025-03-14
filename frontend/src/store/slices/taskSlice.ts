// src/store/slices/taskSlice.ts
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../../services/api';

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
  async (taskId: string, { rejectWithValue }) => {
    try {
      // Notify backend about task selection
      const response = await api.post(`/tasks/${taskId}/select`);
      return { taskId, ...response.data.data };
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to select task');
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