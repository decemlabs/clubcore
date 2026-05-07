"""BusinessService write-path template (INFRA-13 / D-01..D-05 — Phase 15).

This module is **docstring-only**. It documents the canonical write-path
recipe for ``apps/backend/app/modules/*/service.py`` files. There is NO
runtime construct here — no ``class BusinessService``, no abstract base,
no Mixin, no context-manager. The pattern is enforced by the AST gate at
``apps/backend/tests/unit/test_service_commit_gate.py`` (SVC001).

--------------------------------------------------------------------------
Why this file exists
--------------------------------------------------------------------------

Phase 12.1 incident: ``clients/service.py`` had ``audit.emit(...)`` calls
without ``await session.commit()`` and the bug shipped. ``app/core/database.py``
auto-rolls back the session on request exit if the caller hasn't committed,
so the audit row + mutation were silently discarded. The fix is to ALWAYS
commit at the boundary of a write path.

--------------------------------------------------------------------------
Write-path recipe (the SVC001 invariant)
--------------------------------------------------------------------------

    async def <public_write_function>(session, actor, data) -> Response:
        row = await repository.<insert_or_update_or_delete>(...)
        try:
            await session.flush()    # surface DB constraint errors
        except IntegrityError as exc:
            await session.rollback()
            raise <DomainError> from exc

        await audit.emit(
            session,
            "<event_name>",          # MUST be a literal in LOCKED_AUDIT_EVENTS
            actor_user_id=actor.id,
            resource_type="<rt>",    # MUST be a literal in LOCKED_AUDIT_EVENTS
            resource_id=row.id,
            # ... payload ...
        )
        await session.commit()       # <-- THE invariant the AST gate enforces
        return Response.model_validate(row)

Canonical example: ``apps/backend/app/modules/clients/service.py:create_client``.

--------------------------------------------------------------------------
Write-path detection (what the AST gate considers a "write")
--------------------------------------------------------------------------

A function is a write path if its AST contains ANY of:

  * ``session.add(...)``, ``session.add_all(...)``, ``session.delete(...)``
  * ``session.execute(insert(...))``, ``session.execute(update(...))``,
    ``session.execute(delete(...))``
  * any ``audit.emit(...)`` call (D-05 — the audit row enrolls in the
    caller's transaction; missing the commit is the Phase 12.1 bug)

The function MUST contain a literal ``await session.commit()`` call somewhere
in its body (``try``/``except``/``async with`` branches count) — OR carry the
opt-out marker described below.

--------------------------------------------------------------------------
Opt-out: ``# noqa: SVC001 caller-owns-txn``
--------------------------------------------------------------------------

Place the marker on the ``def`` line of a private helper that intentionally
leaves the commit to its caller::

    async def _atomic_inner(session, ...) -> ...:  # noqa: SVC001 caller-owns-txn
        session.add(...)
        await audit.emit(...)
        # NO commit — outer function commits both insert + audit atomically

The marker is VALID ONLY on private helpers (name starts with ``_``). A
public function in ``service.py`` carrying ``# noqa: SVC001`` is itself a
failure: public service functions MUST commit themselves so callers
(routers, ARQ workers, bot handlers) can trust the boundary.

--------------------------------------------------------------------------
Read-only / pure helpers
--------------------------------------------------------------------------

Read-only public helpers (e.g. ``resolve_active_membership_by_client``)
trivially pass the gate because they contain no mutating call AND no
``audit.emit``. No marker needed.

--------------------------------------------------------------------------
Module shape: free functions, NOT classes
--------------------------------------------------------------------------

``service.py`` files are flat modules of ``async def`` free functions.
Phase 15 explicitly does NOT introduce a runtime ``BusinessService`` class.
The pattern lives in this docstring + the AST gate; the discipline is
structural, not syntactic.

--------------------------------------------------------------------------
See also
--------------------------------------------------------------------------

- ``apps/backend/app/modules/clients/service.py:create_client`` (canonical)
- ``apps/backend/app/core/audit.py`` (LOCKED_AUDIT_EVENTS + emit guard)
- ``apps/backend/tests/unit/test_service_commit_gate.py`` (the AST gate)
- ``apps/backend/app/core/database.py`` (lifespan rollback semantics)
"""
