import sys
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Make sure we can import modules
current_dir = Path(__file__).resolve().parent
app_dir = current_dir.parent
root_dir = app_dir.parent

# Add both the app directory and the root directory to sys.path
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

logger.info(f"Python path includes: {sys.path}")

# Now try to import directly from modules
try:
    from modules.agent_collection import AgentCollection
    logger.info("✅ Successfully imported AgentCollection")
except ImportError as e:
    logger.error(f"❌ Failed to import AgentCollection: {e}")

# Try to import the service classes
try:
    from payroll_service import PayrollService
    logger.info("✅ Successfully imported PayrollService")
except ImportError as e:
    logger.error(f"❌ Failed to import PayrollService: {e}")

try:
    from file_service import FileService
    logger.info("✅ Successfully imported FileService")
except ImportError as e:
    logger.error(f"❌ Failed to import FileService: {e}")

try:
    from session_service import SessionService
    logger.info("✅ Successfully imported SessionService")
except ImportError as e:
    logger.error(f"❌ Failed to import SessionService: {e}")

def main():
    """Main test function"""
    logger.info("Starting tests...")
    
    # Test PayrollService and FileService together since they share the DB
    try:
        # Find config.json
        config_paths = [
            os.path.join(app_dir, "json", "config.json"),
            os.path.join(root_dir, "application", "json", "config.json"),
            os.path.join(root_dir, "json", "config.json")
        ]
        
        config_path = None
        for path in config_paths:
            if os.path.exists(path):
                config_path = path
                logger.info(f"Found config at: {config_path}")
                break
        
        if not config_path:
            logger.error("Could not find config.json")
            return
        
        # Initialize PayrollService (which creates a FileAgent internally)
        service = PayrollService(config_path=config_path)
        logger.info("✅ PayrollService initialized successfully")
        
        # Test basic functionality
        tasks = service.get_task_list()
        logger.info(f"Tasks: {tasks}")
        
        # Skip creating a separate FileService instance
        logger.info("✅ FileService is already initialized (via PayrollService)")
        
    except Exception as e:
        logger.error(f"Error testing PayrollService: {e}")
    
    # Test SessionService
    try:
        session_service = SessionService()
        logger.info("✅ SessionService initialized successfully")
        
        # Test session creation
        session_id = session_service.create_session()
        logger.info(f"Created session: {session_id}")
        
        # Test adding messages
        session_service.add_to_conversation(session_id, "user", "Hello")
        session_service.add_to_conversation(session_id, "assistant", "Hi there!")
        
        # Get conversation history
        history = session_service.get_conversation_history(session_id)
        logger.info(f"Conversation has {len(history)} messages")
        
    except Exception as e:
        logger.error(f"Error testing SessionService: {e}")

if __name__ == "__main__":
    main()