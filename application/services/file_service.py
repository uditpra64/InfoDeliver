import os
import logging
from typing import List, Dict, Optional, Tuple, Any
import pandas as pd

import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.append(str(parent_dir))

from modules.file_agent import FileAgent



logger = logging.getLogger(__name__)

class FileService:
    """
    Service class that handles file operations for the payroll application.
    This separates file handling logic from UI to be usable by both desktop and web interfaces.
    """
    
    def __init__(self):
        """Initialize the file service with a FileAgent instance."""
        self.logger = logging.getLogger(__name__)
        self.file_agent = FileAgent()
        self.logger.info("FileService initialized")
    
    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """
        Upload and process a file.
        
        Args:
            file_path: Path to the file to upload
            
        Returns:
            A dictionary with upload status information
        """
        try:
            if not os.path.isfile(file_path):
                self.logger.error(f"File not found: {file_path}")
                return {"success": False, "message": "File not found"}
                
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in ['.csv', '.xlsx']:
                self.logger.error(f"Unsupported file type: {file_ext}")
                return {"success": False, "message": "Only CSV and Excel files are supported"}
            
            # Check file identity to determine what type of file this is
            identity_result = self.file_agent.check_file_identity(file_path)
            
            return {
                "success": True,
                "file_path": file_path, 
                "file_name": os.path.basename(file_path),
                "identity_result": identity_result
            }
            
        except Exception as e:
            self.logger.error(f"Error uploading file: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def get_file_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all stored files.
        
        Returns:
            A list of file information dictionaries
        """
        try:
            return self.file_agent.get_all_files()
        except Exception as e:
            self.logger.error(f"Error getting file list: {str(e)}")
            return []
    
    def get_file_by_id(self, file_id: int) -> Dict[str, Any]:
        """
        Get information about a specific file.
        
        Args:
            file_id: The ID of the file
            
        Returns:
            File information
        """
        try:
            file_info = self.file_agent.get_file_info(file_id)
            if file_info:
                return {
                    "id": file_info.id,
                    "name": file_info.original_name,
                    "definition": file_info.definition,
                    "task_name": file_info.task_name,
                    "upload_date": file_info.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "row_count": file_info.row_count
                }
            return {"success": False, "message": f"File with ID {file_id} not found"}
        except Exception as e:
            self.logger.error(f"Error getting file info: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def delete_file(self, file_id: int) -> Dict[str, Any]:
        """
        Delete a file from storage.
        
        Args:
            file_id: The ID of the file to delete
            
        Returns:
            Status information
        """
        try:
            self.file_agent.delete_file(file_id)
            return {"success": True, "message": f"File {file_id} deleted successfully"}
        except Exception as e:
            self.logger.error(f"Error deleting file: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def store_dataframe(self, 
                       df: pd.DataFrame, 
                       file_name: str,
                       original_name: str,
                       definition: str, 
                       task_name: Optional[str] = None,
                       output: bool = False) -> Dict[str, Any]:
        """
        Store a pandas DataFrame in the database.
        
        Args:
            df: The DataFrame to store
            file_name: Internal name for the file
            original_name: Original filename
            definition: File definition
            task_name: Associated task name
            output: Whether this is an output file
            
        Returns:
            Status information
        """
        try:
            # Create a temporary file path
            temp_path = os.path.join(os.getcwd(), "temp", original_name)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            file_id = self.file_agent.store_csv_file(
                df=df,
                file_name=file_name,
                file_path=temp_path, 
                original_name=original_name,
                definition=definition,
                task_name=task_name,
                output=output
            )
            
            return {
                "success": True, 
                "file_id": file_id,
                "message": f"DataFrame stored as {file_name}"
            }
        except Exception as e:
            self.logger.error(f"Error storing DataFrame: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}