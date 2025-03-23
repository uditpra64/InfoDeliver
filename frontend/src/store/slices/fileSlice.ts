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
      
      // Session ID will be automatically included in headers by the api interceptor
      // No need to explicitly add it here
      
      const response = await api.post('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        }
      });
      
      console.log('File upload response:', response.data);
      
      // Extract response data
      const responseData = response.data.data;
      
      // Update session state if provided
      if (responseData.state) {
        dispatch(setState(responseData.state));
      }
      
      // Add file uploaded message to chat
      const systemMessage: Message = {
        role: 'system',
        content: `ファイル「${file.name}」をアップロードしました。`,
        timestamp: new Date().toISOString()
      };
      dispatch(addMessage(systemMessage));
      
      // Add response message to chat if available
      if (responseData.message) {
        const responseMessage: Message = {
          role: 'assistant',
          content: responseData.message,
          timestamp: new Date().toISOString()
        };
        dispatch(addMessage(responseMessage));
      }
      
      // Refresh file list after upload
      dispatch(fetchAllFiles());
      
      return responseData;
    } catch (error: any) {
      console.error('File upload error:', error);
      
      let errorMessage = 'Unknown error';
      
      if (error.response) {
        errorMessage = error.response.data?.message || error.response.statusText;
      } else if (error.request) {
        errorMessage = 'No response from server';
      } else {
        errorMessage = error.message;
      }
      
      const errorNotificationMessage: Message = {
        role: 'system',
        content: `ファイルのアップロードに失敗しました: ${errorMessage}`,
        timestamp: new Date().toISOString()
      };
      dispatch(addMessage(errorNotificationMessage));
      
      return rejectWithValue({ message: errorMessage });
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