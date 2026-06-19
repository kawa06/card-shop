import httpx
import random
import string

BASE_URL = "http://127.0.0.1:8000"

def test_openapi():
    response = httpx.get(f"{BASE_URL}/api/openapi.json")
    if response.status_code != 200:
        print(f"OpenAPI check failed: {response.status_code}")
        return False
    data = response.json()
    paths = data.get("paths", {})
    required = ["/api/translate", "/api/auth/register", "/api/auth/login"]
    for r in required:
        if r not in paths:
            print(f"Missing path: {r}")
            return False
    print("✓ OpenAPI check passed")
    return True

def test_translate():
    payload = {
        "texts": ["こんにちは"],
        "target": "EN"
    }
    response = httpx.post(f"{BASE_URL}/api/translate", json=payload)
    if response.status_code != 200:
        print(f"Translate API failed: {response.status_code}")
        return False
    print("✓ Translate API check passed")
    return True

def test_register():
    rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    email = f"test_{rand_str}@example.com"
    payload = {
        "email": email,
        "name": "Test User",
        "password": "password123"
    }
    response = httpx.post(f"{BASE_URL}/api/auth/register", json=payload)
    if response.status_code != 201:
        print(f"Register API failed: {response.status_code} - {response.text}")
        return False
    print(f"✓ Register API check passed for {email}")
    return True

if __name__ == "__main__":
    success = True
    success &= test_openapi()
    success &= test_translate()
    success &= test_register()
    if success:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed.")
