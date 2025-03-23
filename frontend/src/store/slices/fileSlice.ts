import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../../services/api';
import { addMessage } from './chatSlice';
import { setState } from './sessionSlice';
import { Message } from '../../types';

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
  async ({ file, sessionId }: { file: File, sessionId?: string }, { dispatch, rejectWithValue }) => {
    try {
      console.log(`Uploading file: ${file.name}, sessionId: ${sessionId}`);
      
      // Create form data
      const formData = new FormData();
      formData.append('file', file);
      
      // Auto-detect file type from extension
      const fileType = file.name.endsWith('.csv') ? 'csv' : 'excel';
      formData.append('file_type', fileType);
      
      if (sessionId) {
        formData.append('session_id', sessionId);
      }
      
      // Upload the file
      const response = await api.post('/upload', formData);
      console.log('File upload response:', response.data);
      
      // Extract response data
      const responseData = response.data.data;
      
      // Update session state if provided
      if (responseData.state) {
        dispatch(setState(responseData.state));
      }
      
      // Add file uploaded message to chat
      dispatch(addMessage({
        role: 'system',
        content: `ファイル「${file.name}」をアップロードしました。`,
        timestamp: new Date().toISOString(),
        is_html: false
      } as Message));
      
      // Add response message to chat if available
      if (responseData.message) {
        dispatch(addMessage({
          role: 'assistant',
          content: responseData.message,
          timestamp: new Date().toISOString(),
          is_html: false
        } as Message));
      }
      
      // Refresh file list after upload
      dispatch(fetchAllFiles());
      
      return responseData;
    } catch (error: unknown) {
      console.error('File upload error:', error);
      
      const errorResponse = error as { response?: { data?: { message?: string } } };
      const errorMessage = errorResponse.response?.data?.message || 'Unknown error';
      
      dispatch(addMessage({
        role: 'system',
        content: `ファイルのアップロードに失敗しました: ${errorMessage}`,
        timestamp: new Date().toISOString(),
        is_html: false
      } as Message));
      
      return rejectWithValue(errorMessage);
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