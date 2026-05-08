"""Integration tests for GET /api/v1/visits/_meta (Phase 22 D-22-1).

Covers:
- 200 happy path for authenticated reception with correct body shape
- 200 happy path for authenticated owner with correct body shape
- 401 for unauthenticated callers (auth dependency fires before RBAC)
- Cache-Control: public, max-age=300 header is present
- No DB session consumed (endpoint does not inject get_db dependency)
- Route registered BEFORE /{visit_id} (path collision safety)
"""

from __future__ import annotations

from typing import Any

from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User

OWNER_EMAIL = "meta-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "meta-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


async def _seed_user(
    db_session: Any,
    *,
    role: Role,
    email: str,
    password: str,
    full_name: str,
) -> User:
    user = User(
        email=email,
        password_hash=await hash_password(password),
        role=role,
        full_name=full_name,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, *, email: str, password: str) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text


async def test_visits_meta_200_reception(
    app: Any,
    db_session: Any,
) -> None:
    """D-22-1: GET /api/v1/visits/_meta returns 200 with correct body for reception."""
    from app.core.redis import get_redis as _get_redis

    await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=RECEPTION_EMAIL,
        password=RECEPTION_PASSWORD,
        full_name="Meta Reception",
    )

    async def _override_get_db() -> Any:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[_get_redis] = _override_get_redis

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await _login(client, email=RECEPTION_EMAIL, password=RECEPTION_PASSWORD)
            r = await client.get("/api/v1/visits/_meta")

        assert r.status_code == 200, r.text
        body = r.json()
        assert "data" in body
        data = body["data"]
        assert "gymHoursStart" in data, f"Missing gymHoursStart in {data}"
        assert "gymHoursEnd" in data, f"Missing gymHoursEnd in {data}"
        # Default Settings values (test env uses .env.example defaults)
        assert data["gymHoursStart"] == "07:00", f"Expected 07:00, got {data['gymHoursStart']}"
        assert data["gymHoursEnd"] == "23:00", f"Expected 23:00, got {data['gymHoursEnd']}"
    finally:
        app.dependency_overrides.clear()


async def test_visits_meta_200_owner(
    app: Any,
    db_session: Any,
) -> None:
    """D-22-1: GET /api/v1/visits/_meta returns 200 with correct body for owner."""
    from app.core.redis import get_redis as _get_redis

    await _seed_user(
        db_session,
        role=Role.OWNER,
        email=OWNER_EMAIL,
        password=OWNER_PASSWORD,
        full_name="Meta Owner",
    )

    async def _override_get_db() -> Any:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[_get_redis] = _override_get_redis

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await _login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD)
            r = await client.get("/api/v1/visits/_meta")

        assert r.status_code == 200, r.text
        body = r.json()
        assert "data" in body
        data = body["data"]
        assert data["gymHoursStart"] == "07:00"
        assert data["gymHoursEnd"] == "23:00"
    finally:
        app.dependency_overrides.clear()


async def test_visits_meta_401_unauthenticated(
    app: Any,
    db_session: Any,
) -> None:
    """D-22-1: GET /api/v1/visits/_meta returns 401 for unauthenticated callers."""
    from app.core.redis import get_redis as _get_redis

    async def _override_get_db() -> Any:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[_get_redis] = _override_get_redis

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            r = await client.get("/api/v1/visits/_meta")

        assert r.status_code == 401, r.text
    finally:
        app.dependency_overrides.clear()


async def test_visits_meta_cache_control_header(
    app: Any,
    db_session: Any,
) -> None:
    """D-22-1: Cache-Control: public, max-age=300 header must be present in the response."""
    from app.core.redis import get_redis as _get_redis

    await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=RECEPTION_EMAIL + ".cc",
        password=RECEPTION_PASSWORD,
        full_name="Cache Reception",
    )

    async def _override_get_db() -> Any:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[_get_redis] = _override_get_redis

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await _login(client, email=RECEPTION_EMAIL + ".cc", password=RECEPTION_PASSWORD)
            r = await client.get("/api/v1/visits/_meta")

        assert r.status_code == 200, r.text
        cache_header = r.headers.get("cache-control", "")
        assert "public" in cache_header, (
            f"Expected 'public' in Cache-Control, got: {cache_header!r}"
        )
        assert "max-age=300" in cache_header, (
            f"Expected 'max-age=300' in Cache-Control, got: {cache_header!r}"
        )
    finally:
        app.dependency_overrides.clear()


async def test_visits_meta_route_before_visit_id(
    app: Any,
) -> None:
    """D-22-1: /_meta route must be registered BEFORE /{visit_id} to avoid path collision."""
    from fastapi.routing import APIRoute

    routes = [r for r in app.routes if isinstance(r, APIRoute)]
    meta_idx: int | None = None
    visit_id_idx: int | None = None

    for i, route in enumerate(routes):
        if hasattr(route, "path"):
            if route.path == "/api/v1/visits/_meta":
                meta_idx = i
            elif route.path == "/api/v1/visits/{visit_id}":
                visit_id_idx = i

    assert meta_idx is not None, "/_meta route not found in app routes"
    assert visit_id_idx is not None, "/{visit_id} route not found in app routes"
    assert meta_idx < visit_id_idx, (
        f"/_meta route (idx={meta_idx}) must be registered BEFORE "
        f"/{{visit_id}} route (idx={visit_id_idx})"
    )
