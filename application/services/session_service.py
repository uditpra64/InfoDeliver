import logging
import time
import uuid
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class SessionState(str, Enum):
    """Enum representing possible session states"""
    INIT = "init"
    CHAT = "chat"
    FILE = "file"
    TASK = "task"
    DATE = "date"

class SessionError(Exception):
    """Base exception for session-related errors"""
    pass

class SessionNotFoundError(SessionError):
    """Exception raised when a session is not found"""
    pass

class SessionExpiredError(SessionError):
    """Exception raised when a session has expired"""
    pass

class SessionMessage:
    """Class representing a message in a conversation"""
    def __init__(self, role: str, message: str, timestamp: Optional[float] = None):
        """
        Initialize a session message
        
        Args:
            role: Message role (user, assistant, system)
            message: Message content
            timestamp: Optional timestamp (defaults to current time)
        """
        self.role = role
        self.message = message
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation"""
        return {
            "role": self.role,
            "message": self.message,
            "timestamp": self.timestamp,
            "formatted_time": datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionMessage':
        """Create a SessionMessage from a dictionary"""
        return cls(
            role=data["role"],
            message=data["message"],
            timestamp=data.get("timestamp", time.time())
        )

class Session:
    """Class representing a user session"""
    def __init__(
        self, 
        session_id: str,
        created_at: Optional[float] = None,
        max_lifetime_hours: int = 24
    ):
        """
        Initialize a session
        
        Args:
            session_id: Unique session identifier
            created_at: Optional creation timestamp
            max_lifetime_hours: Maximum lifetime in hours
        """
        self.id = session_id
        self.created_at = created_at or time.time()
        self.last_activity = self.created_at
        self.conversation_history: List[SessionMessage] = []
        self.metadata: Dict[str, Any] = {}
        self.current_task: Optional[str] = None
        self.current_state = SessionState.INIT
        self.max_lifetime_seconds = max_lifetime_hours * 3600
    
    def add_message(self, role: str, message: str) -> SessionMessage:
        """
        Add a message to the conversation history
        
        Args:
            role: Message role (user, assistant, system)
            message: Message content
            
        Returns:
            The created SessionMessage
        """
        msg = SessionMessage(role, message)
        self.conversation_history.append(msg)
        self.last_activity = time.time()
        return msg
    
    def clear_conversation(self) -> None:
        """Clear the conversation history"""
        self.conversation_history = []
        self.last_activity = time.time()
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata value"""
        self.metadata[key] = value
        self.last_activity = time.time()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value"""
        return self.metadata.get(key, default)
    
    def is_expired(self) -> bool:
        """Check if the session has expired"""
        return (time.time() - self.last_activity) > self.max_lifetime_seconds
    
    def seconds_until_expiry(self) -> float:
        """Get seconds until session expiry"""
        return max(0, self.max_lifetime_seconds - (time.time() - self.last_activity))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary representation"""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "conversation_history": [msg.to_dict() for msg in self.conversation_history],
            "metadata": self.metadata,
            "current_task": self.current_task,
            "current_state": self.current_state,
            "expiry_seconds": self.seconds_until_expiry(),
            "created_time": datetime.fromtimestamp(self.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            "last_activity_time": datetime.fromtimestamp(self.last_activity).strftime("%Y-%m-%d %H:%M:%S")
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """Create a Session from a dictionary"""
        session = cls(
            session_id=data["id"],
            created_at=data.get("created_at", time.time())
        )
        session.last_activity = data.get("last_activity", session.created_at)
        session.metadata = data.get("metadata", {})
        session.current_task = data.get("current_task")
        
        # Handle state as string or enum
        state_val = data.get("current_state", SessionState.INIT)
        if isinstance(state_val, str):
            try:
                session.current_state = SessionState(state_val)
            except ValueError:
                session.current_state = SessionState.INIT
        else:
            session.current_state = state_val
        
        # Handle conversation history
        history = data.get("conversation_history", [])
        session.conversation_history = [
            SessionMessage.from_dict(msg) if isinstance(msg, dict) else msg
            for msg in history
        ]
        
        return session

class SessionService:
    """
    Enhanced service for managing user sessions with persistence capability.
    This helps maintain conversation state between API calls.
    """
    
    def __init__(
        self, 
        session_dir: Optional[str] = None,
        max_lifetime_hours: int = 24,
        persistence_enabled: bool = True
    ):
        """
        Initialize the session service
        
        Args:
            session_dir: Directory for session persistence
            max_lifetime_hours: Maximum session lifetime in hours
            persistence_enabled: Whether to persist sessions to disk
        """
        self.logger = logging.getLogger(__name__)
        self.sessions: Dict[str, Session] = {}
        self.max_lifetime_hours = max_lifetime_hours
        self.persistence_enabled = persistence_enabled
        
        # Set up session directory if persistence is enabled
        if persistence_enabled:
            self.session_dir = session_dir or os.path.join(os.getcwd(), "sessions")
            os.makedirs(self.session_dir, exist_ok=True)
            self.logger.info(f"Session persistence enabled, using directory: {self.session_dir}")
            
            # Load existing sessions
            self._load_sessions()
        else:
            self.session_dir = None
            self.logger.info("Session persistence disabled")
        
        self.logger.info(f"SessionService initialized with {len(self.sessions)} sessions")
    
    def create_session(self) -> str:
        """
        Create a new session
        
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = Session(
            session_id=session_id,
            max_lifetime_hours=self.max_lifetime_hours
        )
        
        if self.persistence_enabled:
            self._save_session(session_id)
            
        self.logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a session by ID
        
        Args:
            session_id: The session ID
            
        Returns:
            The session data or None if not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return None
            
        if session.is_expired():
            self.logger.info(f"Session {session_id} has expired")
            self.delete_session(session_id)
            return None
            
        session.last_activity = time.time()
        
        if self.persistence_enabled:
            self._save_session(session_id)
            
        return session.to_dict()
    
    def get_session_object(self, session_id: str) -> Optional[Session]:
        """
        Get a session object by ID (internal use)
        
        Args:
            session_id: The session ID
            
        Returns:
            Session object or None if not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return None
            
        if session.is_expired():
            self.logger.info(f"Session {session_id} has expired")
            self.delete_session(session_id)
            return None
            
        session.last_activity = time.time()
        return session
    
    def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        Update a session with new data
        
        Args:
            session_id: The session ID
            data: New data to update in the session
            
        Returns:
            True if successful, False if session not found
        """
        session = self.get_session_object(session_id)
        if not session:
            return False
        
        # Update metadata
        for key, value in data.items():
            if key == "current_state" and isinstance(value, str):
                try:
                    session.current_state = SessionState(value)
                except ValueError:
                    session.current_state = SessionState.CHAT
            elif key == "current_task":
                session.current_task = value
            else:
                session.set_metadata(key, value)
        
        if self.persistence_enabled:
            self._save_session(session_id)
            
        return True
    
    def add_to_conversation(self, session_id: str, role: str, message: str) -> bool:
        """
        Add a message to the conversation history for a session
        
        Args:
            session_id: The session ID
            role: Either "user", "assistant", or "system"
            message: The message text
            
        Returns:
            True if successful, False if session not found
        """
        session = self.get_session_object(session_id)
        if not session:
            return False
        
        # Validate role
        valid_roles = ["user", "assistant", "system"]
        if role not in valid_roles:
            role = "system"  # Default to system for unknown roles
        
        session.add_message(role, message)
        
        if self.persistence_enabled:
            self._save_session(session_id)
            
        return True
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get the conversation history for a session
        
        Args:
            session_id: The session ID
            
        Returns:
            List of conversation messages or empty list if session not found
        """
        session = self.get_session_object(session_id)
        if not session:
            # Log this as information, not error, since it's an expected case
            self.logger.info(f"Session {session_id} not found or expired")
            return []
        
        try:
            return [msg.to_dict() for msg in session.conversation_history]
        except Exception as e:
            self.logger.error(f"Error retrieving conversation history for session {session_id}: {e}")
            return []
    
    def clear_conversation(self, session_id: str) -> bool:
        """
        Clear the conversation history for a session
        
        Args:
            session_id: The session ID
            
        Returns:
            True if successful, False if session not found
        """
        session = self.get_session_object(session_id)
        if not session:
            return False
        
        session.clear_conversation()
        
        if self.persistence_enabled:
            self._save_session(session_id)
            
        return True
    
    def cleanup_old_sessions(self, max_age_seconds: int = 86400) -> int:
        """
        Remove sessions older than the specified age with better file handling
        
        Args:
            max_age_seconds: Maximum session age in seconds (default: 24 hours)
            
        Returns:
            Number of sessions removed
        """
        to_delete = []
        current_time = time.time()
        
        # First identify sessions to delete
        for session_id, session in self.sessions.items():
            if current_time - session.last_activity > max_age_seconds:
                to_delete.append(session_id)
        
        deleted_count = 0
        for session_id in to_delete:
            try:
                # Try to delete the session
                self._delete_session_file(session_id)
                # Remove from memory even if file deletion fails
                if session_id in self.sessions:
                    del self.sessions[session_id]
                deleted_count += 1
            except Exception as e:
                self.logger.warning(f"Could not fully remove session {session_id}: {e}")
        
        self.logger.info(f"Cleaned up {deleted_count} old sessions")
        return deleted_count

    def _delete_session_file(self, session_id: str) -> None:
        """
        Delete a session file with improved error handling
        
        Args:
            session_id: ID of the session whose file should be deleted
        """
        if not self.persistence_enabled:
            return
            
        session_file = os.path.join(self.session_dir, f"{session_id}.json")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                self.logger.info(f"Deleted session file: {session_file}")
            except PermissionError:
                self.logger.warning(f"Cannot delete session file {session_file} - permission denied")
            except OSError as e:
                self.logger.warning(f"Error deleting session file {session_file}: {e}")
        

    
    def get_session_count(self) -> int:
        """
        Get the total number of active sessions
        
        Returns:
            Number of active sessions
        """
        return len(self.sessions)
    
    def get_all_session_ids(self) -> List[str]:
        """
        Get a list of all session IDs
        
        Returns:
            List of session IDs
        """
        return list(self.sessions.keys())
    
    def _save_session(self, session_id: str) -> None:
        """
        Save a session to disk (internal method)
        
        Args:
            session_id: ID of the session to save
        """
        if not self.persistence_enabled or session_id not in self.sessions:
            return
            
        session = self.sessions[session_id]
        session_file = os.path.join(self.session_dir, f"{session_id}.json")
        
        try:
            with open(session_file, 'w') as f:
                # Convert Session object to dictionary
                session_data = session.to_dict()
                
                # Convert conversation history to serializable format
                session_data['conversation_history'] = [
                    msg.to_dict() for msg in session.conversation_history
                ]
                
                # Convert state enum to string
                if isinstance(session_data['current_state'], SessionState):
                    session_data['current_state'] = session_data['current_state'].value
                
                json.dump(session_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving session {session_id}: {e}")
    
    def _load_sessions(self) -> None:
        """
        Load all sessions from disk with improved error handling for file locking
        """
        if not self.persistence_enabled:
            return
            
        try:
            loaded_count = 0
            for filename in os.listdir(self.session_dir):
                if filename.endswith('.json'):
                    session_id = filename[:-5]  # Remove .json
                    session_file = os.path.join(self.session_dir, filename)
                    
                    try:
                        # Use a try-except block for each individual file
                        with open(session_file, 'r') as f:
                            session_data = json.load(f)
                            
                            # Create Session object
                            session = Session.from_dict(session_data)
                            
                            # Skip expired sessions
                            if session.is_expired():
                                self.logger.info(f"Skipping expired session {session_id}")
                                try:
                                    os.remove(session_file)
                                except (PermissionError, OSError) as e:
                                    # Don't fail if we can't delete the file - just log it
                                    self.logger.info(f"Could not remove expired session file: {e}")
                                continue
                                
                            self.sessions[session_id] = session
                            loaded_count += 1
                    except (PermissionError, OSError) as e:
                        # Handle file locking errors gracefully
                        self.logger.info(f"Could not access session file {session_id}: {e}")
                        continue
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Malformed session file {session_id}: {e}")
                        continue
                    except Exception as e:
                        self.logger.error(f"Error loading session {session_id}: {e}")
                        continue
            
            self.logger.info(f"Loaded {loaded_count} sessions from disk")
        except Exception as e:
            self.logger.error(f"Error loading sessions: {e}")

# Simple test function
def test_session_service():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Create with temporary persistence
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        service = SessionService(
            session_dir=temp_dir,
            max_lifetime_hours=1,
            persistence_enabled=True
        )
        
        # Create a session
        session_id = service.create_session()
        print(f"Created session: {session_id}")
        
        # Add messages
        service.add_to_conversation(session_id, "user", "Hello")
        service.add_to_conversation(session_id, "assistant", "Hi there!")
        
        # Get conversation history
        history = service.get_conversation_history(session_id)
        print(f"Conversation has {len(history)} messages")
        
        # Update session
        service.update_session(session_id, {"current_state": "chat", "test_value": 123})
        
        # Get session
        session = service.get_session(session_id)
        print(f"Session state: {session['current_state']}")
        print(f"Session metadata: {session['metadata']}")
        
        # Test persistence by creating a new service instance
        service2 = SessionService(session_dir=temp_dir, persistence_enabled=True)
        session2 = service2.get_session(session_id)
        print(f"Retrieved session from disk: {session2 is not None}")
        if session2:
            print(f"Retrieved session has {len(session2['conversation_history'])} messages")
        
        # Clean up
        service.delete_session(session_id)
        print(f"Sessions remaining: {service.get_session_count()}")

if __name__ == "__main__":
    test_session_service()