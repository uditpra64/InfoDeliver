import os
import sys
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path

# Get the parent directory to import setup_paths
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Import setup_paths to configure everything
import setup_paths

# Define app_dir AFTER importing setup_paths
app_dir = os.path.join(parent_dir, "application")

# Now import service classes
from application.services.payroll_service import PayrollService
from application.services.file_service import FileService
from application.services.session_service import SessionService

# Initialize FastAPI app
app = FastAPI(title="Payroll Assistant API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
config_path = os.path.join(app_dir, "json", "config.json")
print(f"Using config path: {config_path}")

try:
    file_service = FileService()
    print("FileService initialized successfully")
    
    payroll_service = PayrollService(config_path=config_path)
    print("PayrollService initialized successfully")
    
    session_service = SessionService()
    print("SessionService initialized successfully")
except Exception as e:
    print(f"Error initializing services: {e}")
    import traceback
    traceback.print_exc()


# Request and response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    state: str

# Helper function to get session ID
async def get_session(x_session_id: Optional[str] = Header(None)):
    if not x_session_id:
        # Create new session if none provided
        return session_service.create_session()
    
    # Check if session exists
    session = session_service.get_session(x_session_id)
    if not session:
        # Create new session if provided ID is invalid
        return session_service.create_session()
    
    return x_session_id

# Routes
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, session_id: str = Depends(get_session)):
    try:
        # Add message to conversation history
        session_service.add_to_conversation(session_id, "user", request.message)
        
        # Process the message
        result, extra_info = payroll_service.process_message(request.message)
        
        # Convert result to string if it's a list
        response_text = result if isinstance(result, str) else "\n".join(result)
        
        # Add assistant response to conversation
        session_service.add_to_conversation(session_id, "assistant", response_text)
        
        # Update session state
        current_state = payroll_service.get_current_state()
        session_service.update_session(session_id, {"current_state": current_state})
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            state=current_state
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}