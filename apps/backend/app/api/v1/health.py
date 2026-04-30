"""Health check endpoint (D-14, API-03)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def health() -> dict[str, str]:
    """Liveness probe. Returns {"status": "ok"} with HTTP 200."""
    return {"status": "ok"}
