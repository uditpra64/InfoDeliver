import os
import sys
import tempfile
import logging
import shutil
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Generic, TypeVar
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header, Request, BackgroundTasks, status
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator, Field
from pydantic.generics import GenericModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Import security components
from application.services.security.auth import (
    setup_api_security, 
    get_current_active_user, 
    check_scopes
)

# Get the parent directory to import setup_paths
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Import setup_paths to configure everything
import setup_paths

# Define app_dir AFTER importing setup_paths
app_dir = os.path.join(parent_dir, "application")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(current_dir, "api.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("payroll_api")

# Now import service classes with better error handling
try:
    from application.services.payroll_service import PayrollService
    from application.services.file_service import FileService
    from application.services.session_service import SessionService
    logger.info("Service modules imported successfully")
except ImportError as e:
    logger.critical(f"Failed to import service modules: {e}")
    raise

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

class TokenRequest(BaseModel):
    username: str
    password: str
    scope: Optional[str] = None

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

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="Payroll Assistant API",
    description="API for payroll processing with natural language capabilities",
    version="1.0.0",
)

allowed_origins = ["http://localhost:3000"]  # Make sure React app origin is included
setup_api_security(app, allowed_origins=allowed_origins)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Handle rate limit exceptions
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=HTTP_429_TOO_MANY_REQUESTS,
        content=StandardResponse(
            code=HTTP_429_TOO_MANY_REQUESTS,
            success=False,
            message="Rate limit exceeded",
            data={"detail": "Too many requests"}
        ).dict(),
    )

# Custom exception handler for PayrollAPIException
@app.exception_handler(PayrollAPIException)
async def payroll_exception_handler(request: Request, exc: PayrollAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content=StandardResponse(
            code=exc.status_code,
            success=False,
            message=exc.message,
            data=None
        ).dict(),
    )

# Handle other HTTP exceptions
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=StandardResponse(
            code=exc.status_code,
            success=False,
            message=str(exc.detail),
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
    file_service = FileService()
    logger.info("FileService initialized successfully")
    
    payroll_service = PayrollService(config_path=config_path)
    logger.info("PayrollService initialized successfully")
    
    session_service = SessionService()
    logger.info("SessionService initialized successfully")
    
    # Clean up expired sessions periodically
    @app.on_event("startup")
    def startup_event():
        # Clean up expired sessions
        session_service.cleanup_old_sessions(max_age_seconds=session_expiry_hours * 3600)
        logger.info(f"Startup: cleaned up sessions older than {session_expiry_hours} hours")
        
        # Clean up temporary files
        cleanup_temp_files()
        logger.info("Startup: cleaned up temporary files")
    
    # Cleanup on shutdown
    @app.on_event("shutdown")
    def shutdown_event():
        logger.info("API shutting down")
        cleanup_temp_files()
except Exception as e:
    logger.critical(f"Error initializing services: {e}")
    raise

# Helper function to clean up temporary files
def cleanup_temp_files():
    """Clean up temporary files older than 24 hours"""
    try:
        temp_dir = upload_folder
        current_time = time.time()
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                # If file is older than 24 hours, delete it
                if current_time - os.path.getmtime(file_path) > 86400:  # 24 hours in seconds
                    os.remove(file_path)
                    logger.info(f"Deleted old temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up temp files: {e}")

# Helper function to get or create session
async def get_session(x_session_id: Optional[str] = Header(None)):
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
    # Validate file size
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    file_content = b''
    
    while True:
        chunk = await upload_file.read(chunk_size)
        if not chunk:
            break
        file_size += len(chunk)
        file_content += chunk
        
        # Check if file is too large
        if file_size > max_upload_size_mb * 1024 * 1024:
            raise ValidationError(f"File too large (max {max_upload_size_mb}MB)")
    
    # Validate file type
    filename = upload_file.filename
    if not filename:
        raise ValidationError("Filename is required")
    
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_type == FileType.CSV.value and file_ext != '.csv':
        raise ValidationError("Expected CSV file but got a different format")
    elif file_type == FileType.EXCEL.value and file_ext not in ['.xlsx', '.xls']:
        raise ValidationError("Expected Excel file but got a different format")
    elif file_ext not in ['.csv', '.xlsx', '.xls']:
        raise ValidationError("Only CSV and Excel files are supported")
    
    # Generate secure filename to prevent path traversal
    secure_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_folder, secure_filename)
    
    # Write file to disk
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Schedule cleanup
    background_tasks.add_task(lambda: os.unlink(file_path) if os.path.exists(file_path) else None)
    
    return file_path

# Authentication endpoints
@app.post("/token", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, form_data: TokenRequest):
    """Get authentication token"""
    # For development/demo purposes, implement simple auth:
    valid_users = {
        "admin": {"password": "password", "scopes": ["admin", "read", "write"]},
        "user": {"password": "password", "scopes": ["read"]}
    }
    
    if form_data.username not in valid_users or form_data.password != valid_users[form_data.username]["password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    scopes = valid_users[form_data.username]["scopes"]
    if form_data.scope and form_data.scope not in scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The scope {form_data.scope} is not available for this user"
        )
    
    # Create a token valid for 30 minutes
    expires_at = datetime.utcnow() + timedelta(minutes=30)
    
    # In a real app, you'd use JWT or similar
    access_token = str(uuid.uuid4())
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_at=expires_at
    )

# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return StandardResponse(
        code=200,
        success=True,
        message="API is operational",
        data={"status": "ok", "timestamp": datetime.now().isoformat()}
    )

@app.post("/chat", response_model=StandardResponse[ChatResponse])
@limiter.limit("30/minute")
async def chat_endpoint(
    request: Request,
    chat_request: ChatRequest, 
    session_id: str = Depends(get_session)
):
    """Process a chat message and return a response"""
    logger.info(f"Processing chat message for session {session_id}")
    try:
        # Add message to conversation history
        session_service.add_to_conversation(session_id, "user", chat_request.message)
        
        # Process the message
        result, extra_info = payroll_service.process_message(chat_request.message)

        if isinstance(result, tuple) and len(result) == 2:
            response_text, extra_info = result
        else:
            response_text = result if isinstance(result, str) else "\n".join(result)
        
        # Convert result to string if it's a list
        response_text = result if isinstance(result, str) else "\n".join(result)
        
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
        
        logger.info(f"Chat processed successfully for session {session_id}, state: {current_state}")
        
        chat_response = ChatResponse(
            response=response_text,
            session_id=session_id,
            state=state_enum,
            timestamp=datetime.now().isoformat()
        )
        
        return StandardResponse(
            code=200,
            success=True,
            message="Successfully processed chat message",
            data=chat_response
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Chat processing error: {str(e)}")

@app.post("/upload", response_model=StandardResponse[FileUploadResponse])
@limiter.limit("10/minute")
async def upload_file_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    file_type: FileType = Form(...),
    task_name: Optional[str] = Form(None),
    session_id: str = Depends(get_session)
):
    """Upload a file for processing"""
    logger.info(f"File upload request for session {session_id}: {file.filename}")
    try:
        # Validate and save file
        file_path = await save_upload_file(file, background_tasks, file_type.value)
        
        # Process the file
        upload_result = file_service.upload_file(file_path)
        
        if not upload_result["success"]:
            raise ValidationError(upload_result["message"])
        
        # Construct message for payroll service
        message = f"選択されたファイル: {file_path}"
        result, extra_info = payroll_service.process_message(message)
        
        # Update session state
        current_state = payroll_service.get_current_state()
        session_service.update_session(session_id, {"current_state": current_state})
        
        # Map state to enum
        try:
            state_enum = SessionState(current_state)
        except ValueError:
            state_enum = SessionState.FILE  # Default to FILE if unknown state
            
        # Add system message to conversation
        response_text = result if isinstance(result, str) else "\n".join(result)
        session_service.add_to_conversation(session_id, "system", f"File uploaded: {file.filename}")
        session_service.add_to_conversation(session_id, "assistant", response_text)
        
        logger.info(f"File uploaded successfully: {file.filename}")
        
        upload_response = FileUploadResponse(
            success=True,
            file_id=upload_result.get("file_id"),
            message="File uploaded successfully",
            file_details={
                "original_name": file.filename,
                "file_type": file_type.value,
                "identity_result": upload_result.get("identity_result", "")
            },
            session_id=session_id,
            state=state_enum
        )
        
        return StandardResponse(
            code=200,
            success=True,
            message="File uploaded successfully",
            data=upload_response
        )
    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"File upload error: {str(e)}")

@app.get("/files", response_model=StandardResponse[List[FileInfo]])
@limiter.limit("60/minute")
async def get_files(
    request: Request,
    session_id: str = Depends(get_session)
):
    """Get list of uploaded files"""
    logger.info(f"Files list requested for session {session_id}")
    try:
        files = file_service.get_file_list()
        
        return StandardResponse(
            code=200,
            success=True,
            message="Files retrieved successfully",
            data=files
        )
    except Exception as e:
        logger.error(f"Error getting files: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error retrieving files: {str(e)}")

@app.get("/tasks", response_model=StandardResponse[List[TaskResponse]])
@limiter.limit("60/minute")
async def get_tasks(
    request: Request,
    session_id: str = Depends(get_session)
):
    """Get a list of available tasks"""
    logger.info(f"Task list requested for session {session_id}")
    try:
        tasks = payroll_service.get_task_list()
        result = []
        
        for task_name in tasks:
            description = payroll_service.get_task_description(task_name)
            # This is a placeholder - you would need to modify PayrollService to return required files
            required_files = []  # payroll_service.get_task_files(task_name)
            
            result.append(TaskResponse(
                task_id=task_name,
                name=task_name,
                description=description,
                required_files=required_files,
                status="available"
            ))
        
        return StandardResponse(
            code=200,
            success=True,
            message="Tasks retrieved successfully",
            data=result
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
    session_id: str = Depends(get_session)
):
    """Select a task for processing"""
    logger.info(f"Task selection request for session {session_id}: {task_id}")
    try:
        # Select the task
        success = payroll_service.select_task(task_id)
        
        if not success:
            raise ResourceNotFoundError(f"Task {task_id} not found")
        
        # Update session state
        session_service.update_session(session_id, {"current_state": "file"})
        
        # Add message to conversation
        session_service.add_to_conversation(
            session_id, 
            "system", 
            f"Task selected: {task_id}"
        )
        
        return StandardResponse(
            code=200,
            success=True,
            message=f"Task {task_id} selected successfully",
            data={"task_id": task_id, "session_id": session_id}
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
    session_id: str = Depends(get_session)
):
    """Get list of session history"""
    logger.info(f"Session history list requested for session {session_id}")
    try:
        # In a real app, you'd fetch this from database
        # For demo purposes, return sample data
        history = [
            {
                "id": "session1",
                "title": "Previous Chat 1",
                "lastUpdate": datetime.now().isoformat()
            },
            {
                "id": session_id,
                "title": "Current Chat",
                "lastUpdate": datetime.now().isoformat()
            }
        ]
        
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

@app.get("/session/{session_id}/history", response_model=StandardResponse[SessionHistoryResponse])
@limiter.limit("20/minute")
async def get_conversation_history(
    request: Request,
    session_id: str
):
    """Get conversation history for a session"""
    logger.info(f"Conversation history requested for session {session_id}")
    try:
        # Get conversation history
        history = session_service.get_conversation_history(session_id)
        
        if not history:
            raise ResourceNotFoundError(f"Session {session_id} not found or has no history")
        
        # Convert Unix timestamps to ISO string format if needed
        history_items = []
        for msg in history:
            # Check if timestamp is a float and convert it
            timestamp = msg.get("timestamp", "")
            if isinstance(timestamp, float):
                timestamp = datetime.fromtimestamp(timestamp).isoformat()
            elif isinstance(timestamp, int):
                timestamp = datetime.fromtimestamp(timestamp).isoformat()
            
            history_items.append(
                SessionHistoryItem(
                    role=msg["role"],
                    content=msg["message"],
                    timestamp=timestamp
                )
            )
        
        response = SessionHistoryResponse(
            session_id=session_id,
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
    session_id: str = Depends(get_session)
):
    """Reset a session"""
    logger.info(f"Session reset requested for {session_id}")
    try:
        # Clear conversation history
        success = session_service.clear_conversation(session_id)
        
        if not success:
            raise ResourceNotFoundError(f"Session {session_id} not found")
            
        # Reset payroll service state
        payroll_service.reset()
        
        return StandardResponse(
            code=200,
            success=True,
            message="Session reset successfully",
            data={"session_id": session_id}
        )
    except Exception as e:
        logger.error(f"Error resetting session: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error resetting session: {str(e)}")

# Admin routes
@app.get("/admin/sessions")
@limiter.limit("10/minute")
async def get_all_sessions(request: Request):  # Added request parameter
    """Get all active sessions (admin only)"""
    try:
        session_ids = session_service.get_all_session_ids()
        return StandardResponse(
            code=200,
            success=True,
            message="Sessions retrieved successfully",
            data={
                "session_count": len(session_ids),
                "session_ids": session_ids
            }
        )
    except Exception as e:
        logger.error(f"Error getting all sessions: {str(e)}")
        raise PayrollAPIException(f"Error retrieving sessions: {str(e)}")