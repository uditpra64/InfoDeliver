import React from 'react';
import { Container, Box, Typography, Button, Paper } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import LockIcon from '@mui/icons-material/Lock';

const UnauthorizedPage: React.FC = () => {
  const navigate = useNavigate();
  
  const handleGoBack = () => {
    navigate('/');
  };

  return (
    <Container maxWidth="md">
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
        }}
      >
        <Paper elevation={3} sx={{ p: 4, width: '100%', borderRadius: 2, textAlign: 'center' }}>
          <LockIcon color="error" sx={{ fontSize: 60, mb: 2 }} />
          <Typography variant="h4" component="h1" gutterBottom>
            アクセス権限がありません
          </Typography>
          <Typography variant="body1" paragraph>
            このページにアクセスするための権限がありません。
            必要な権限がある場合は、管理者にお問い合わせください。
          </Typography>
          <Button
            variant="contained"
            color="primary"
            onClick={handleGoBack}
            sx={{ mt: 2 }}
          >
            ホームに戻る
          </Button>
        </Paper>
      </Box>
    </Container>
  );
};

export default UnauthorizedPage;