import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

# Import the user database interface
from application.services.security.user_db import get_user_db, UserInDB

# Configuration from environment variables
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Initialize OAuth2 with token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Models
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime

class TokenData(BaseModel):
    username: Optional[str] = None
    scopes: List[str] = []

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    scopes: List[str] = []

# Security functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that the password matches the hash"""
    return get_user_db().verify_password(plain_password, hashed_password)

def get_user(username: str) -> Optional[UserInDB]:
    """Get user from database"""
    return get_user_db().get_user(username)

def authenticate_user(username: str, password: str) -> Union[UserInDB, bool]:
    """Authenticate user with username and password"""
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get current user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
            
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(username=username, scopes=token_scopes)
    except JWTError:
        raise credentials_exception
        
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    
    # Convert UserInDB to User model (strip out the hashed_password)
    return User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        disabled=user.disabled,
        scopes=user.scopes
    )

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Verify that the current user is active"""
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

def check_scopes(required_scopes: List[str]):
    """Check that the user has the required scopes"""
    async def scope_checker(current_user: User = Depends(get_current_user)):
        for scope in required_scopes:
            if scope not in current_user.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not enough permissions. Required scope: {scope}"
                )
        return current_user
    return scope_checker

# Security middleware functions remain unchanged

# This function sets up all security for a FastAPI app
def setup_api_security(app, allowed_origins: List[str]):
    """Set up security with documentation access"""
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse
    
    # Setup CORS with enhanced configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Added OPTIONS
        allow_headers=[
            "X-Session-ID", 
            "Content-Type", 
            "Authorization",
            "Access-Control-Allow-Headers",
            "Access-Control-Allow-Origin",
            "X-Requested-With",
            "X-CSRF-Token"
        ],  # Enhanced headers
        expose_headers=["X-Total-Count"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )
    
    # Ensure OpenAPI docs are accessible
    app.openapi_url = "/openapi.json"
    
    # Add security middleware with exceptions for docs
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # Allow documentation endpoints without security checks
        if request.url.path in ["/docs", "/redoc", "/openapi.json", "/token"]:
            return await call_next(request)
        
        # For OPTIONS requests, allow without additional processing
        if request.method == "OPTIONS":
            response = await call_next(request)
            return response
            
        # Add security headers for other endpoints
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response
    
    return app