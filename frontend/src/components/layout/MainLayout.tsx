// src/components/layout/MainLayout.tsx
import React, { useState, useEffect } from 'react';
import { Box, Grid, Divider, useTheme, useMediaQuery } from '@mui/material';
import TaskTable from '../tasks/TaskTable';
import FileTable from '../files/FileTable';
import HistoryList from '../chat/HistoryList';
import ChatDisplay from '../chat/ChatDisplay';
import ChatInput from '../chat/ChatInput';
import NewChatButton from '../chat/NewChatButton';

const MainLayout: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  // State to control resizable split (simulating QSplitter)
  const [leftPanelWidth, setLeftPanelWidth] = useState<number>(25); // percentage
  const [leftPanelVisible, setLeftPanelVisible] = useState<boolean>(true);
  
  // Handle resize - would need a custom implementation for draggable splitter
  const handleResize = (newWidth: number) => {
    if (newWidth >= 15 && newWidth <= 40) {
      setLeftPanelWidth(newWidth);
    }
  };

  // For mobile view, toggle between panels
  const togglePanel = () => {
    setLeftPanelVisible(!leftPanelVisible);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', flexGrow: 1, overflow: 'hidden' }}>
        {/* Left Panel - matches the left side of the desktop app */}
        <Box 
          sx={{ 
            width: isMobile ? '100%' : `${leftPanelWidth}%`, 
            display: isMobile ? (leftPanelVisible ? 'block' : 'none') : 'block',
            height: '100%',
            overflow: 'auto',
            borderRight: '1px solid rgba(0, 0, 0, 0.12)'
          }}
        >
          <Box sx={{ p: 2 }}>
            <TaskTable />
          </Box>
          <Divider />
          <Box sx={{ p: 2 }}>
            <FileTable />
          </Box>
          <Divider />
          <Box sx={{ p: 2 }}>
            <HistoryList />
          </Box>
        </Box>

        {/* Resizable Divider - would need custom drag implementation */}
        {!isMobile && (
          <Box 
            sx={{ 
              width: '5px', 
              backgroundColor: 'rgba(0, 0, 0, 0.08)',
              cursor: 'col-resize',
              '&:hover': {
                backgroundColor: 'primary.main'
              }
            }}
            // This is simplified - a real implementation would need mouse events
            onClick={() => handleResize(leftPanelWidth === 25 ? 35 : 25)}
          />
        )}

        {/* Right Panel - matches the right side of the desktop app */}
        <Box 
          sx={{ 
            width: isMobile ? '100%' : `${100 - leftPanelWidth}%`, 
            display: isMobile ? (!leftPanelVisible ? 'block' : 'none') : 'block',
            height: '100%',
            
            flexDirection: 'column'
          }}
        >
          <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
            <ChatDisplay />
          </Box>
          <Box sx={{ p: 2, borderTop: '1px solid rgba(0, 0, 0, 0.12)' }}>
            <ChatInput />
            <Box sx={{ mt: 2 }}>
              <NewChatButton />
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default MainLayout;