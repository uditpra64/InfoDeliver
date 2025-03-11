# web_application/test_api.py
import os
import sys
import requests
from pathlib import Path

# Add parent directory to sys.path
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

# Test configuration
API_URL = "http://localhost:8000"

def test_chat_endpoint():
    """Test the chat endpoint"""
    print("Testing chat endpoint...")
    
    # First request to get a session
    response = requests.post(
        f"{API_URL}/chat",
        json={"message": "給与計算を開始"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Chat endpoint working")
        print(f"Response: {data['response']}")
        print(f"Session ID: {data['session_id']}")
        print(f"State: {data['state']}")
        
        # Test using the session ID
        session_id = data['session_id']
        second_response = requests.post(
            f"{API_URL}/chat",
            json={"message": "Hello again", "session_id": session_id},
            headers={"X-Session-ID": session_id}
        )
        
        if second_response.status_code == 200:
            print(f"✅ Session maintained")
        else:
            print(f"❌ Session test failed: {second_response.status_code}")
            print(second_response.text)
    else:
        print(f"❌ Chat endpoint test failed: {response.status_code}")
        print(response.text)

def test_tasks_endpoint():
    """Test the tasks endpoint"""
    print("\nTesting tasks endpoint...")
    
    response = requests.get(f"{API_URL}/tasks")
    
    if response.status_code == 200:
        tasks = response.json()
        print(f"✅ Tasks endpoint working")
        print(f"Found {len(tasks)} tasks")
        for task in tasks:
            print(f"- {task['name']}: {task['description']}")
    else:
        print(f"❌ Tasks endpoint test failed: {response.status_code}")
        print(response.text)

def main():
    """Run API tests"""
    print("Starting API tests...")
    test_chat_endpoint()
    test_tasks_endpoint()
    print("\nTests completed.")

if __name__ == "__main__":
    main()