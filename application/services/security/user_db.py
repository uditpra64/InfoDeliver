import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import os
import json
from passlib.context import CryptContext

# Initialize logging
logger = logging.getLogger(__name__)

# Initialize password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserInDB(BaseModel):
    """User model as stored in the database"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None 
    hashed_password: str
    disabled: bool = False
    scopes: List[str] = []

class UserDB:
    """User database interface that can be switched between implementations"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.users: Dict[str, Dict[str, Any]] = {}
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "users.json")
        self._load_users()
    
    def _load_users(self) -> None:
        """Load users from a JSON file or initialize with default admin"""
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'r') as f:
                    self.users = json.load(f)
                    logger.info(f"Loaded {len(self.users)} users from {self.db_path}")
            else:
                # Initialize with a default admin user
                self._create_default_admin()
                self._save_users()  # Save the default user
        except Exception as e:
            logger.error(f"Error loading users: {str(e)}")
            # Initialize with a default admin user on error
            self._create_default_admin()
    
    def _save_users(self) -> None:
        """Save users to a JSON file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with open(self.db_path, 'w') as f:
                json.dump(self.users, f, indent=2)
            logger.info(f"Saved {len(self.users)} users to {self.db_path}")
        except Exception as e:
            logger.error(f"Error saving users: {str(e)}")
    
    def _create_default_admin(self) -> None:
        """Create a default admin user"""
        default_admin = {
            "username": "admin",
            "full_name": "Administrator",
            "email": "admin@example.com",
            "hashed_password": pwd_context.hash(os.getenv("ADMIN_PASSWORD", "admin")),
            "disabled": False,
            "scopes": ["admin", "read", "write"]
        }
        
        default_user = {
            "username": "user",
            "full_name": "Regular User",
            "email": "user@example.com",
            "hashed_password": pwd_context.hash(os.getenv("USER_PASSWORD", "password")),
            "disabled": False,
            "scopes": ["read"]
        }
        
        self.users = {
            "admin": default_admin,
            "user": default_user
        }
        
        logger.warning("Created default admin and user accounts. Change passwords immediately in production!")
    
    def get_user(self, username: str) -> Optional[UserInDB]:
        """Get a user by username"""
        if username in self.users:
            return UserInDB(**self.users[username])
        return None
    
    def create_user(self, 
                   username: str, 
                   password: str, 
                   email: Optional[str] = None,
                   full_name: Optional[str] = None,
                   scopes: List[str] = None,
                   disabled: bool = False) -> Optional[UserInDB]:
        """Create a new user"""
        if username in self.users:
            logger.warning(f"User {username} already exists")
            return None
        
        if scopes is None:
            scopes = ["read"]  # Default scope
        
        new_user = {
            "username": username,
            "email": email,
            "full_name": full_name,
            "hashed_password": pwd_context.hash(password),
            "disabled": disabled,
            "scopes": scopes
        }
        
        self.users[username] = new_user
        self._save_users()
        return UserInDB(**new_user)
    
    def update_user(self, username: str, **kwargs) -> Optional[UserInDB]:
        """Update a user's information"""
        if username not in self.users:
            logger.warning(f"User {username} not found")
            return None
        
        # Handle password updates specially to hash them
        if "password" in kwargs:
            kwargs["hashed_password"] = pwd_context.hash(kwargs.pop("password"))
        
        # Update user information
        self.users[username].update(kwargs)
        self._save_users()
        return UserInDB(**self.users[username])
    
    def delete_user(self, username: str) -> bool:
        """Delete a user"""
        if username not in self.users:
            logger.warning(f"User {username} not found")
            return False
        
        del self.users[username]
        self._save_users()
        return True
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify that the password matches the hash"""
        return pwd_context.verify(plain_password, hashed_password)

# Create a singleton instance
user_db = UserDB()

# Function to get a properly initialized user_db
def get_user_db() -> UserDB:
    """Get the user database instance"""
    return user_db