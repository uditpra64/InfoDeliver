import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { CircularProgress, Box } from '@mui/material';
import { useAppSelector, useAppDispatch } from '../../store/hooks/reduxHooks';
import { createSession } from '../../store/slices/sessionSlice';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredScopes?: string[];
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requiredScopes = [] 
}) => {
  const { isAuthenticated, user, loading: authLoading } = useAppSelector(state => state.auth);
  const { 
    currentSessionId, 
    loading: sessionLoading, 
    sessionCreationInProgress 
  } = useAppSelector(state => state.session);
  const location = useLocation();
  const dispatch = useAppDispatch();
  const [sessionInitialized, setSessionInitialized] = useState(false);

  useEffect(() => {
    // Only try to create a session once if authenticated and no session exists
    if (isAuthenticated && !currentSessionId && !sessionCreationInProgress && !sessionInitialized) {
      console.log('Creating new session for authenticated user');
      setSessionInitialized(true);
      dispatch(createSession());
    }
  }, [isAuthenticated, currentSessionId, sessionCreationInProgress, sessionInitialized, dispatch]);

  // Show loading while authentication is in progress
  if (authLoading || (isAuthenticated && !currentSessionId && sessionLoading)) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // If not authenticated, redirect to login
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check for required scopes
  if (requiredScopes.length > 0) {
    const hasRequiredScopes = requiredScopes.every(scope => 
      user?.scopes.includes(scope)
    );

    if (!hasRequiredScopes) {
      // Redirect to unauthorized page
      return <Navigate to="/unauthorized" replace />;
    }
  }

  // Render children if authenticated and has required scopes
  return <>{children}</>;
};

export default ProtectedRoute;