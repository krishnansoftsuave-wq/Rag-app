import requests
import uuid

BASE_URL = "http://localhost:8000"

def test_oauth_flow():
    print("=== 1. Testing OAuth Server Metadata Discovery ===")
    res = requests.get(f"{BASE_URL}/.well-known/oauth-authorization-server")
    print(f"Status: {res.status_code}")
    print(f"Metadata: {res.json()}")

    unique_user = f"user_{uuid.uuid4().hex[:6]}"
    unique_email = f"{unique_user}@company.com"
    password = "colleague_password_123"

    print(f"\n=== 2. Registering Fresh User '{unique_user}' ===")
    reg_resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json={
        "username": unique_user,
        "email": unique_email,
        "password": password
    })
    print(f"Registration Status: {reg_resp.status_code}")
    print(f"User Registered: {reg_resp.json().get('user')}")

    print("\n=== 3. Obtaining OAuth Access Token ===")
    token_resp = requests.post(f"{BASE_URL}/api/v1/oauth/token", json={
        "grant_type": "password",
        "username": unique_user,
        "password": password
    })
    print(f"Token Endpoint Status: {token_resp.status_code}")
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    print(f"[SUCCESS] Issued OAuth Token for user '{token_data.get('username')}': {access_token[:30]}...")

    print("\n=== 4. Testing MCP SSE Endpoint with OAuth Token ===")
    headers = {"Authorization": f"Bearer {access_token}"}
    sse_resp = requests.get(f"{BASE_URL}/mcp/sse?token={access_token}", headers=headers, stream=True)
    print(f"MCP SSE Connection Status: {sse_resp.status_code}")
    if sse_resp.status_code == 200:
        print("[SUCCESS] OAuth Authenticated MCP SSE Stream Connected successfully!")

if __name__ == "__main__":
    test_oauth_flow()
