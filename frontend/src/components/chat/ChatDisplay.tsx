import React, { useEffect, useRef } from 'react';
import { Box } from '@mui/material';
import { useAppSelector } from '../../store/hooks/reduxHooks';
import ChatBubble from './ChatBubble';
import { Message } from '../../../types';

const ChatDisplay: React.FC = () => {
  const { messages, loading } = useAppSelector(state => state.chat);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Debug logging to help troubleshoot message display issues
  useEffect(() => {
    console.log('Current messages in store:', messages);
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
      {messages.map((message, index) => (
        <ChatBubble 
          key={`${message.role}-${index}`}
          message={message.content}
          isUser={message.role === 'user'}
          // Use type assertion to fix the error
          isHtml={(message as any).is_html || message.content.includes('class="dataframe">')}
      />
      ))}
      
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