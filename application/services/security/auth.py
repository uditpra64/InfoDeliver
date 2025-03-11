import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Configuration from environment variables
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Initialize password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

class UserInDB(User):
    hashed_password: str

# Sample user database - in production, replace with a real database
fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "Administrator",
        "email": "admin@example.com",
        "hashed_password": pwd_context.hash(os.getenv("ADMIN_PASSWORD", "password")),
        "disabled": False,
        "scopes": ["admin", "read", "write"]
    },
    "user": {
        "username": "user",
        "full_name": "Regular User",
        "email": "user@example.com",
        "hashed_password": pwd_context.hash(os.getenv("USER_PASSWORD", "password")),
        "disabled": False,
        "scopes": ["read"]
    }
}

# Security functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that the password matches the hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

def get_user(db: Dict[str, Dict[str, Any]], username: str) -> Optional[UserInDB]:
    """Get user from database"""
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(db: Dict[str, Dict[str, Any]], username: str, password: str) -> Union[UserInDB, bool]:
    """Authenticate user with username and password"""
    user = get_user(db, username)
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
        
    user = get_user(fake_users_db, token_data.username)
    if user is None:
        raise credentials_exception
        
    return user

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

# Rate limiting class
class RateLimiter:
    """Simple in-memory rate limiter"""
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.request_history: Dict[str, List[datetime]] = {}
    
    def is_rate_limited(self, client_id: str) -> bool:
        """Check if a client is rate limited"""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean up old requests
        if client_id in self.request_history:
            self.request_history[client_id] = [
                timestamp for timestamp in self.request_history[client_id]
                if timestamp > minute_ago
            ]
        else:
            self.request_history[client_id] = []
        
        # Check rate limit
        if len(self.request_history[client_id]) >= self.requests_per_minute:
            return True
        
        # Record request
        self.request_history[client_id].append(now)
        return False

# Initialize rate limiter
rate_limiter = RateLimiter()

# Rate limit middleware
async def rate_limit_middleware(request: Request, call_next):
    """Middleware to rate limit requests"""
    client_id = request.client.host
    
    # Check if client is rate limited
    if rate_limiter.is_rate_limited(client_id):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded"},
        )
    
    # Process request normally
    response = await call_next(request)
    return response

# Request logging middleware
async def logging_middleware(request: Request, call_next):
    """Middleware to log all API requests"""
    start_time = datetime.utcnow()
    
    # Get request details
    method = request.method
    url = str(request.url)
    client = request.client.host if request.client else "unknown"
    
    # Process request
    response = await call_next(request)
    
    # Calculate request duration
    duration = (datetime.utcnow() - start_time).total_seconds()
    
    # Log request
    logger.info(
        f"Request: {method} {url} from {client} - "
        f"Status: {response.status_code} - Duration: {duration:.3f}s"
    )
    
    return response

# Helper for CORS configuration with improved security
def setup_cors(app, allowed_origins: List[str]):
    """Set up CORS with security best practices"""
    from fastapi.middleware.cors import CORSMiddleware
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["X-Session-ID", "Content-Type", "Authorization"],
        expose_headers=["X-Total-Count"],
        max_age=86400,  # Caching CORS preflight requests for 1 day
    )

# Security headers middleware
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    
    return response

# Import missing dependencies
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Example of adding to FastAPI
def setup_api_security(app, allowed_origins: List[str]):
    """Set up security with docs access"""
    from fastapi.middleware.cors import CORSMiddleware
    
    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["X-Session-ID", "Content-Type", "Authorization"],
        expose_headers=["X-Total-Count"],
    )
    
    # Ensure OpenAPI docs are accessible
    # Make sure not to add security requirements to docs endpoints
    app.openapi_url = "/openapi.json"
    
    # Add token endpoint with implementation directly inside to avoid recursion
    @app.post("/token", response_model=Token)
    async def login_endpoint(form_data: OAuth2PasswordRequestForm = Depends()):
        """Token endpoint for OAuth2 authentication"""
        user = authenticate_user(fake_users_db, form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Check if the user has requested scopes
        token_scopes = []
        for scope in form_data.scopes or []:  # Handle empty scopes
            if scope in user.scopes:
                token_scopes.append(scope)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"The scope {scope} is not available for this user",
                )
        
        # If no scopes requested, grant all user scopes
        if not token_scopes:
            token_scopes = user.scopes
        
        access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        expires_at = datetime.utcnow() + access_token_expires
        
        access_token = create_access_token(
            data={"sub": user.username, "scopes": token_scopes},
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token, 
            token_type="bearer",
            expires_at=expires_at
        )
    
    # Add middleware with exceptions for docs
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # Allow documentation endpoints without security checks
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
            
        # Add security headers for other endpoints
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # Add other security headers...
        
        return response
        
    # Log that security is configured
    logger.info("API security configured")
    
    return app