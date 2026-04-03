"""
Test script for /api/call-analytics endpoint
"""
import requests
import base64
import json

# Configuration
API_URL = "http://localhost:8000/api/call-analytics"
API_KEY = "sk_track3_987654321"
AUDIO_FILE = "dummy.wav"  # Change to your test audio file

def test_call_analytics():
    # Read and encode audio file
    with open(AUDIO_FILE, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    
    # Prepare payload
    payload = {
        "language": "Auto",
        "audioFormat": "mp3",  # or "wav" depending on your file
        "audioBase64": audio_base64
    }
    
    # Make request
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY
    }
    
    print(f"Testing {API_URL}...")
    print(f"Audio file: {AUDIO_FILE}")
    print(f"Payload size: {len(json.dumps(payload))} bytes")
    
    response = requests.post(API_URL, json=payload, headers=headers)
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ SUCCESS!")
        print(f"Status: {data.get('status')}")
        print(f"Summary: {data.get('summary', 'N/A')[:100]}...")
        print(f"SOP Score: {data.get('sop_validation', {}).get('complianceScore', 'N/A')}")
    else:
        print("\n❌ FAILED!")
        print(f"Error: {response.json()}")

if __name__ == "__main__":
    test_call_analytics()
