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

# Enums for more structured state management
class SessionState(str, Enum):
    INIT = "init"
    CHAT = "chat"
    FILE = "file"
    TASK = "task"
    DATE = "date"

class FileType(str, Enum):
    CSV = "csv"
    EXCEL = "excel"

# Enhanced request and response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class FileUploadRequest(BaseModel):
    file_type: FileType
    task_name: Optional[str] = None
    session_id: Optional[str] = None

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

class TaskResponse(BaseModel):
    task_id: str
    name: str
    description: str
    required_files: List[Dict[str, Any]]
    status: str

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app with rate limiting
app = FastAPI(
    title="Payroll Assistant API",
    description="API for payroll processing with natural language capabilities",
    version="1.0.0",
)

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

# Setup security (replaces CORS middleware setup)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
setup_api_security(app, allowed_origins=allowed_origins)

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

# Helper function to get session ID
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
    
    if file_type == FileType.CSV and file_ext != '.csv':
        raise ValidationError("Expected CSV file but got a different format")
    elif file_type == FileType.EXCEL and file_ext not in ['.xlsx', '.xls']:
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

@app.post("/chat")
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
            state=state_enum
        )
        
        return StandardResponse(
            code=200,
            success=True,
            message="Successfully processed chat message",
            data=chat_response.dict()
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Chat processing error: {str(e)}")

@app.post("/upload")
@limiter.limit("10/minute")
async def upload_file_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    file_type: FileType = Form(...),
    task_name: Optional[str] = Form(None),
    session_id: str = Depends(get_session),
    current_user = Depends(check_scopes(["write"]))  # Added authentication with write scope
):
    """Upload a file for processing"""
    logger.info(f"File upload request for session {session_id}: {file.filename}")
    try:
        # Validate and save file
        file_path = await save_upload_file(file, background_tasks, file_type)
        
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
                "file_type": file_type,
                "identity_result": upload_result.get("identity_result", "")
            },
            session_id=session_id,
            state=state_enum
        )
        
        return StandardResponse(
            code=200,
            success=True,
            message="File uploaded successfully",
            data=upload_response.dict()
        )
    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"File upload error: {str(e)}")

@app.get("/tasks")
@limiter.limit("60/minute")
async def get_tasks(
    request: Request,
    current_user = Depends(get_current_active_user)  # Changed from verify_credentials
):
    """Get a list of available tasks"""
    logger.info("Task list requested")
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

@app.get("/session/{session_id}/history")
@limiter.limit("20/minute")
async def get_conversation_history(
    request: Request,
    session_id: str,
    current_user = Depends(check_scopes(["read"]))  # Changed to use scopes
):
    """Get conversation history for a session"""
    logger.info(f"Conversation history requested for session {session_id}")
    try:
        history = session_service.get_conversation_history(session_id)
        if not history:
            raise ResourceNotFoundError(f"Session {session_id} not found or has no history")
        
        return StandardResponse(
            code=200,
            success=True,
            message="Conversation history retrieved successfully",
            data={"session_id": session_id, "history": history}
        )
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        if isinstance(e, PayrollAPIException):
            raise
        raise PayrollAPIException(f"Error retrieving conversation history: {str(e)}")

@app.post("/session/{session_id}/reset")
@limiter.limit("10/minute")
async def reset_session(
    request: Request,
    session_id: str,
    current_user = Depends(check_scopes(["write"]))  # Changed to use scopes
):
    """Reset a session"""
    logger.info(f"Session reset requested for {session_id}")
    try:
        # Clear conversation history
        if not session_service.clear_conversation(session_id):
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

# Add a protected admin route as an example
@app.get("/admin/sessions")
async def get_all_sessions(
    current_user = Depends(check_scopes(["admin"]))  # Require admin scope
):
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "127.0.0.1")
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)