import os
import sys
import pandas as pd
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# Import setup_paths to configure everything correctly
import setup_paths

# Import necessary modules
from application.modules.file_agent import FileAgent, DataFile

def main():
    """Test database connection and file operations directly"""
    print("Starting database verification...")
    
    # Create a test FileAgent
    file_agent = FileAgent()
    
    # Check database connection
    print("Testing database connection...")
    try:
        count = file_agent.session.query(file_agent.DataFile).count()
        print(f"Database connection successful! Found {count} files.")
    except Exception as e:
        print(f"⚠️ Database connection error: {str(e)}")
        
    # Try to create a test file
    print("\nTesting file creation...")
    try:
        # Create a simple test DataFrame
        data = {
            'name': ['Alice', 'Bob', 'Charlie'],
            'age': [25, 30, 35],
            'department': ['HR', 'IT', 'Finance']
        }
        df = pd.DataFrame(data)
        
        # Store in database
        file_id = file_agent.store_csv_file(
            df=df,
            file_name="test_file.csv",
            file_path="/tmp/test_file.csv",
            original_name="test_file.csv",
            definition="Test Definition",
            task_name="Test Task",
            output=False
        )
        
        print(f"✅ Test file created successfully with ID: {file_id}")
    except Exception as e:
        print(f"⚠️ File creation error: {str(e)}")
    
    # List all files
    print("\nListing all files in database...")
    try:
        files = file_agent.get_all_files()
        print(f"Found {len(files)} files:")
        for i, file in enumerate(files):
            print(f"{i+1}. {file.original_name} ({file.definition}) - {file.row_count} rows")
            
        if not files:
            print("⚠️ No files found in database!")
    except Exception as e:
        print(f"⚠️ Error listing files: {str(e)}")
    
    print("\nDatabase verification complete!")

if __name__ == "__main__":
    main()