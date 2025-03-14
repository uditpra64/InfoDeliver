// src/components/chat/NewChatButton.tsx
import React from 'react';
import { Button } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { useAppDispatch } from '../../store/hooks/reduxHooks';
import { startNewChat } from '../../store/slices/chatSlice';

const NewChatButton: React.FC = () => {
  const dispatch = useAppDispatch();

  const handleNewChat = () => {
    dispatch(startNewChat());
  };

  return (
    <Button
      variant="contained"
      color="primary"
      startIcon={<AddIcon />}
      onClick={handleNewChat}
      fullWidth
    >
      新しいチャット
    </Button>
  );
};

export default NewChatButton;