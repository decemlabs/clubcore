"""Auth module router.

TODO Phase C+: add /login, /refresh, /logout endpoints.
Phase A: empty router so app/api/v1/router.py can `from app.modules.auth.router import router`
when the first endpoint lands. Currently commented out at the include site (D-02).
"""

from fastapi import APIRouter

router = APIRouter()
# TODO Phase C+: add endpoints here, e.g.
# @router.post("/login")
# async def login(...): ...
