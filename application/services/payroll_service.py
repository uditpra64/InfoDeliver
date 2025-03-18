import sys
import os
from typing import Tuple, Optional, List, Dict, Any, Union
import logging
from pathlib import Path

# Add project root (InfoDeliver) to path
parent_dir = Path(__file__).resolve().parent.parent.parent  # One level up from application/services
sys.path.insert(0, str(parent_dir))

# Import setup_paths to configure everything consistently
import setup_paths

# Now import with absolute paths
from application.modules.agent_collection import AgentCollection
from application.modules.file_agent import FileAgent

logger = logging.getLogger(__name__)

class PayrollService:
    """
    Service class that handles core payroll processing logic.
    This separates business logic from UI to be usable by both desktop and web interfaces.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the payroll service with configuration.
        
        Args:
            config_path: Path to the configuration file (config.json)
        """
        self.logger = logging.getLogger(__name__)
        
        if not config_path:
            base_path = os.getenv("LLM_EXCEL_BASE_PATH", os.getcwd())
            config_path = os.path.join(base_path, "json", "config.json")
        
        self.config_path = config_path
        self.logger.info(f"Initializing PayrollService with config: {config_path}")
        
        try:
            self.agent_collection = AgentCollection(config_path=config_path)
            self.logger.info("AgentCollection initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize AgentCollection: {str(e)}")
            raise

    def process_message(self, message: str) -> Tuple[Union[str, List[str]], str]:
        """
        Process a user message through the agent collection.
        
        Args:
            message: The user's message text
            
        Returns:
            A tuple containing (response_text, extra_info)
        """
        try:
            self.logger.info(f"Processing message: {message}")
            
            # Call the agent_collection's process_message method
            result = self.agent_collection.process_message(message)
            self.logger.debug(f"Result from agent_collection.process_message: {result}, type: {type(result)}")
            
            # Standardize the return format
            if isinstance(result, tuple):
                # If it's already a tuple, use it directly
                if len(result) == 2:
                    response_text, extra_info = result
                elif len(result) == 1:
                    response_text = result[0]
                    extra_info = ""
                else:
                    # Empty tuple case
                    response_text = "No response received"
                    extra_info = ""
            else:
                # If it's not a tuple, treat the entire result as the response text
                response_text = result
                extra_info = ""
            
            # Handle list responses
            if isinstance(response_text, list):
                response_text = "\n".join(map(str, response_text))
            
            # Ensure both parts are strings
            response_text = str(response_text) if response_text is not None else ""
            extra_info = str(extra_info) if extra_info is not None else ""
            
            self.logger.debug(f"Standardized response: ({response_text}, {extra_info})")
            return response_text, extra_info
        
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            self.logger.exception("Detailed traceback:")
            return f"Error processing your request: {str(e)}", "error"

    def get_current_state(self) -> str:
        """
        Get the current state of the conversation.
        
        Returns:
            The current state as a string
        """
        return self.agent_collection.get_current_state()
    
    def select_task(self, task_name: str) -> bool:
        """
        Select a task by name.
        
        Args:
            task_name: The name of the task to select
            
        Returns:
            True if successful, False otherwise
        """
        return self.agent_collection.set_current_task_agent(task_name)
    
    def get_task_list(self) -> List[str]:
        """
        Get the list of available tasks.
        
        Returns:
            A list of task names
        """
        return self.agent_collection.get_task_list()
    
    def get_task_description(self, task_name: str) -> str:
        """
        Get the description of a specific task.
        
        Args:
            task_name: The name of the task
            
        Returns:
            The task description
        """
        return self.agent_collection.get_task_description(task_name)
    
    def process_files(self) -> Tuple[Union[str, List[str]], str]:
        """
        Process files for the current task.
        
        Returns:
            A tuple containing (response_text, extra_info)
        """
        return self.agent_collection.process_files()
    
    def get_grouped_tasks(self) -> Dict[str, List]:
        """
        Get tasks grouped by their base names.
        
        Returns:
            A dictionary of grouped tasks
        """
        return self.agent_collection.get_grouped_tasks()
    
    def set_date(self, date_str: str) -> Tuple[str, str]:
        """
        Set the processing date.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            A tuple containing (response_text, extra_info)
        """
        if self.agent_collection.get_current_state() == "date":
            return self.agent_collection._process_date_message(date_str)
        return "Can't set date in current state", "error"
    
    def reset(self) -> None:
        """
        Reset the service to its initial state.
        """
        self.agent_collection.reset_all_task_agents()