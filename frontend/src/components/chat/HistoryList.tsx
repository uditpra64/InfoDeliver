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
    console.log('Initializing history list, fetching chat history');
    dispatch(fetchChatHistory());
  }, [dispatch]);

  const handleChatSelect = (index: number) => {
    console.log(`Selecting chat at index: ${index}`);
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
          <ListItem key={`chat-${index}-${chat.id}`} disablePadding>
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
        <ListItem>
          <ListItemButton 
            selected={selectedChatIndex === -1}
            onClick={() => handleChatSelect(-1)}
          >
            <ListItemText primary="現在のチャット" />
          </ListItemButton>
        </ListItem>
      </List>
    </>
  );
};

export default HistoryList;