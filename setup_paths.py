# setup_paths.py
import sys
import os
from pathlib import Path

# Add the project root and application directory to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Set environment variable
os.environ["LLM_EXCEL_BASE_PATH"] = str(project_root)

# Create data directory if it doesn't exist
data_dir = os.path.join(project_root, "data")
os.makedirs(data_dir, exist_ok=True)

print(f"Python paths configured:")
print(f"- Added {project_root} to sys.path")
print(f"- Set LLM_EXCEL_BASE_PATH={project_root}")
print(f"- Ensured data directory exists: {data_dir}")

rule_dir = os.path.join(project_root, "rule")
os.makedirs(rule_dir, exist_ok=True)
print(f"- Ensured rule directory exists: {rule_dir}")