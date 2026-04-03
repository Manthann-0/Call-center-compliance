"""
Quick test to verify /api/call-analytics endpoint
"""
import requests
import json

# Test with minimal payload (will fail processing but should not give 405)
API_URL = "http://localhost:8000/api/call-analytics"
API_KEY = "sk_track3_987654321"

payload = {
    "language": "Auto",
    "audioFormat": "mp3",
    "audioBase64": "dGVzdA=="  # Just "test" in base64
}

headers = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY
}

print(f"Testing {API_URL}...")
print(f"Headers: {headers}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(API_URL, json=payload, headers=headers, timeout=10)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 405:
        print("\n❌ 405 ERROR - Method Not Allowed!")
    elif response.status_code == 401:
        print("\n❌ 401 ERROR - Unauthorized (check API key)")
    elif response.status_code in [200, 400, 422, 500]:
        print("\n✅ Endpoint is accessible (not 405)")
    
except requests.exceptions.ConnectionError:
    print("\n❌ Connection failed - is the server running?")
except Exception as e:
    print(f"\n❌ Error: {e}")
