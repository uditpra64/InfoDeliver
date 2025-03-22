// src/store/slices/fileSlice.ts
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../../services/api';

// Rename this to FileInfo to avoid conflict with browser's File type
interface FileInfo {
  id: number;
  name: string;
  task_name: string;
  upload_date: string;
  row_count: number;
  output: boolean;
}

interface FileState {
  files: FileInfo[];
  loading: boolean;
  error: string | null;
  uploadLoading: boolean;
  uploadError: string | null;
}

const initialState: FileState = {
  files: [],
  loading: false,
  error: null,
  uploadLoading: false,
  uploadError: null,
};

export const fetchAllFiles = createAsyncThunk(
  'files/fetchAllFiles',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/files');
      return response.data.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to fetch files');
    }
  }
);


export const uploadFile = createAsyncThunk(
  'files/uploadFile',
  async ({ file, sessionId }: { file: File, sessionId?: string }, { rejectWithValue, dispatch }) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      // Auto-detect file type from extension
      const fileType = file.name.endsWith('.csv') ? 'csv' : 'excel';
      formData.append('file_type', fileType);
      
      if (sessionId) {
        formData.append('session_id', sessionId);
      }
      
      // Make sure Content-Type is NOT set manually for file uploads
      const response = await api.post('/upload', formData);
      
      // Refresh file list after upload
      dispatch(fetchAllFiles());
      
      return response.data.data;
    } catch (error: any) {
      return rejectWithValue(error.response?.data?.message || 'Failed to upload file');
    }
  }
);

const fileSlice = createSlice({
  name: 'files',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchAllFiles.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchAllFiles.fulfilled, (state, action) => {
        state.loading = false;
        state.files = action.payload;
      })
      .addCase(fetchAllFiles.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      .addCase(uploadFile.pending, (state) => {
        state.uploadLoading = true;
        state.uploadError = null;
      })
      .addCase(uploadFile.fulfilled, (state) => {
        state.uploadLoading = false;
      })
      .addCase(uploadFile.rejected, (state, action) => {
        state.uploadLoading = false;
        state.uploadError = action.payload as string;
      });
  },
});

export default fileSlice.reducer;