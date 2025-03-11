import logging
from typing import Dict, Any, List
import uuid
import time

logger = logging.getLogger(__name__)

class SessionService:
    """
    Service for managing user sessions in the web application.
    This helps maintain conversation state between API calls.
    """
    
    def __init__(self):
        """Initialize the session service with an empty sessions dictionary."""
        self.logger = logging.getLogger(__name__)
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.logger.info("SessionService initialized")
    
    def create_session(self) -> str:
        """
        Create a new session.
        
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "created_at": time.time(),
            "last_activity": time.time(),
            "conversation_history": [],
            "current_task": None,
            "current_state": "chat"
        }
        self.logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get a session by ID.
        
        Args:
            session_id: The session ID
            
        Returns:
            The session data or None if not found
        """
        session = self.sessions.get(session_id)
        if session:
            session["last_activity"] = time.time()
        return session
    
    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        Update a session with new data.
        
        Args:
            session_id: The session ID
            data: New data to update in the session
            
        Returns:
            True if successful, False if session not found
        """
        if session_id not in self.sessions:
            return False
        
        self.sessions[session_id].update(data)
        self.sessions[session_id]["last_activity"] = time.time()
        return True
    
    def add_to_conversation(self, session_id: str, role: str, message: str) -> bool:
        """
        Add a message to the conversation history for a session.
        
        Args:
            session_id: The session ID
            role: Either "user" or "assistant"
            message: The message text
            
        Returns:
            True if successful, False if session not found
        """
        if session_id not in self.sessions:
            return False
        
        self.sessions[session_id]["conversation_history"].append({
            "role": role,
            "message": message,
            "timestamp": time.time()
        })
        self.sessions[session_id]["last_activity"] = time.time()
        return True
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get the conversation history for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            List of conversation messages or empty list if session not found
        """
        if session_id not in self.sessions:
            return []
        
        return self.sessions[session_id]["conversation_history"]
    
    def clear_conversation(self, session_id: str) -> bool:
        """
        Clear the conversation history for a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            True if successful, False if session not found
        """
        if session_id not in self.sessions:
            return False
        
        self.sessions[session_id]["conversation_history"] = []
        self.sessions[session_id]["last_activity"] = time.time()
        return True
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            True if successful, False if session not found
        """
        if session_id not in self.sessions:
            return False
        
        del self.sessions[session_id]
        return True
    
    def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> int:
        """
        Remove sessions older than the specified age.
        
        Args:
            max_age_seconds: Maximum session age in seconds
            
        Returns:
            Number of sessions removed
        """
        current_time = time.time()
        to_delete = []
        
        for session_id, session in self.sessions.items():
            if current_time - session["last_activity"] > max_age_seconds:
                to_delete.append(session_id)
        
        for session_id in to_delete:
            del self.sessions[session_id]
        
        self.logger.info(f"Cleaned up {len(to_delete)} old sessions")
        return len(to_delete)