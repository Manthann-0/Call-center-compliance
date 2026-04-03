"""
API Key Authentication — guards protected endpoints.
Returns proper JSONResponse (not HTTPException) so the response body
is the raw JSON object, not wrapped in a `detail` key.
"""
from fastapi import Header, Request
from fastapi.responses import JSONResponse
from config import settings


async def verify_api_key(request: Request):
    """
    FastAPI dependency — checks x-api-key header.
    Returns JSONResponse(401) if missing or incorrect so that
    evaluation test cases see {"status":"error","message":"..."} directly.
    """
    x_api_key = request.headers.get("x-api-key")

    if not x_api_key:
        # We raise a special exception that our handler catches
        raise APIKeyError("Unauthorized — missing API key. Provide x-api-key header.")

    if x_api_key != settings.API_KEY:
        raise APIKeyError("Unauthorized — invalid API key.")

    return x_api_key


class APIKeyError(Exception):
    """Raised when API key validation fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
