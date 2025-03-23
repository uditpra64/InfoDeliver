import React, { useState, useRef } from 'react';
import { Box, TextField, IconButton, CircularProgress, Snackbar, Alert } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import { useAppDispatch, useAppSelector } from '../../store/hooks/reduxHooks';
import { sendMessage } from '../../store/slices/chatSlice';
import { uploadFile } from '../../store/slices/fileSlice';

const ChatInput: React.FC = () => {
  const [message, setMessage] = useState('');
  const [uploading, setUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const dispatch = useAppDispatch();
  const { loading } = useAppSelector(state => state.chat);
  const { uploadLoading, uploadError } = useAppSelector(state => state.files);
  const { currentSessionId } = useAppSelector(state => state.session);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (message.trim() && !loading) {
      console.log(`Sending message: ${message}`);
      dispatch(sendMessage({ 
        message, 
        sessionId: currentSessionId || undefined 
      }));
      setMessage('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      console.log(`File selected: ${file.name}`);
      setUploading(true);
      
      // Dispatch with the file
      dispatch(uploadFile({ 
        file, 
        sessionId: currentSessionId || undefined 
      }))
        .unwrap()
        .then(() => {
          console.log('File upload completed successfully');
        })
        .catch((error) => {
          console.error('File upload failed:', error);
          setErrorMessage(`Upload failed: ${error.message || 'Unknown error'}`);
        })
        .finally(() => {
          setUploading(false);
          // Reset file input
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
        });
    }
  };

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <IconButton 
          color="primary" 
          aria-label="upload file" 
          component="span"
          onClick={handleFileClick}
          disabled={loading || uploading || uploadLoading}
        >
          {uploadLoading || uploading ? <CircularProgress size={24} /> : <AttachFileIcon />}
        </IconButton>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          style={{ display: 'none' }}
          onChange={handleFileChange}
          disabled={loading || uploading || uploadLoading}
        />
        
        <TextField
          fullWidth
          placeholder="メッセージを入力してください..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={loading || uploading || uploadLoading}
          variant="outlined"
          size="small"
          sx={{ mx: 1 }}
        />
        
        <IconButton 
          color="primary" 
          onClick={handleSend} 
          disabled={!message.trim() || loading || uploading || uploadLoading}
        >
          {loading ? <CircularProgress size={24} /> : <SendIcon />}
        </IconButton>
      </Box>
      
      {/* Error message snackbar */}
      <Snackbar 
        open={!!errorMessage} 
        autoHideDuration={6000} 
        onClose={() => setErrorMessage(null)}
      >
        <Alert onClose={() => setErrorMessage(null)} severity="error">
          {errorMessage}
        </Alert>
      </Snackbar>
    </>
  );
};

export default ChatInput;