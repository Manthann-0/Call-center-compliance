"""
API Key Authentication — guards protected endpoints.
"""
from fastapi import Header, HTTPException
from config import settings


async def verify_api_key(x_api_key: str = Header(None)):
    """
    FastAPI dependency — checks x-api-key header.
    Returns 401 if missing or incorrect.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Unauthorized — missing API key. Provide x-api-key header."},
        )

    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"status": "error", "message": "Unauthorized — invalid API key."},
        )

    return x_api_key
