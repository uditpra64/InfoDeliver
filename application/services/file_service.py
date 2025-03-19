import os
import sys
import logging
import shutil
import uuid
import mimetypes
from typing import List, Dict, Optional, Tuple, Any, Union
import pandas as pd
from pathlib import Path
from datetime import datetime
from application.modules.file_agent import FileAgent

# Add project root to path
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Import setup_paths to configure everything consistently
import setup_paths

# Now import with absolute paths
from application.modules.file_agent import FileAgent

logger = logging.getLogger(__name__)

# Custom exceptions for the file service
class FileServiceError(Exception):
    """Base exception for FileService errors."""
    pass

class FileNotFoundError(FileServiceError):
    """Exception when a requested file is not found."""
    pass

class InvalidFileTypeError(FileServiceError):
    """Exception when file type is not supported."""
    pass

class FileSizeLimitExceededError(FileServiceError):
    """Exception when file size exceeds the limit."""
    pass

class FileService:
    """
    Enhanced service class that handles file operations for the payroll application.
    This separates file handling logic from UI to be usable by both desktop and web interfaces.
    """
    
    # Supported file types and their MIME types
    SUPPORTED_FILE_TYPES = {
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel"
    }
    
    # Maximum file size (10MB by default)
    MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "10"))
    
    
    def __init__(self, temp_dir=None):
        """
        Initialize the file service with a FileAgent instance.
        """
        self.logger = logging.getLogger(__name__)
        try:
            self.file_agent = FileAgent()
            self.file_agent.ensure_database_ready()
            
            # Initialize task_configs with an empty dict if it's None
            if self.file_agent.task_configs is None:
                config_path = os.getenv("CONFIG_PATH", os.path.join(os.getenv("LLM_EXCEL_BASE_PATH", ""), "json", "config.json"))
                self.logger.info(f"Loading config from {config_path} for FileAgent")
                
                try:
                    if os.path.exists(config_path):
                        with open(config_path, "r", encoding="utf-8") as f:
                            config = json.load(f)
                            task_configs = {}
                            for task in config.get("タスク", []):
                                task_configs[task["名称"]] = task
                            self.file_agent.task_configs = task_configs
                            self.logger.info(f"Loaded {len(task_configs)} tasks into FileAgent")
                    else:
                        self.file_agent.task_configs = {}
                        self.logger.warning(f"Config file not found at {config_path}, using empty task_configs")
                except Exception as config_error:
                    self.file_agent.task_configs = {}
                    self.logger.error(f"Error loading config: {str(config_error)}")
            
            self.temp_dir = temp_dir or os.path.join(parent_dir, "temp")
            
            # Ensure temp directory exists
            os.makedirs(self.temp_dir, exist_ok=True)
            
            self.logger.info(f"FileService initialized with temp_dir: {self.temp_dir}")
        except Exception as e:
            self.logger.error(f"Failed to initialize FileService: {e}")
            raise
    
    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate a file's existence, size, and type.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Check if file exists
            if not os.path.isfile(file_path):
                return False, f"File not found: {file_path}"
                
            # Validate file size
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                return False, f"File exceeds maximum size of {self.MAX_FILE_SIZE_MB}MB"
            
            # Validate file type
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in self.SUPPORTED_FILE_TYPES:
                return False, f"Unsupported file type: {file_ext}. Supported types: {', '.join(self.SUPPORTED_FILE_TYPES.keys())}"
            
            # For additional security, verify content type
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type not in self.SUPPORTED_FILE_TYPES.values():
                return False, f"File content type {mime_type} does not match expected type for extension {file_ext}"
            
            return True, "File validation successful"
        except Exception as e:
            self.logger.error(f"Error validating file {file_path}: {str(e)}")
            return False, f"Error validating file: {str(e)}"

    def create_file_copy(self, file_path: str) -> str:
        """
        Create a copy of a file in the temp directory with a secure name.
        
        Args:
            file_path: Path to the original file
            
        Returns:
            Path to the copied file
        """
        try:
            # Generate a secure filename with UUID
            file_ext = os.path.splitext(file_path)[1].lower()
            secure_filename = f"{uuid.uuid4()}{file_ext}"
            target_path = os.path.join(self.temp_dir, secure_filename)
            
            # Copy the file
            shutil.copy2(file_path, target_path)
            self.logger.info(f"Created secure copy of {file_path} at {target_path}")
            
            return target_path
        except Exception as e:
            self.logger.error(f"Error creating file copy: {str(e)}")
            raise FileServiceError(f"Error creating file copy: {str(e)}")

    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """
        Upload and process a file.
        """
        try:
            self.logger.info(f"Starting to upload file: {file_path}")
            
            # Validate the file
            is_valid, message = self.validate_file(file_path)
            self.logger.debug(f"File validation result: valid={is_valid}, message={message}")
            
            if not is_valid:
                self.logger.error(message)
                return {"success": False, "message": message}
            
            # Create a secure copy of the file
            self.logger.debug(f"Creating secure copy of file: {file_path}")
            secure_file_path = self.create_file_copy(file_path)
            
            # Check file identity
            self.logger.debug(f"Checking file identity: {secure_file_path}")
            identity_result = self.file_agent.check_file_identity(secure_file_path)
            self.logger.info(f"File identity result: {identity_result}")
            
            # If needed, add more detailed analysis of the identity_result here
            
            # Refresh file list after upload
            self.logger.info(f"Successfully processed file: {os.path.basename(file_path)}")
            return {
                "success": True,
                "file_path": secure_file_path, 
                "file_name": os.path.basename(file_path),
                "identity_result": identity_result,
                "original_path": file_path
            }
        except Exception as e:
            self.logger.error(f"Error uploading file: {str(e)}")
            self.logger.exception("Detailed traceback:")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def read_file_as_dataframe(self, file_path: str) -> pd.DataFrame:
        """
        Read a file and return as pandas DataFrame.
        
        Args:
            file_path: Path to the file
            
        Returns:
            DataFrame containing the file data
        """
        try:
            # Validate the file
            is_valid, message = self.validate_file(file_path)
            if not is_valid:
                raise InvalidFileTypeError(message)
            
            # Read the file based on its extension
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == '.csv':
                return pd.read_csv(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return pd.read_excel(file_path)
            else:
                raise InvalidFileTypeError(f"Unsupported file type: {file_ext}")
        except Exception as e:
            self.logger.error(f"Error reading file as DataFrame: {str(e)}")
            if isinstance(e, FileServiceError):
                raise
            raise FileServiceError(f"Error reading file: {str(e)}")
    
    def get_file_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all stored files.
        
        Returns:
            A list of file information dictionaries
        """
        try:
            self.logger.info("Getting list of all files")
            files = self.file_agent.get_all_files()
            
            # Enhanced logging
            self.logger.debug(f"Raw files from file_agent.get_all_files(): {files}")
            
            result = []
            
            # Handle different return types
            if files:
                for file in files:
                    # Check if file is a DataFile object
                    if hasattr(file, 'id'):
                        result.append({
                            "id": file.id,
                            "name": file.original_name or "Unknown",
                            "task_name": file.task_name or "Manual Upload",
                            "upload_date": file.upload_date.strftime("%Y-%m-%d %H:%M:%S") if hasattr(file.upload_date, 'strftime') else str(file.upload_date),
                            "row_count": file.row_count or 0,
                            "output": file.output or False
                        })
                    # Handle dictionary format
                    elif isinstance(file, dict):
                        result.append({
                            "id": file.get("id", 0),
                            "name": file.get("name", "Unknown"),
                            "task_name": file.get("task_name", "Manual Upload"),
                            "upload_date": file.get("upload_date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                            "row_count": file.get("row_count", 0),
                            "output": file.get("output", False)
                        })
            
            self.logger.debug(f"Processed file list: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error getting file list: {str(e)}")
            self.logger.exception("Detailed traceback:")
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
            if not file_info:
                raise FileNotFoundError(f"File with ID {file_id} not found")
                
            return {
                "id": file_info.id,
                "name": file_info.original_name,
                "definition": file_info.definition,
                "task_name": file_info.task_name,
                "upload_date": file_info.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                "row_count": file_info.row_count,
                "output": file_info.output
            }
        except Exception as e:
            self.logger.error(f"Error getting file info: {str(e)}")
            if isinstance(e, FileServiceError):
                raise
            raise FileServiceError(f"Error getting file info: {str(e)}")
    
    def delete_file(self, file_id: int) -> Dict[str, Any]:
        """
        Delete a file from storage.
        
        Args:
            file_id: The ID of the file to delete
            
        Returns:
            Status information
        """
        try:
            # Check if the file exists first
            file_info = self.file_agent.get_file_info(file_id)
            if not file_info:
                raise FileNotFoundError(f"File with ID {file_id} not found")
                
            self.file_agent.delete_file(file_id)
            self.logger.info(f"Deleted file: {file_id}")
            
            return {
                "success": True, 
                "message": f"File {file_id} deleted successfully"
            }
        except Exception as e:
            self.logger.error(f"Error deleting file: {str(e)}")
            if isinstance(e, FileServiceError):
                raise
            raise FileServiceError(f"Error deleting file: {str(e)}")
    
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
            temp_path = os.path.join(self.temp_dir, f"{uuid.uuid4()}_{original_name}")
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
            
            self.logger.info(f"Stored DataFrame as {file_name} with ID {file_id}")
            return {
                "success": True, 
                "file_id": file_id,
                "message": f"DataFrame stored as {file_name}"
            }
        except Exception as e:
            self.logger.error(f"Error storing DataFrame: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
            
    def cleanup_temp_files(self, hours: int = 24) -> int:
        """
        Delete temporary files older than the specified number of hours.
        
        Args:
            hours: Age threshold in hours
            
        Returns:
            Number of files deleted
        """
        if not os.path.exists(self.temp_dir):
            return 0
            
        count = 0
        try:
            current_time = datetime.now().timestamp()
            for file_name in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, file_name)
                if os.path.isfile(file_path):
                    # Get file modification time
                    file_time = os.path.getmtime(file_path)
                    # If file is older than the threshold, delete it
                    if (current_time - file_time) > (hours * 3600):
                        os.remove(file_path)
                        count += 1
                        self.logger.info(f"Deleted temporary file: {file_path}")
            
            return count
        except Exception as e:
            self.logger.error(f"Error cleaning up temporary files: {str(e)}")
            return count

    def get_files_by_task(self, task_name: str) -> List[Dict[str, Any]]:
        """
        Get files associated with a specific task.
        
        Args:
            task_name: The name of the task
            
        Returns:
            List of file information
        """
        try:
            files = self.file_agent.get_files_by_task(task_name)
            result = []
            
            for file in files:
                result.append({
                    "id": file.id,
                    "name": file.original_name,
                    "definition": file.definition,
                    "task_name": file.task_name,
                    "upload_date": file.upload_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "row_count": file.row_count,
                    "output": file.output
                })
                
            return result
        except Exception as e:
            self.logger.error(f"Error getting files for task {task_name}: {str(e)}")
            return []

# Simple test function
def test_file_service():
    file_service = FileService()
    print("FileService initialized successfully")
    
    # Test file validation
    test_file = "test_file.csv"
    with open(test_file, "w") as f:
        f.write("col1,col2\n1,2\n3,4")
    
    valid, message = file_service.validate_file(test_file)
    print(f"File validation: {valid}, Message: {message}")
    
    # Test file upload
    result = file_service.upload_file(test_file)
    print(f"File upload result: {result}")
    
    # Clean up
    os.remove(test_file)
    file_service.cleanup_temp_files(0)  # Delete all temp files immediately

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    test_file_service()