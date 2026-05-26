"""Health check endpoint (D-14, API-03)."""

from fastapi import APIRouter

# Phase 64 FRZ-03 / D-64-TAG-INTERNAL — liveness probe tagged Internal so
# Redocly preview does not create a "default" folder for untagged operations.
router = APIRouter(tags=["Internal"])


@router.get("/healthz")
async def health() -> dict[str, str]:
    """Liveness probe. Returns {"status": "ok"} with HTTP 200."""
    return {"status": "ok"}
