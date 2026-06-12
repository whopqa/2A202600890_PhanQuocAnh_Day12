"""API key authentication for the production agent."""
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

try:
    from Lab_Assigment.app.config import settings
except ModuleNotFoundError:
    from app.config import settings  # type: ignore[no-redef]


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key.",
        )
    return api_key
