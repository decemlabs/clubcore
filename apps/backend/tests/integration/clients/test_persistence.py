"""Phase 12.1 regression: every clients write path must call session.commit().

Pre-fix, `app.modules.clients.service` only flushed (to surface IntegrityError) and
relied on something further up the request chain to commit. Nothing did. POST/PATCH/
DELETE returned 201/200/204 to the client, but the row never persisted because
`get_db` exits its `async with session_factory() as session` context without an
explicit commit and SQLAlchemy auto-rolls-back. Auth has always called commit
explicitly; clients was the outlier.

These tests spy on `AsyncSession.commit` so a future regression that strips the
commit call (or buries it behind a wrong code branch) trips loudly. The SAVEPOINT
fixture (`db_session`) translates the spied commit into a nested-transaction
release, so test isolation is preserved and the spy still observes the call.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Тестов",
    "firstName": "Тест",
    "middleName": "Тестович",
    "phone": "+79991110000",
}


class CommitCounter:
    """Count invocations of AsyncSession.commit while delegating to the real impl.

    A plain attribute counter is enough — we only need to assert "≥ 1" per write
    path. Reset between create + patch/delete stages via `.reset()`.
    """

    def __init__(self) -> None:
        self.count = 0

    def reset(self) -> None:
        self.count = 0


@pytest.fixture
def commit_spy(monkeypatch: pytest.MonkeyPatch) -> CommitCounter:
    """Wrap AsyncSession.commit so each call increments a counter, then delegates."""
    counter = CommitCounter()
    real_commit = AsyncSession.commit

    async def counting_commit(self: AsyncSession) -> None:
        counter.count += 1
        await real_commit(self)

    monkeypatch.setattr(AsyncSession, "commit", counting_commit)
    return counter


async def test_create_client_calls_commit(
    authed_client_owner: AsyncClient,
    commit_spy: CommitCounter,
) -> None:
    """create_client must commit so the inserted row survives request scope."""
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json={**VALID_CLIENT, "phone": "+79991110001"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    assert commit_spy.count >= 1, (
        "create_client returned 201 without calling session.commit() — "
        "the inserted row will be rolled back at request scope exit."
    )


async def test_update_client_calls_commit(
    authed_client_owner: AsyncClient,
    commit_spy: CommitCounter,
) -> None:
    """update_client must commit on the changed-fields path (D-09 no-op excluded)."""
    r_create = await authed_client_owner.post(
        "/api/v1/clients",
        json={**VALID_CLIENT, "phone": "+79991110002"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    client_id = r_create.json()["data"]["id"]

    commit_spy.reset()

    r_patch = await authed_client_owner.patch(
        f"/api/v1/clients/{client_id}",
        json={"firstName": "Сергей"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_patch.status_code == 200, r_patch.text
    assert commit_spy.count >= 1, (
        "update_client returned 200 with a real diff but did not call "
        "session.commit() — the mutation will be rolled back at request scope exit."
    )


async def test_delete_client_calls_commit(
    authed_client_owner: AsyncClient,
    commit_spy: CommitCounter,
) -> None:
    """soft_delete_client must commit so deleted_at survives request scope."""
    r_create = await authed_client_owner.post(
        "/api/v1/clients",
        json={**VALID_CLIENT, "phone": "+79991110003"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    client_id = r_create.json()["data"]["id"]

    commit_spy.reset()

    r_delete = await authed_client_owner.delete(
        f"/api/v1/clients/{client_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_delete.status_code == 204, r_delete.text
    assert commit_spy.count >= 1, (
        "soft_delete_client returned 204 without calling session.commit() — "
        "the row's deleted_at flag will be rolled back at request scope exit."
    )


async def test_update_client_noop_does_not_require_commit(
    authed_client_owner: AsyncClient,
    commit_spy: CommitCounter,
) -> None:
    """D-09 no-op PATCH (no fields changed) is allowed to skip commit.

    No-op PATCH returns the current state without flushing or emitting audit;
    by the same token it should not be required to commit. This test pins that
    behaviour so a future change does not accidentally tighten the contract.
    """
    r_create = await authed_client_owner.post(
        "/api/v1/clients",
        json={**VALID_CLIENT, "phone": "+79991110004"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_create.status_code == 201, r_create.text
    client_id = r_create.json()["data"]["id"]

    commit_spy.reset()

    # Empty PATCH body — exclude_unset means zero changed fields.
    r_patch = await authed_client_owner.patch(
        f"/api/v1/clients/{client_id}",
        json={},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_patch.status_code == 200, r_patch.text
    # No assertion on commit_spy.await_count — D-09 explicitly permits skipping.
