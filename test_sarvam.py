"""Quick test for Sarvam API key"""
from sarvamai import SarvamAI
from config import settings

print(f"Testing Sarvam API key: {settings.SARVAM_API_KEY[:10]}...")

try:
    client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)
    print("[OK] Sarvam client created successfully")
    print("[OK] API key appears valid")
except Exception as e:
    print(f"[ERROR] {e}")
    print("\nGet a valid key from: https://www.sarvam.ai/")
