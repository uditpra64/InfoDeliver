import React, { useEffect, useRef } from 'react';
import { Box, Typography, Paper } from '@mui/material';
import { useAppSelector } from '../../store/hooks/reduxHooks';
import ChatBubble from './ChatBubble';

const ChatDisplay: React.FC = () => {
  const { messages, loading } = useAppSelector(state => state.chat);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'auto',
        padding: 2,
        backgroundColor: '#f5f5f5',
      }}
    >
      {messages.map((message, index) => (
        <ChatBubble 
          key={`${message.role}-${index}`}
          message={message.content}
          isUser={message.role === 'user'}
          isHtml={message.content.includes('class="dataframe">')}
        />
      ))}
      {loading && (
        <ChatBubble 
          message="生成中...."
          isUser={false}
          isHtml={false}
        />
      )}
      <div ref={messagesEndRef} />
    </Box>
  );
};

export default ChatDisplay;
