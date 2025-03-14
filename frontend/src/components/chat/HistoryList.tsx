// src/components/chat/HistoryList.tsx
import React, { useEffect } from 'react';
import { 
  Typography, 
  List, 
  ListItem, 
  ListItemText, 
  ListItemButton, 
  CircularProgress 
} from '@mui/material';
import { useAppDispatch, useAppSelector } from '../../store/hooks/reduxHooks';
import { fetchChatHistory, selectChat } from '../../store/slices/chatHistorySlice';

const HistoryList: React.FC = () => {
  const dispatch = useAppDispatch();
  const { history, loading, error, selectedChatIndex } = useAppSelector(state => state.chatHistory);

  useEffect(() => {
    dispatch(fetchChatHistory());
  }, [dispatch]);

  const handleChatSelect = (index: number) => {
    dispatch(selectChat(index));
  };

  if (loading) {
    return <CircularProgress />;
  }

  if (error) {
    return <Typography color="error">{error}</Typography>;
  }

  return (
    <>
      <Typography variant="h6" component="h2" gutterBottom>
        チャット履歴
      </Typography>
      <List sx={{ width: '100%', bgcolor: 'background.paper' }}>
        {history.map((chat, index) => (
          <ListItem key={`chat-${index}`} disablePadding>
            <ListItemButton
              selected={index === selectedChatIndex}
              onClick={() => handleChatSelect(index)}
            >
              <ListItemText 
                primary={`チャット ${index + 1}`} 
                secondary={chat.lastUpdate} 
              />
            </ListItemButton>
          </ListItem>
        ))}
        {history.length === 0 && (
          <ListItem>
            <ListItemText primary="履歴がありません" />
          </ListItem>
        )}
        {selectedChatIndex === -1 && history.length > 0 && (
          <ListItem>
            <ListItemButton selected>
              <ListItemText primary="現在のチャット" />
            </ListItemButton>
          </ListItem>
        )}
      </List>
    </>
  );
};

export default HistoryList;