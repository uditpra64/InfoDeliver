import os
import sys
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Add application directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import service classes
from application.services.payroll_service import PayrollService
from application.services.file_service import FileService
from application.services.session_service import SessionService

# Initialize FastAPI app
app = FastAPI(title="Payroll Assistant API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify allowed domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
config_path = os.path.join(os.getcwd(), "application", "json", "config.json")
payroll_service = PayrollService(config_path=config_path)
file_service = FileService()
session_service = SessionService()

# Request and response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    state: str

class TaskResponse(BaseModel):
    name: str
    description: str

class SessionResponse(BaseModel):
    session_id: str
    created_at: float
    last_activity: float

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

@app.get("/tasks", response_model=List[TaskResponse])
async def get_tasks():
    try:
        tasks = []
        for task_name in payroll_service.get_task_list():
            tasks.append(TaskResponse(
                name=task_name,
                description=payroll_service.get_task_description(task_name)
            ))
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/{task_name}/select")
async def select_task(task_name: str, session_id: str = Depends(get_session)):
    try:
        success = payroll_service.select_task(task_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Task '{task_name}' not found")
        
        # Update session with selected task
        session_service.update_session(session_id, {"current_task": task_name})
        
        # Get required files for this task
        result, _ = payroll_service.process_files()
        response_text = result if isinstance(result, str) else "\n".join(result)
        
        return {"success": True, "message": response_text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Depends(get_session)
):
    try:
        # Create temporary file
        temp_file_path = f"temp/{file.filename}"
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        
        # Save uploaded file
        with open(temp_file_path, "wb") as f:
            f.write(await file.read())
        
        # Process the file
        result = file_service.upload_file(temp_file_path)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        # Create a chat message with the file upload information
        file_message = f"選択されたファイル: {temp_file_path}"
        
        # Process the file message
        chat_response, extra_info = payroll_service.process_message(file_message)
        response_text = chat_response if isinstance(chat_response, str) else "\n".join(chat_response)
        
        # Update session
        session_service.add_to_conversation(session_id, "user", file_message)
        session_service.add_to_conversation(session_id, "assistant", response_text)
        
        return {
            "success": True, 
            "filename": file.filename,
            "response": response_text
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/date/set")
async def set_date(
    date: str = Form(...),
    session_id: str = Depends(get_session)
):
    try:
        result, extra_info = payroll_service.set_date(date)
        
        # Update session
        session_service.add_to_conversation(session_id, "user", date)
        session_service.add_to_conversation(session_id, "assistant", result)
        
        return {"success": True, "response": result, "state": payroll_service.get_current_state()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/reset")
async def reset_session(session_id: str = Depends(get_session)):
    try:
        # Create a new session
        new_session_id = session_service.create_session()
        
        # Reset the payroll service
        payroll_service.reset()
        
        return {"success": True, "session_id": new_session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversation", response_model=List[Dict[str, Any]])
async def get_conversation(session_id: str = Depends(get_session)):
    try:
        conversation = session_service.get_conversation_history(session_id)
        return conversation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}