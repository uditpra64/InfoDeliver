
import React, { useEffect, useRef } from 'react';
import { Box } from '@mui/material';
import { useAppSelector } from '../../store/hooks/reduxHooks';
import ChatBubble from './ChatBubble';
import { Message } from '../../types';

const ChatDisplay: React.FC = () => {
  // Explicitly type the messages to satisfy TypeScript
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
      {/* Render each message */}
      {messages.map((message, index) => {
        // Handle is_html property safely
        const isHtml = 'is_html' in message 
          ? Boolean(message.is_html) 
          : message.content.includes('class="dataframe">');
        
        return (
          <ChatBubble 
            key={`${message.role}-${index}`}
            message={message.content}
            isUser={message.role === 'user'}
            isHtml={isHtml}
          />
        );
      })}
      
      {/* Loading indicator */}
      {loading && (
        <ChatBubble 
          message="生成中...."
          isUser={false}
          isHtml={false}
        />
      )}
      
      {/* Reference element for scrolling */}
      <div ref={messagesEndRef} />
    </Box>
  );
};

export default ChatDisplay;