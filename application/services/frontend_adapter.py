import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class FrontendAdapter:
    """
    Adapter class to ensure API responses match what the frontend expects.
    This bridges any gaps between backend implementation and frontend requirements.
    """
    
    @staticmethod
    def adapt_chat_response(response_text: str, session_id: str, state: str) -> Dict[str, Any]:
        """Adapt chat responses to frontend expected format"""
        # Detect if the response contains HTML table data
        is_html = 'class="dataframe">' in response_text
        
        return {
            "response": response_text,
            "session_id": session_id,
            "state": state,
            "is_html": is_html,
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def adapt_file_info(file_data: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt file information to frontend expected format"""
        # Ensure all required fields are present
        return {
            "id": file_data.get("id", 0),
            "name": file_data.get("name", ""),
            "task_name": file_data.get("task_name", ""),
            "upload_date": file_data.get("upload_date", datetime.now().isoformat()),
            "row_count": file_data.get("row_count", 0),
            "output": file_data.get("output", False)
        }
    
    @staticmethod
    def adapt_task_list(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adapt task list to frontend expected format"""
        adapted_tasks = []
        
        for task in tasks:
            # Ensure task has the format expected by frontend
            adapted_task = {
                "task_id": task.get("task_id", task.get("name", "")),
                "name": task.get("name", ""),
                "description": task.get("description", ""),
                "required_files": task.get("required_files", []),
                "status": task.get("status", "available")
            }
            adapted_tasks.append(adapted_task)
            
        return adapted_tasks
    
    @staticmethod
    def adapt_session_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Adapt session history to frontend expected format"""
        adapted_history = []
        
        for msg in history:
            # Convert role from various formats to either "user" or "assistant"
            role = msg.get("role", "")
            if role in ["human", "user"]:
                role = "user"
            elif role in ["ai", "assistant", "system"]:
                role = "assistant"
            
            # Get message content with fallbacks
            content = msg.get("message", msg.get("content", ""))
            
            # Handle timestamp formats
            timestamp = msg.get("timestamp", "")
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp).isoformat()
            elif not timestamp:
                timestamp = datetime.now().isoformat()
            
            adapted_msg = {
                "role": role,
                "content": content,
                "timestamp": timestamp
            }
            adapted_history.append(adapted_msg)
            
        return adapted_history
    
    @staticmethod
    def adapt_user_info(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt user information to frontend expected format"""
        return {
            "username": user_data.get("username", ""),
            "full_name": user_data.get("full_name", ""),
            "email": user_data.get("email", ""),
            "scopes": user_data.get("scopes", [])
        }
    
    @staticmethod
    def adapt_error_response(error_message: str, status_code: int = 500) -> Dict[str, Any]:
        """Create a standardized error response"""
        return {
            "error": True,
            "message": error_message,
            "status_code": status_code,
            "timestamp": datetime.now().isoformat()
        }

# Create a singleton instance
frontend_adapter = FrontendAdapter()