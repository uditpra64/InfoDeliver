import React, { useState, useRef } from 'react';
import { Box, TextField, IconButton } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import { useAppDispatch, useAppSelector } from '../../store/hooks/reduxHooks';
import { sendMessage } from '../../store/slices/chatSlice';
import { uploadFile } from '../../store/slices/fileSlice';

const ChatInput: React.FC = () => {
  const [message, setMessage] = useState('');
  const dispatch = useAppDispatch();
  const { loading } = useAppSelector(state => state.chat);
  const { currentSessionId } = useAppSelector(state => state.session);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (message.trim() && !loading) {
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
      dispatch(uploadFile({ 
        file, 
        sessionId: currentSessionId || undefined 
      }));
    }
  };

  return (
    <Box sx={{ display: 'flex', alignItems: 'center' }}>
      <IconButton 
        color="primary" 
        aria-label="upload file" 
        component="span"
        onClick={handleFileClick}
      >
        <AttachFileIcon />
      </IconButton>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      
      <TextField
        fullWidth
        placeholder="メッセージを入力してください..."
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyPress={handleKeyPress}
        disabled={loading}
        variant="outlined"
        size="small"
        sx={{ mx: 1 }}
      />
      
      <IconButton 
        color="primary" 
        onClick={handleSend} 
        disabled={!message.trim() || loading}
      >
        <SendIcon />
      </IconButton>
    </Box>
  );
};

export default ChatInput;