import os
import sys
import tempfile
import logging
import shutil
import time
import uuid
import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Generic, TypeVar
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header, Request, BackgroundTasks, status
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, validator, Field
from pydantic.generics import GenericModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from dotenv import load_dotenv

# Import auth components
from application.services.security.auth import (
    setup_api_security, 
    get_current_active_user, 
    check_scopes,
    authenticate_user,
    create_access_token,
    User,
    Token,
    TokenData
)

# Import from user_db for cleaner authentication
from application.services.security.user_db import get_user_db

# Import frontend adapter for consistent responses
from application.services.frontend_adapter import frontend_adapter

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("payroll_api")

# Get the parent directory to import setup_paths
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Import setup_paths to configure everything correctly
import setup_paths

# Define app_dir AFTER importing setup_paths
app_dir = os.path.join(parent_dir, "application")

# Now import service classes with error handling
try:
    from application.services.payroll_service import PayrollService
    from application.services.file_service import FileService
    from application.services.session_service import SessionService
    logger.info("Service modules imported successfully")
except ImportError as e:
    logger.critical(f"Failed to import service modules: {e}")
    raise

# Load environment variables
load_dotenv()

# Define a type variable for generic response data
T = TypeVar('T')

# Create a standard response model that can wrap any data type
class StandardResponse(GenericModel, Generic[T]):
    code: int = 200
    success: bool = True
    message: str
    data: Optional[T] = None

# Custom exceptions for more specific error handling
class PayrollAPIException(Exception):
    """Base exception for Payroll API errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class ValidationError(PayrollAPIException):
    """Exception for input validation errors."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

class ResourceNotFoundError(PayrollAPIException):
    """Exception for requested resources not found."""
    def __init__(self, message: str):
        super().__init__(message, status_code=404)

class AuthenticationError(PayrollAPIException):
    """Exception for authentication failures."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)

# Models for requests and responses
class SessionState(str, Enum):
    INIT = "init"
    CHAT = "chat"
    FILE = "file"
    TASK = "task"
    DATE = "date"

class FileType(str, Enum):
    CSV = "csv"
    EXCEL = "excel"

# Request and response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime

class UserResponse(BaseModel):
    username: str
    scopes: List[str]

class ChatResponse(BaseModel):
    response: str
    session_id: str
    state: SessionState
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_html: bool = False
    
    class Config:
        use_enum_values = True

class FileUploadResponse(BaseModel):
    success: bool
    file_id: Optional[int] = None
    message: str
    file_details: Optional[Dict[str, Any]] = None
    session_id: str
    state: SessionState

class FileInfo(BaseModel):
    id: int
    name: str
    task_name: str
    upload_date: str
    row_count: int
    output: bool

class TaskResponse(BaseModel):
    task_id: str
    name: str
    description: str
    required_files: List[Dict[str, Any]]
    status: str

class SessionHistoryItem(BaseModel):
    role: str
    content: str
    timestamp: str

class SessionHistoryResponse(BaseModel):
    session_id: str
    history: List[SessionHistoryItem]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

# JWT Configuration from environment variables
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="Payroll Assistant API",
    description="API for payroll processing with natural language capabilities",
    version="1.0.0",
)

# Setup API security with CORS
allowed_origins = [
    "http://localhost:3000",  # React app on local dev
    "http://127.0.0.1:3000",  # Alternative local address
    os.getenv("FRONTEND_URL", "")  # Production frontend URL from env
]
# Remove empty strings from allowed_origins
allowed_origins = [origin for origin in allowed_origins if origin]
# Apply security configuration
setup_api_security(app, allowed_origins=allowed_origins)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Handle rate limit exceptions
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    error_response = frontend_adapter.adapt_error_response(
        error_message="Rate limit exceeded",
        status_code=HTTP_429_TOO_MANY_REQUESTS
    )
    
    return JSONResponse(
        status_code=HTTP_429_TOO_MANY_REQUESTS,
        content=StandardResponse(
            code=HTTP_429_TOO_MANY_REQUESTS,
            success=False,
            message=error_response["message"],
            data={"detail": "Too many requests"}
        ).dict(),
    )

# Custom exception handler for PayrollAPIException
@app.exception_handler(PayrollAPIException)
async def payroll_exception_handler(request: Request, exc: PayrollAPIException):
    error_response = frontend_adapter.adapt_error_response(
        error_message=exc.message,
        status_code=exc.status_code
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=StandardResponse(
            code=exc.status_code,
            success=False,
            message=error_response["message"],
            data=None
        ).dict(),
    )

# Handle other HTTP exceptions
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    error_response = frontend_adapter.adapt_error_response(
        error_message=str(exc.detail),
        status_code=exc.status_code
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=StandardResponse(
            code=exc.status_code,
            success=False,
            message=error_response["message"],
            data=None
        ).dict(),
    )

# Load configuration from environment variables with fallbacks
config_path = os.getenv("CONFIG_PATH", os.path.join(app_dir, "json", "config.json"))
session_expiry_hours = int(os.getenv("SESSION_EXPIRY_HOURS", "24"))
max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
upload_folder = os.getenv("UPLOAD_FOLDER", os.path.join(current_dir, "uploads"))

# Create upload folder if it doesn't exist
os.makedirs(upload_folder, exist_ok=True)

# Initialize services with error handling
try:
    file_service = FileService(temp_dir=upload_folder)
    logger.info("FileService initialized successfully")
    
    payroll_service = PayrollService(config_path=config_path)
    logger.info("PayrollService initialized successfully")
    
    session_dir = os.getenv("SESSION_DIR", os.path.join(current_dir, "sessions"))
    session_service = SessionService(session_dir=session_dir, max_lifetime_hours=session_expiry_hours)
    logger.info("SessionService initialized successfully")
except Exception as e:
    logger.critical(f"Error initializing services: {e}")
    raise

# Initialize authentication
def initialize_auth():
    """Initialize authentication components"""
    logger.info("Initializing authentication")
    # Verify JWT secret key is properly set
    if JWT_SECRET_KEY == secrets.token_hex(32):
        logger.warning("Using a randomly generated JWT secret key. This will change on restart!")
    
    # In a production environment, you'd verify connection to your user database here
    user_db = get_user_db()
    logger.info(f"User authentication initialized with {len(user_db.users)} users")
    
    return True

# Startup events
@app.on_event("startup")
def startup_event():

    user_db = get_user_db()
    logger.info(f"User database path: {user_db.db_path}")
    logger.info(f"Users in database: {list(user_db.users.keys())}")
    logger.info(f"Admin password from env: {os.getenv('ADMIN_PASSWORD')}")
    # Clean up expired sessions
    try:
        expired_sessions = session_service.cleanup_old_sessions(max_age_seconds=session_expiry_hours * 3600)
        logger.info(f"Startup: cleaned up {expired_sessions} sessions older than {session_expiry_hours} hours")
    except Exception as e:
        logger.error(f"Error cleaning up expired sessions: {e}")
    
    # Clean up temporary files
    try:
        cleanup_temp_files()
        logger.info("Startup: cleaned up temporary files")
    except Exception as e:
        logger.error(f"Error cleaning up temporary files: {e}")
    
    # Initialize authentication
    try:
        initialize_auth()
        logger.info("Authentication initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing authentication: {e}")

# Shutdown events
@app.on_event("shutdown")
def shutdown_event():
    logger.info("API shutting down")
    cleanup_temp_files()

# Helper function to clean up temporary files
def cleanup_temp_files():
    """Clean up temporary files older than 24 hours"""
    try:
        temp_dir = upload_folder
        current_time = time.time()
        file_count = 0
        
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                # If file is older than 24 hours, delete it
                if current_time - os.path.getmtime(file_path) > 86400:  # 24 hours in seconds
                    try:
                        os.remove(file_path)
                        file_count += 1
                    except PermissionError:
                        logger.warning(f"Cannot remove file {file_path} - permission denied")
                    except Exception as e:
                        logger.warning(f"Error removing file {file_path}: {e}")
        
        logger.info(f"Deleted {file_count} old temporary files")
    except Exception as e:
        logger.error(f"Error cleaning up temp files: {e}")

# Helper function to get or create session
async def get_session(x_session_id: Optional[str] = Header(None)) -> str:
    """Get or create a session"""
    if not x_session_id:
        # Create new session if none provided
        new_session_id = session_service.create_session()
        logger.info(f"Created new session: {new_session_id}")
        return new_session_id
    
    # Check if session exists
    session = session_service.get_session(x_session_id)
    if not session:
        # Create new session if provided ID is invalid
        new_session_id = session_service.create_session()
        logger.info(f"Invalid session ID provided, created new session: {new_session_id}")
        return new_session_id
    
    return x_session_id

# Helper function to validate and save uploaded file
async def save_upload_file(
    upload_file: UploadFile, 
    background_tasks: BackgroundTasks,
    file_type: Optional[str] = None
) -> str:
    """Validate and save an uploaded file, returning the file path"""
    # Generate secure filename to prevent path traversal
    filename = upload_file.filename
    if not filename:
        raise ValidationError("Filename is required")
    
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Validate file type based on extension
    valid_extensions = {
        "csv": [".csv"],
        "excel": [".xlsx", ".xls"]
    }
    
    if file_type and file_type in valid_extensions:
        if file_ext not in valid_extensions[file_type]:
            raise ValidationError(f"Expected {file_type} file but got {file_ext}")
    elif file_ext not in ['.csv', '.xlsx', '.xls']:
        raise ValidationError("Only CSV and Excel files are supported")
    
    secure_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_folder, secure_filename)
    
    # Stream file to disk efficiently
    try:
        with open(file_path, "wb") as buffer:
            # Read and write in chunks to handle large files
            chunk_size = 1024 * 1024  # 1MB chunks
            total_size = 0
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                
                # Check file size limit
                if total_size > max_upload_size_mb * 1024 * 1024:
                    # Remove partial file
                    os.unlink(file_path)
                    raise ValidationError(f"File too large (max {max_upload_size_mb}MB)")
                    
                buffer.write(chunk)
    except Exception as e:
        # Ensure file is cleaned up if something goes wrong
        if os.path.exists(file_path):
            os.unlink(file_path)
        raise ValidationError(f"Error saving file: {str(e)}")
    
    # Schedule cleanup after 24 hours
    def cleanup_file():
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {str(e)}")
    
    background_tasks.add_task(cleanup_file)
    
    return file_path

# Authentication endpoint
@app.post("/token", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return JWT token"""

    logger.debug(f"Login attempt: username={form_data.username}, password=***")
    
    # Verify the user database
    logger.info(f"User database path: {get_user_db().db_path}")
    logger.info(f"Users in database: {list(get_user_db().users.keys())}")
    
    # Authenticate the user
    user = authenticate_user(form_data.username, form_data.password)
    logger.debug(f"Authentication result: {user is not False}")
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check requested scopes against user's available scopes
    token_scopes = []
    for scope in form_data.scopes or []:
        if scope in user.scopes:
            token_scopes.append(scope)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The scope {scope} is not available for this user",
            )
    
    # Default to all user scopes if none requested
    if not token_scopes:
        token_scopes = user.scopes
    
    # Create token with expiration time
    access_token_expires = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.utcnow() + access_token_expires
    
    access_token = create_access_token(
        data={"sub": user.username, "scopes": token_scopes},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token, 
        token_type="bearer",
        expires_at=expires_at
    )

# Health check endpoint (public)
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return StandardResponse(
        code=200,
        success=True,
        message="API is operational",
        data={"status": "ok", "timestamp": datetime.now().isoformat()}
    )

# API endpoints with authentication
@app.post("/chat", response_model=StandardResponse[ChatResponse])
@limiter.limit("30/minute")
async def chat_endpoint(
    request: Request,
    chat_request: ChatRequest, 
    current_user: User = Depends(get_current_active_user),
    session_id: str = Depends(get_session)
):
    """Process a chat message and return a response"""
    logger.info(f"Processing chat message for user {current_user.username}, session {session_id}: {chat_request.message}")
    
    try:
        # Add message to conversation history
        session_service.add_to_conversation(session_id, "user", chat_request.message)
        
        # Process the message
        result = payroll_service.process_message(chat_request.message)
        
        # Handle different return types from process_message
        response_text = ""
        extra_info = ""
        
        if isinstance(result, tuple) and len(result) >= 1:
            response_text = result[0]
            if len(result) >= 2:
                extra_info = result[1]
        else:
            response_text = result
        
        # Convert list responses to string
        if isinstance(response_text, list):
            response_text = "\n".join(map(str, response_text))
        
        # Add assistant response to conversation
        session_service.add_to_conversation(session_id, "assistant", response_text)
        
        # Update session state
        current_state = payroll_service.get_current_state()
        session_service.update_session(session_id, {"current_state": current_state})
        
        # Map state to enum
        try:
            state_enum = SessionState(current_state)
        except ValueError:
            state_enum = SessionState.CHAT  # Default to CHAT if unknown state
        
        # Detect if response contains HTML
        is_html = 'class="dataframe">' in response_text
        
        # Create response object
        chat_response = ChatResponse(
            response=response_text,
            session_id=session_id,
            state=state_enum,
            timestamp=datetime.now().isoformat(),
            is_html=is_html
        )
        
        return StandardResponse(
            code=200,
            success=True,
            message="Successfully processed chat message",
            data=chat_response
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        logger.exception("Detailed traceback:")
        
        if isinstance(e, HTTPException):
            raise
            
        if isinstance(e, PayrollAPIException):
            raise
            
        raise PayrollAPIException(f"Chat processing error: {str(e)}")

@app.post("/upload", response_model=StandardResponse[FileUploadResponse])
@limiter.limit("10/minute")
async def upload_file_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    file_type: Optional[str] = Form(None),  # Make file_type optional
    task_name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    session_id: str = Depends(get_session)
):
    """Upload a file for processing"""
    logger.info(f"File upload request from user {current_user.username}, session {session_id}: {file.filename}")
    
    # Determine file type from file extension if not provided
    if not file_type:
        ext = os.path.splitext(file.filename)[1].lower()
        file_type = "csv" if ext == ".csv" else "excel" if ext in [".xlsx", ".xls"] else None
        
    if not file_type:
        raise ValidationError("Could not determine file type. Please specify file_type parameter.")
    
    try:
        # Save file with improved error handling
        try:
            file_path = await save_upload_file(file, background_tasks, file_type)
            logger.debug(f"File saved to: {file_path}")
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            raise ValidationError(f"Could not save uploaded file: {str(e)}")
            
        # Enhanced file processing - ensure proper database storage
        try:
            # Read the file as a DataFrame
            df = None
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            else:
                raise ValidationError("Unsupported file format")
                
            # Check if DataFrame was loaded correctly
            if df is None or df.empty:
                raise ValidationError("Failed to read file data or file is empty")
                
            logger.info(f"Successfully read file with {len(df)} rows")
                
            # Store file directly in database
            file_id = file_service.file_agent.store_csv_file(
                df=df,
                file_name=f"uploaded_{uuid.uuid4()}",
                file_path=file_path,
                original_name=file.filename,
                definition=f"Uploaded {file_type.upper()} file",
                task_name=task_name or "Manual Upload",
                output=False
            )
            
            if not file_id:
                raise ValidationError("File was processed but could not be stored in database")
                
            logger.info(f"File successfully stored in database with ID: {file_id}")
            
            # Create response with file details
            upload_result = {
                "success": True,
                "file_id": file_id,
                "message": "File uploaded and stored successfully",
                "identity_result": f"Uploaded {file_type.upper()} file"
            }
            
        except Exception as db_error:
            logger.error(f"Error storing file in database: {str(db_error)}")
            logger.exception("Detailed traceback:")
            raise PayrollAPIException(f"Error storing file in database: {str(db_error)}")
            
        # Construct message for payroll service
        message = f"選択されたファイル: {file_path}"
        
        try:
            result, extra_info = payroll_service.process_message(message)
            logger.debug(f"Payroll service processed message: {result}")
        except Exception as e:
            logger.error(f"Error in payroll service: {str(e)}")
            logger.exception("Detailed traceback:")
            # Continue even if payroll service has an issue, since we've already stored the file
            result = "File was uploaded and stored, but could not be processed by the payroll service."
            extra_info = ""
            
        # Update session state
        current_state = payroll_service.get_current_state()
        session_service.update_session(session_id, {"current_state": current_state})
        
        # Map state to enum
        try:
            state_enum = SessionState(current_state)
        except ValueError:
            state_enum = SessionState.FILE  # Default to FILE if unknown state
            
        # Add system message to conversation
        response_text = result if isinstance(result, str) else "\n".join(result) if isinstance(result, list) else str(result)
        session_service.add_to_conversation(session_id, "system", f"File uploaded: {file.filename}")
        session_service.add_to_conversation(session_id, "assistant", response_text)
        
        logger.info(f"File uploaded successfully: {file.filename} with {len(df)} rows")
        
        # Format response using the adapter
        file_details = {
            "id": upload_result.get("file_id", 0),
            "name": file.filename,
            "file_type": file_type,
            "task_name": task_name or "Manual Upload",
            "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "row_count": len(df) if df is not None else 0,
            "output": False,
            "identity_result": upload_result.get("identity_result", "")
        }
        
        adapted_file_details = frontend_adapter.adapt_file_info(file_details)
        
        upload_response = FileUploadResponse(
            success=True,
            file_id=upload_result.get("file_id"),
            message=f"File uploaded successfully with {len(df)} rows",
            file_details=adapted_file_details,
            session_id=session_id,
            state=state_enum
        )
        
        return StandardResponse(
            code=200,
            success=True,
            message="File uploaded successfully",
            data=upload_response
        )
        
    except ValidationError as e:
        logger.error(f"Validation error in file upload: {str(e)}")
        raise
    except PayrollAPIException as e:
        logger.error(f"PayrollAPIException in file upload: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in file upload: {str(e)}")
        logger.exception("Detailed traceback:")
        raise PayrollAPIException(f"File upload error: {str(e)}")
        
@app.get("/files", response_model=StandardResponse[List[FileInfo]])
@limiter.limit("60/minute")
async def get_files(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session_id: str = Depends(get_session)
):
    """Get list of uploaded files"""
    logger.info(f"Files list requested by user {current_user.username} for session {session_id}")
    try:
        files = file_service.get_file_list()
        logger.debug(f"Raw files from file_service: {files}")
        
        # Ensure each file has all required fields
        processed_files = []
        for file in files:
            # Ensure minimum fields exist
            processed_file = {
                "id": file.get("id", 0),
                "name": file.get("name", "Unknown File"),
                "task_name": file.get("task_name", ""),
                "upload_date": file.get("upload_date", datetime.now().isoformat()),
                "row_count": file.get("row_count", 0),
                "output": file.get("output", False)
            }
            processed_files.append(processed_file)
        
        # Adapt the file information for frontend
        adapted_files = [frontend_adapter.adapt_file_info(file) for file in processed_files]
        logger.debug(f"Adapted files for frontend: {adapted_files}")
        
        return StandardResponse(
            code=200,
            success=True,
            message="Files retrieved successfully",
            data=adapted_files
        )
    except Exception as e:
        logger.error(f"Error getting files: {str(e)}")
        logger.exception("Detailed traceback:")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error retrieving files: {str(e)}")

@app.get("/tasks", response_model=StandardResponse[List[TaskResponse]])
@limiter.limit("60/minute")
async def get_tasks(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session_id: str = Depends(get_session)
):
    """Get a list of available tasks"""
    logger.info(f"Task list requested by user {current_user.username} for session {session_id}")
    try:
        tasks = payroll_service.get_task_list()
        result = []
        
        for task_name in tasks:
            description = payroll_service.get_task_description(task_name)
            # Get required files (empty list for now, needs implementation in PayrollService)
            required_files = []  
            
            result.append(TaskResponse(
                task_id=task_name,
                name=task_name,
                description=description,
                required_files=required_files,
                status="available"
            ))
        
        # Adapt tasks for frontend
        adapted_tasks = frontend_adapter.adapt_task_list(result)
        
        return StandardResponse(
            code=200,
            success=True,
            message="Tasks retrieved successfully",
            data=adapted_tasks
        )
    except Exception as e:
        logger.error(f"Error getting tasks: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error retrieving tasks: {str(e)}")

@app.post("/tasks/{task_id}/select", response_model=StandardResponse[Dict[str, Any]])
@limiter.limit("20/minute")
async def select_task(
    request: Request,
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    session_id: str = Depends(get_session)
):
    """Select a task for processing"""
    logger.info(f"Task selection request from user {current_user.username} for session {session_id}: {task_id}")
    try:
        # Select the task
        success = payroll_service.select_task(task_id)
        
        if not success:
            raise ResourceNotFoundError(f"Task {task_id} not found")
        
        # Update session state
        session_service.update_session(session_id, {"current_state": "file", "current_task": task_id})
        
        # Add message to conversation
        session_service.add_to_conversation(
            session_id, 
            "system", 
            f"Task selected: {task_id}"
        )
        
        # Process files (get needed files for the task)
        files_response, extra_info = payroll_service.process_files()
        
        # Add assistant response to conversation
        if isinstance(files_response, list):
            for msg in files_response:
                session_service.add_to_conversation(session_id, "assistant", msg)
            
            # Only the last message will be returned in the response
            files_message = files_response[-1] if files_response else ""
        else:
            files_message = files_response
            session_service.add_to_conversation(session_id, "assistant", files_message)
        
        return StandardResponse(
            code=200,
            success=True,
            message=f"Task {task_id} selected successfully",
            data={
                "task_id": task_id, 
                "session_id": session_id,
                "state": "file",
                "files_message": files_message
            }
        )
    except Exception as e:
        logger.error(f"Error selecting task: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error selecting task: {str(e)}")

@app.get("/session/history", response_model=StandardResponse[List[Dict[str, Any]]])
@limiter.limit("20/minute")
async def get_session_history(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session_id: str = Depends(get_session)
):
    """Get list of session history"""
    logger.info(f"Session history list requested by user {current_user.username} for session {session_id}")
    try:
        # Get all session IDs for this user (implementation needed)
        # For demo purposes, return sample data including current session
        history = [
            {
                "id": session_id,
                "title": "Current Session",
                "lastUpdate": datetime.now().isoformat()
            }
        ]
        
        # Add previous sessions
        # In a real implementation, you would get this from database
        
        return StandardResponse(
            code=200,
            success=True,
            message="Session history retrieved successfully",
            data=history
        )
    except Exception as e:
        logger.error(f"Error getting session history: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error retrieving session history: {str(e)}")

@app.get("/session/{history_session_id}/history", response_model=StandardResponse[SessionHistoryResponse])
@limiter.limit("20/minute")
async def get_conversation_history(
    request: Request,
    history_session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get conversation history for a session"""
    logger.info(f"Conversation history requested by user {current_user.username} for session {history_session_id}")
    try:
        # Get conversation history
        history = session_service.get_conversation_history(history_session_id)
        
        if not history:
            raise ResourceNotFoundError(f"Session {history_session_id} not found or has no history")
        
        # Adapt history for frontend
        adapted_history = frontend_adapter.adapt_session_history(history)
        
        history_items = []
        for msg in adapted_history:
            history_items.append(
                SessionHistoryItem(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=msg["timestamp"]
                )
            )
        
        response = SessionHistoryResponse(
            session_id=history_session_id,
            history=history_items
        )
        
        return StandardResponse(
            code=200,
            success=True,
            message="Conversation history retrieved successfully",
            data=response
        )
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error retrieving conversation history: {str(e)}")

@app.post("/session/reset", response_model=StandardResponse[Dict[str, Any]])
@limiter.limit("10/minute")
async def reset_session(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session_id: str = Depends(get_session)
):
    """Reset a session"""
    logger.info(f"Session reset requested by user {current_user.username} for session {session_id}")
    try:
        # Clear conversation history
        success = session_service.clear_conversation(session_id)
        
        if not success:
            raise ResourceNotFoundError(f"Session {session_id} not found")
            
        # Reset payroll service state
        payroll_service.reset()
        
        # Reset session state
        session_service.update_session(session_id, {"current_state": "chat", "current_task": None})
        
        # Add welcome message
        welcome_message = "ようこそ！\n私は給与計算タスク管理エージェントです！すべてのタスクを紹介し、それぞれのタスクとその処理ルールを詳しく説明することができます。その後、どのタスクに取り組むかを選択するお手伝いをします。"
        session_service.add_to_conversation(session_id, "assistant", welcome_message)
        
        return StandardResponse(
            code=200,
            success=True,
            message="Session reset successfully",
            data={
                "session_id": session_id,
                "welcome_message": welcome_message
            }
        )
    except Exception as e:
        logger.error(f"Error resetting session: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error resetting session: {str(e)}")

# User information endpoint
@app.get("/user", response_model=StandardResponse[UserResponse])
@limiter.limit("10/minute")
async def get_current_user_info(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    logger.info(f"User info requested: {current_user.username}")
    try:
        # Adapt user info for frontend
        user_info = frontend_adapter.adapt_user_info({
            "username": current_user.username,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "scopes": current_user.scopes
        })
        
        return StandardResponse(
            code=200,
            success=True,
            message="User information retrieved successfully",
            data=UserResponse(
                username=user_info["username"],
                scopes=user_info["scopes"]
            )
        )
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error retrieving user information: {str(e)}")

# Admin routes - requires admin scope
@app.get("/admin/sessions")
@limiter.limit("10/minute")
async def get_all_sessions(
    request: Request,
    current_user: User = Depends(check_scopes(["admin"]))
):
    """Get all active sessions (admin only)"""
    logger.info(f"Admin requested all sessions: {current_user.username}")
    try:
        session_ids = session_service.get_all_session_ids()
        sessions_info = []
        
        for session_id in session_ids:
            session = session_service.get_session(session_id)
            if session:
                sessions_info.append({
                    "id": session_id,
                    "created_at": session.get("created_time", ""),
                    "last_activity": session.get("last_activity_time", ""),
                    "state": session.get("current_state", ""),
                    "current_task": session.get("current_task", "")
                })
        
        return StandardResponse(
            code=200,
            success=True,
            message="Sessions retrieved successfully",
            data={
                "session_count": len(sessions_info),
                "sessions": sessions_info
            }
        )
    except Exception as e:
        logger.error(f"Error getting all sessions: {str(e)}")
        raise PayrollAPIException(f"Error retrieving sessions: {str(e)}")

@app.delete("/admin/sessions/{admin_session_id}")
@limiter.limit("10/minute")
async def delete_session(
    request: Request,
    admin_session_id: str,
    current_user: User = Depends(check_scopes(["admin"]))
):
    """Delete a session (admin only)"""
    logger.info(f"Admin requested to delete session {admin_session_id}: {current_user.username}")
    try:
        success = session_service.delete_session(admin_session_id)
        
        if not success:
            raise ResourceNotFoundError(f"Session {admin_session_id} not found")
        
        return StandardResponse(
            code=200,
            success=True,
            message=f"Session {admin_session_id} deleted successfully",
            data=None
        )
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error deleting session: {str(e)}")

@app.get("/admin/users")
@limiter.limit("10/minute")
async def get_all_users(
    request: Request,
    current_user: User = Depends(check_scopes(["admin"]))
):
    """Get all users (admin only)"""
    logger.info(f"Admin requested all users: {current_user.username}")
    try:
        user_db = get_user_db()
        users_info = []
        
        for username, user_data in user_db.users.items():
            users_info.append({
                "username": username,
                "email": user_data.get("email", ""),
                "full_name": user_data.get("full_name", ""),
                "disabled": user_data.get("disabled", False),
                "scopes": user_data.get("scopes", [])
            })
        
        return StandardResponse(
            code=200,
            success=True,
            message="Users retrieved successfully",
            data={
                "user_count": len(users_info),
                "users": users_info
            }
        )
    except Exception as e:
        logger.error(f"Error getting all users: {str(e)}")
        raise PayrollAPIException(f"Error retrieving users: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    
    uvicorn.run(
        "api:app", 
        host=host, 
        port=port, 
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level="info"
    )