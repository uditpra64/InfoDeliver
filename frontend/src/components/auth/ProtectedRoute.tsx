import React, { useEffect } from 'react';
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
  const { isAuthenticated, user, loading } = useAppSelector(state => state.auth);
  const { currentSessionId, loading: sessionLoading } = useAppSelector(state => state.session);
  const location = useLocation();
  const dispatch = useAppDispatch();

  useEffect(() => {
    // If authenticated but no session, create one
    if (isAuthenticated && !currentSessionId && !sessionLoading) {
      dispatch(createSession());
    }
  }, [isAuthenticated, currentSessionId, sessionLoading, dispatch]);

  // Show loading while authentication is in progress
  if (loading || (isAuthenticated && !currentSessionId && sessionLoading)) {
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
      // Redirect to unauthorized page or home
      return <Navigate to="/unauthorized" replace />;
    }
  }

  // Render children if authenticated and has required scopes
  return <>{children}</>;
};

export default ProtectedRoute;