"""
IOlabs AI SDR Platform — FastAPI Dependencies
Auth header validation and DB session injection per request.
Implemented in Step 14.
"""

from fastapi import Header, HTTPException, status
import os


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Validate the internal API key on all admin + trigger endpoints."""
    expected = os.environ.get("API_SECRET_KEY", "")
    if not expected or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return x_api_key
