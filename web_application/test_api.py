import requests
import json
import time
from colorama import init, Fore, Style

# Initialize colorama for colored terminal output
init()

# Base API URL
BASE_URL = "http://localhost:8000"

# Test session ID to use in requests
TEST_SESSION_ID = None  # Will be set during testing

def print_header(message):
    """Print a section header"""
    print(f"\n{Fore.BLUE}{'=' * 80}")
    print(f"{message.center(80)}")
    print(f"{'=' * 80}{Style.RESET_ALL}\n")

def print_result(test_name, success, response=None, error=None):
    """Print the result of a test"""
    if success:
        status = f"{Fore.GREEN}PASS{Style.RESET_ALL}"
    else:
        status = f"{Fore.RED}FAIL{Style.RESET_ALL}"
    
    print(f"{status} - {test_name}")
    
    if not success and error:
        print(f"  {Fore.RED}Error: {error}{Style.RESET_ALL}")
    
    if response:
        # Try to format as JSON if possible
        if isinstance(response, dict) or isinstance(response, list):
            try:
                formatted_response = json.dumps(response, indent=2)
                print(f"  Response: {formatted_response}")
            except:
                print(f"  Response: {response}")
        else:
            print(f"  Response: {response}")

def get_token(username, password, scope=None):
    """Get an authentication token for the specified user"""
    data = {
        "username": username,
        "password": password
    }
    
    if scope:
        data["scope"] = scope
    
    response = requests.post(
        f"{BASE_URL}/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    if response.status_code == 200:
        token_data = response.json()
        return token_data.get("access_token")
    else:
        print(f"{Fore.RED}Failed to get token for {username}: {response.text}{Style.RESET_ALL}")
        return None

def test_endpoint(method, endpoint, expected_status, token=None, session_id=None, data=None, files=None, form_data=None):
    """Test an API endpoint with specified parameters"""
    headers = {"accept": "application/json"}
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if session_id:
        headers["x-session-id"] = session_id
    
    kwargs = {"headers": headers}
    
    if data:
        kwargs["json"] = data
    
    if files:
        kwargs["files"] = files

    if form_data:
        kwargs["data"] = form_data
    
    response = requests.request(method, f"{BASE_URL}{endpoint}", **kwargs)
    
    success = response.status_code == expected_status
    response_data = None
    error = None
    
    try:
        response_data = response.json()
    except:
        response_data = response.text
        
    if not success:
        error = f"Expected status {expected_status}, got {response.status_code}"
    
    return success, response_data, error

def run_tests():
    """Run all API tests"""
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0
    }
    
    print_header("API TESTING SCRIPT")
    
    # Step 1: Get tokens for admin and user
    print_header("TOKEN ACQUISITION")
    
    admin_token = get_token("admin", "password")
    if not admin_token:
        print(f"{Fore.RED}Cannot proceed without admin token{Style.RESET_ALL}")
        return
    
    print(f"{Fore.GREEN}✓ Admin token acquired{Style.RESET_ALL}")
    
    user_token = get_token("user", "password")
    if not user_token:
        print(f"{Fore.RED}Cannot proceed without user token{Style.RESET_ALL}")
        return
    
    print(f"{Fore.GREEN}✓ User token acquired{Style.RESET_ALL}")
    
    # Step 2: Test health endpoint (public)
    print_header("PUBLIC ENDPOINTS")
    
    success, response, error = test_endpoint("GET", "/health", 200)
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Health check endpoint", success, response, error)
    
    # Step 3: Create a session and store its ID
    print_header("SESSION MANAGEMENT")
    
    # Create a session through a chat message
    success, response, error = test_endpoint(
        "POST", 
        "/chat", 
        200, 
        data={"message": "Hello"}
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
        # Extract session ID from response
        if isinstance(response, dict) and "data" in response and "session_id" in response["data"]:
            global TEST_SESSION_ID
            TEST_SESSION_ID = response["data"]["session_id"]
            print(f"{Fore.GREEN}✓ Session created, ID: {TEST_SESSION_ID}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠ Session created but couldn't extract session ID{Style.RESET_ALL}")
    else:
        results["failed"] += 1
    print_result("Create session via chat", success, response, error)
    
    # Step 4: Test admin-only endpoints
    print_header("ADMIN ENDPOINTS WITH PROPER AUTHORIZATION")
    
    # Test admin sessions endpoint with admin token (should succeed)
    success, response, error = test_endpoint(
        "GET", 
        "/admin/sessions", 
        200, 
        token=admin_token
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Admin sessions endpoint with admin token", success, response, error)
    
    print_header("ADMIN ENDPOINTS WITH INSUFFICIENT AUTHORIZATION")
    
    # Test admin sessions endpoint with user token (should fail)
    success, response, error = test_endpoint(
        "GET", 
        "/admin/sessions", 
        403, 
        token=user_token
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Admin sessions endpoint with user token (should fail with 403)", success, response, error)
    
    # Test admin sessions endpoint with no token (should fail)
    success, response, error = test_endpoint(
        "GET", 
        "/admin/sessions", 
        401
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Admin sessions endpoint with no token (should fail with 401)", success, response, error)
    
    # Step 5: Test read-only endpoints
    print_header("READ ENDPOINTS")
    
    # Test tasks endpoint with user token (should succeed)
    success, response, error = test_endpoint(
        "GET", 
        "/tasks", 
        200, 
        token=user_token
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Tasks endpoint with user token", success, response, error)
    
    # Test tasks endpoint with no token (should fail)
    success, response, error = test_endpoint(
        "GET", 
        "/tasks", 
        401
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Tasks endpoint with no token (should fail with 401)", success, response, error)
    
    # Only test session history if we have a session ID
    if TEST_SESSION_ID:
        # Test session history with user token (should succeed)
        success, response, error = test_endpoint(
            "GET", 
            f"/session/{TEST_SESSION_ID}/history", 
            200, 
            token=user_token
        )
        results["total"] += 1
        if success:
            results["passed"] += 1
        else:
            results["failed"] += 1
        print_result(f"Session history with user token", success, response, error)
    
    # Step 6: Test write endpoints
    print_header("WRITE ENDPOINTS")
    
    # Test session reset with admin token (should succeed)
    if TEST_SESSION_ID:
        success, response, error = test_endpoint(
            "POST", 
            f"/session/{TEST_SESSION_ID}/reset", 
            200, 
            token=admin_token
        )
        results["total"] += 1
        if success:
            results["passed"] += 1
        else:
            results["failed"] += 1
        print_result("Session reset with admin token", success, response, error)
    
        # Test session reset with user token (should fail)
        success, response, error = test_endpoint(
            "POST", 
            f"/session/{TEST_SESSION_ID}/reset", 
            403, 
            token=user_token
        )
        results["total"] += 1
        if success:
            results["passed"] += 1
        else:
            results["failed"] += 1
        print_result("Session reset with user token (should fail with 403)", success, response, error)
    
    # Testing chat with various tokens
    print_header("CHAT ENDPOINTS")
    
    # Chat with admin token
    success, response, error = test_endpoint(
        "POST", 
        "/chat", 
        200, 
        token=admin_token,
        data={"message": "Hello from admin"}
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Chat with admin token", success, response, error)
    
    # Chat with user token
    success, response, error = test_endpoint(
        "POST", 
        "/chat", 
        200, 
        token=user_token,
        data={"message": "Hello from user"}
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Chat with user token", success, response, error)
    
    # Chat with no token (depends on your implementation if this should work)
    success, response, error = test_endpoint(
        "POST", 
        "/chat", 
        200,  # or 401 if chat requires authentication
        data={"message": "Hello with no auth"}
    )
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print_result("Chat with no token", success, response, error)
    
    # Print summary
    print_header("TEST SUMMARY")
    print(f"Total tests: {results['total']}")
    print(f"{Fore.GREEN}Passed: {results['passed']}{Style.RESET_ALL}")
    print(f"{Fore.RED}Failed: {results['failed']}{Style.RESET_ALL}")
    
    if results["failed"] == 0:
        print(f"\n{Fore.GREEN}All tests passed! Your API authorization is working correctly.{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}Some tests failed. Review the results above for details.{Style.RESET_ALL}")

if __name__ == "__main__":
    run_tests()