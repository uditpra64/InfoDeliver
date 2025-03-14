// src/components/chat/ChatBubble.tsx
import React from 'react';
import { Box, Paper, Typography, Avatar } from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import SmartToyIcon from '@mui/icons-material/SmartToy';

interface ChatBubbleProps {
  message: string;
  isUser: boolean;
  isHtml: boolean;
}

const ChatBubble: React.FC<ChatBubbleProps> = ({ message, isUser, isHtml }) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'row',
        mb: 2,
        justifyContent: isUser ? 'flex-end' : 'flex-start',
      }}
    >
      {!isUser && (
        <Avatar sx={{ mr: 1, bgcolor: isUser ? 'primary.main' : 'secondary.main' }}>
          <SmartToyIcon />
        </Avatar>
      )}
      
      <Paper
        elevation={1}
        sx={{
          p: 2,
          maxWidth: '80%',
          borderRadius: 2,
          backgroundColor: isUser ? '#e5e5ea' : '#c4c4c4',
        }}
      >
        {isHtml ? (
          <Box
            sx={{ maxWidth: '100%', overflow: 'auto' }}
            dangerouslySetInnerHTML={{ 
              __html: 
                `<style>
                  .dataframe {
                    font-family: Arial, sans-serif;
                    border-collapse: collapse;
                    width: 100%;
                  }
                  .dataframe th, .dataframe td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                  }
                  .dataframe th {
                    background-color: #f2f2f2;
                    font-weight: bold;
                  }
                  .dataframe tr:nth-child(even) {
                    background-color: #f9f9f9;
                  }
                  .dataframe tr:hover {
                    background-color: #f1f1f1;
                  }
                </style>` + message 
            }}
          />
        ) : (
          <Typography
            variant="body1"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {message}
          </Typography>
        )}
      </Paper>
      
      {isUser && (
        <Avatar sx={{ ml: 1, bgcolor: 'primary.main' }}>
          <PersonIcon />
        </Avatar>
      )}
    </Box>
  );
};

export default ChatBubble;