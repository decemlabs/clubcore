"""Plan 51-06 D-51-15 / Plan 52-05 D-52-11 — post-commit enqueue seam structural gate.

Replaces Plan 50-04 W-2 stub gate (``body is only _log.info``).

Tautology-resistant AST-level inspection of ``_post_commit_enqueue``'s body.
The previous Phase 50 gate (``test_post_commit_enqueue_body_is_only_log_info``)
asserted the body was a single ``_log.info(...)`` call. Plan 51-06 flips that
in-place: the body must contain (a) the log call AND (b) a guarded
``await arq_pool.enqueue_job("dispatch_fiscal_receipt", ...)`` enqueue.

Plan 52-05 (D-52-11, this update) extends the gate again in lockstep with the
production body change: the body now MUST contain (a) the log call AND (b) the
fiscal-dispatch guard AND (c) a notification guard
``await arq_pool.enqueue_job("dispatch_payment_notification", ...)`` — three
non-docstring statements total.

Why the runtime-spy approach in the original revision was tautological is
preserved in the docstring history: the Phase 50 handler passed
``arq_pool=None`` positionally to ``_post_commit_enqueue``, so any spy
mounted on ``app.state.arq_pool`` was never reached. The AST gate inspects
function source directly, so it catches structural drift regardless of
runtime call paths — that property carries forward into Phase 51 and 52.
"""

import ast
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

# parents[0]=webhook_yookassa, [1]=integration, [2]=tests, [3]=backend.
# The handlers.py path is reachable from the backend root via
# app/api/v1/_internal/yookassa/handlers.py.
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_HANDLERS_PATH = _BACKEND_ROOT / "app" / "api" / "v1" / "_internal" / "yookassa" / "handlers.py"


def _load_post_commit_enqueue_fn() -> ast.AsyncFunctionDef:
    src = _HANDLERS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "_post_commit_enqueue"
        ),
        None,
    )
    assert fn is not None, "_post_commit_enqueue must exist in handlers.py"
    return fn


def _non_docstring_body(fn: ast.AsyncFunctionDef) -> list[ast.stmt]:
    return [
        s
        for s in fn.body
        if not (
            isinstance(s, ast.Expr)
            and isinstance(s.value, ast.Constant)
            and isinstance(s.value.value, str)
        )
    ]


def test_post_commit_enqueue_dispatches_fiscal_receipt() -> None:
    """Phase 51 D-51-15 / Phase 52 D-52-11 — body MUST be (a) a ``_log.info``
    call AND (b) a guarded ``await arq_pool.enqueue_job('dispatch_fiscal_receipt',
    ...)`` AND (c) a guarded ``await arq_pool.enqueue_job(
    'dispatch_payment_notification', ...)``.

    Tautology-resistant structural gate. The test inspects the function's
    AST directly, so it fails on any structural drift away from the locked
    3-statement shape — even if the function signature still accepts
    ``fiscal_receipt_id`` / ``payment_id`` / ``kind``. This is what carries
    the invariant forward so any future branch addition also requires a
    lockstep gate update (PATTERNS.md errata #3 / D-52-11).
    """
    fn = _load_post_commit_enqueue_fn()
    body = _non_docstring_body(fn)
    assert len(body) == 3, (
        "Phase 52 _post_commit_enqueue must call _log.info AND conditionally "
        "enqueue dispatch_fiscal_receipt AND conditionally enqueue "
        f"dispatch_payment_notification; got {len(body)} non-docstring "
        f"statements: {[ast.unparse(s) for s in body]}"
    )

    # Statement 1: Expr wrapping a Call to _log.info(...).
    log_stmt = body[0]
    assert isinstance(log_stmt, ast.Expr), (
        "Phase 52 _post_commit_enqueue body[0] must be an Expr wrapping a Call; "
        f"got {ast.dump(log_stmt)}"
    )
    assert isinstance(log_stmt.value, ast.Call), (
        f"Phase 52 _post_commit_enqueue body[0] must wrap a Call; got {ast.dump(log_stmt.value)}"
    )
    log_target = ast.unparse(log_stmt.value.func)
    assert log_target == "_log.info", (
        f"Phase 52 _post_commit_enqueue body[0] must call _log.info; got {log_target}"
    )

    # Statement 2: fiscal If whose test is BoolOp(And, [IsNot None, IsNot None]).
    fiscal_if = body[1]
    assert isinstance(fiscal_if, ast.If), (
        "Phase 52 _post_commit_enqueue body[1] must be an If guard (fiscal branch); "
        f"got {ast.dump(fiscal_if)}"
    )
    assert isinstance(fiscal_if.test, ast.BoolOp) and isinstance(fiscal_if.test.op, ast.And), (
        "Phase 52 _post_commit_enqueue fiscal if-guard must be a BoolOp(And, ...); "
        f"got {ast.dump(fiscal_if.test)}"
    )
    fiscal_bool_values = fiscal_if.test.values
    assert len(fiscal_bool_values) == 2, (
        f"Phase 52 _post_commit_enqueue fiscal if-guard must combine exactly 2 "
        f"clauses (arq_pool is not None AND fiscal_receipt_id is not None); "
        f"got {len(fiscal_bool_values)}"
    )
    for clause in fiscal_bool_values:
        assert isinstance(clause, ast.Compare), (
            f"fiscal if-guard clause must be a Compare; got {ast.dump(clause)}"
        )
        assert len(clause.ops) == 1 and isinstance(clause.ops[0], ast.IsNot), (
            f"fiscal if-guard clause must use ``is not``; got {ast.dump(clause.ops[0])}"
        )
        assert (
            len(clause.comparators) == 1
            and isinstance(clause.comparators[0], ast.Constant)
            and clause.comparators[0].value is None
        ), f"fiscal if-guard clause must compare against None; got {ast.dump(clause)}"
    fiscal_guard_names = {ast.unparse(c.left) for c in fiscal_bool_values}  # type: ignore[union-attr]
    assert fiscal_guard_names == {"arq_pool", "fiscal_receipt_id"}, (
        f"fiscal if-guard must combine arq_pool + fiscal_receipt_id; got {fiscal_guard_names}"
    )

    # fiscal If.body: single Expr wrapping an Await of arq_pool.enqueue_job(...).
    fiscal_inner = fiscal_if.body
    assert len(fiscal_inner) == 1, (
        f"Phase 52 _post_commit_enqueue fiscal if-body must have exactly 1 statement; "
        f"got {len(fiscal_inner)}"
    )
    fiscal_enq_stmt = fiscal_inner[0]
    assert isinstance(fiscal_enq_stmt, ast.Expr) and isinstance(fiscal_enq_stmt.value, ast.Await), (
        f"fiscal if-body must be Expr(Await(Call(...))); got {ast.dump(fiscal_enq_stmt)}"
    )
    fiscal_await_val = fiscal_enq_stmt.value.value
    assert isinstance(fiscal_await_val, ast.Call), (
        f"fiscal awaited expression must be a Call; got {ast.dump(fiscal_await_val)}"
    )
    fiscal_enq_target = ast.unparse(fiscal_await_val.func)
    assert fiscal_enq_target == "arq_pool.enqueue_job", (
        f"fiscal if-body must call arq_pool.enqueue_job; got {fiscal_enq_target}"
    )
    assert len(fiscal_await_val.args) >= 1, (
        f"fiscal enqueue_job must receive at least the task name; got {fiscal_await_val.args}"
    )
    fiscal_first_arg = fiscal_await_val.args[0]
    assert (
        isinstance(fiscal_first_arg, ast.Constant)
        and isinstance(fiscal_first_arg.value, str)
        and fiscal_first_arg.value == "dispatch_fiscal_receipt"
    ), (
        "fiscal first enqueue_job argument must be the literal "
        f"'dispatch_fiscal_receipt'; got {ast.dump(fiscal_first_arg)}"
    )
    fiscal_kw_map: dict[str, ast.expr] = {
        kw.arg: kw.value for kw in fiscal_await_val.keywords if kw.arg
    }
    assert "_max_tries" in fiscal_kw_map, "fiscal enqueue_job must pass _max_tries"
    assert "_expires" in fiscal_kw_map, "fiscal enqueue_job must pass _expires"
    fiscal_max_tries = fiscal_kw_map["_max_tries"]
    fiscal_expires = fiscal_kw_map["_expires"]
    assert isinstance(fiscal_max_tries, ast.Constant) and fiscal_max_tries.value == 3, (
        f"fiscal _max_tries must be the literal 3; got {ast.dump(fiscal_max_tries)}"
    )
    assert isinstance(fiscal_expires, ast.Constant) and fiscal_expires.value == 60, (
        f"fiscal _expires must be the literal 60; got {ast.dump(fiscal_expires)}"
    )

    # Statement 3: notification If whose test is BoolOp(And, [..., ..., ...]).
    notif_if = body[2]
    assert isinstance(notif_if, ast.If), (
        "Phase 52 _post_commit_enqueue body[2] must be an If guard (notification branch); "
        f"got {ast.dump(notif_if)}"
    )
    assert isinstance(notif_if.test, ast.BoolOp) and isinstance(notif_if.test.op, ast.And), (
        "Phase 52 _post_commit_enqueue notification if-guard must be a BoolOp(And, ...); "
        f"got {ast.dump(notif_if.test)}"
    )
    notif_bool_values = notif_if.test.values
    assert len(notif_bool_values) == 3, (
        f"Phase 52 _post_commit_enqueue notification if-guard must combine exactly 3 "
        f"clauses (arq_pool, payment_id, kind are not None); "
        f"got {len(notif_bool_values)}"
    )
    for clause in notif_bool_values:
        assert isinstance(clause, ast.Compare), (
            f"notification if-guard clause must be a Compare; got {ast.dump(clause)}"
        )
        assert len(clause.ops) == 1 and isinstance(clause.ops[0], ast.IsNot), (
            f"notification if-guard clause must use ``is not``; got {ast.dump(clause.ops[0])}"
        )
        assert (
            len(clause.comparators) == 1
            and isinstance(clause.comparators[0], ast.Constant)
            and clause.comparators[0].value is None
        ), f"notification if-guard clause must compare against None; got {ast.dump(clause)}"
    notif_guard_names = {ast.unparse(c.left) for c in notif_bool_values}  # type: ignore[union-attr]
    assert notif_guard_names == {"arq_pool", "payment_id", "kind"}, (
        f"notification if-guard must combine arq_pool + payment_id + kind; got {notif_guard_names}"
    )

    # notification If.body: single Expr wrapping an Await of arq_pool.enqueue_job(...).
    notif_inner = notif_if.body
    assert len(notif_inner) == 1, (
        f"Phase 52 _post_commit_enqueue notification if-body must have exactly 1 statement; "
        f"got {len(notif_inner)}"
    )
    notif_enq_stmt = notif_inner[0]
    assert isinstance(notif_enq_stmt, ast.Expr) and isinstance(notif_enq_stmt.value, ast.Await), (
        f"notification if-body must be Expr(Await(Call(...))); got {ast.dump(notif_enq_stmt)}"
    )
    notif_await_val = notif_enq_stmt.value.value
    assert isinstance(notif_await_val, ast.Call), (
        f"notification awaited expression must be a Call; got {ast.dump(notif_await_val)}"
    )
    notif_enq_target = ast.unparse(notif_await_val.func)
    assert notif_enq_target == "arq_pool.enqueue_job", (
        f"notification if-body must call arq_pool.enqueue_job; got {notif_enq_target}"
    )
    # Notification uses _kwargs= (not a positional task name), so check keyword args.
    notif_kw_map: dict[str, ast.expr] = {
        kw.arg: kw.value for kw in notif_await_val.keywords if kw.arg
    }
    assert "_kwargs" in notif_kw_map, (
        "notification enqueue_job must pass _kwargs={'payment_id': ..., 'kind': ...}"
    )
    assert "_max_tries" in notif_kw_map, "notification enqueue_job must pass _max_tries"
    assert "_expires" in notif_kw_map, "notification enqueue_job must pass _expires"
    notif_max_tries = notif_kw_map["_max_tries"]
    notif_expires = notif_kw_map["_expires"]
    assert isinstance(notif_max_tries, ast.Constant) and notif_max_tries.value == 3, (
        f"notification _max_tries must be the literal 3; got {ast.dump(notif_max_tries)}"
    )
    assert isinstance(notif_expires, ast.Constant) and notif_expires.value == 60, (
        f"notification _expires must be the literal 60; got {ast.dump(notif_expires)}"
    )
    # The task name for notification is passed as the first positional arg OR via
    # the function call's first arg — check that no positional arg is 'dispatch_fiscal_receipt'
    # (guard against accidentally calling the wrong task).
    notif_positional_args = notif_await_val.args
    assert not any(
        isinstance(a, ast.Constant) and a.value == "dispatch_fiscal_receipt"
        for a in notif_positional_args
    ), (
        "notification enqueue_job must NOT call dispatch_fiscal_receipt "
        "(must call dispatch_payment_notification)"
    )
    # The notification task name should appear as the first positional arg if present,
    # or verified via _kwargs structure. Check first positional arg if present.
    if notif_positional_args:
        notif_first_arg = notif_positional_args[0]
        assert (
            isinstance(notif_first_arg, ast.Constant)
            and isinstance(notif_first_arg.value, str)
            and notif_first_arg.value == "dispatch_payment_notification"
        ), (
            "notification first enqueue_job argument must be the literal "
            f"'dispatch_payment_notification'; got {ast.dump(notif_first_arg)}"
        )


# ---------------------------------------------------------------------------
# Runtime auxiliary tests — exercise the actual function body against a
# fake arq_pool. Together with the AST gate these lock both the structural
# shape AND the runtime contract.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_commit_enqueue_calls_arq_enqueue_when_fiscal_receipt_id_present() -> None:
    """Plan 51-06: when both ``arq_pool`` and ``fiscal_receipt_id`` are
    non-None, the helper enqueues ``dispatch_fiscal_receipt`` with the
    locked retry contract (``_max_tries=3``, ``_expires=60``)."""
    from app.api.v1._internal.yookassa.handlers import _post_commit_enqueue

    fake_pool = AsyncMock()
    op_id = uuid4()
    subj_id = uuid4()
    fr_id = uuid4()

    await _post_commit_enqueue(
        fake_pool,
        online_payment_id=op_id,
        subject_kind="membership",
        subject_id=subj_id,
        fiscal_receipt_id=fr_id,
    )

    fake_pool.enqueue_job.assert_awaited_once_with(
        "dispatch_fiscal_receipt",
        str(fr_id),
        _max_tries=3,
        _expires=60,
    )


@pytest.mark.asyncio
async def test_post_commit_enqueue_does_not_enqueue_when_fiscal_receipt_id_is_none() -> None:
    """Plan 51-06 / Phase 52 D-52-11: with a real pool but no fiscal_receipt_id
    and no payment_id/kind, both guards short-circuit — no enqueue happens."""
    from app.api.v1._internal.yookassa.handlers import _post_commit_enqueue

    fake_pool = AsyncMock()

    await _post_commit_enqueue(
        fake_pool,
        online_payment_id=uuid4(),
        subject_kind="membership",
        subject_id=uuid4(),
        fiscal_receipt_id=None,
    )

    fake_pool.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_commit_enqueue_does_not_enqueue_when_arq_pool_is_none() -> None:
    """Plan 51-06: with no pool, the enqueue guard short-circuits and the
    helper completes without raising. Preserves the Phase 50 ergonomics
    (the default kwarg ``arq_pool=None`` is still safe for unit tests that
    bypass the lifespan)."""
    from app.api.v1._internal.yookassa.handlers import _post_commit_enqueue

    await _post_commit_enqueue(
        None,
        online_payment_id=uuid4(),
        subject_kind="pt_package",
        subject_id=uuid4(),
        fiscal_receipt_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_post_commit_enqueue_calls_notification_when_payment_id_present() -> None:
    """Phase 52 D-52-11: when ``arq_pool``, ``payment_id``, and ``kind`` are
    all non-None, the helper enqueues ``dispatch_payment_notification`` with the
    locked retry contract (``_max_tries=3``, ``_expires=60``)."""
    from app.api.v1._internal.yookassa.handlers import _post_commit_enqueue

    fake_pool = AsyncMock()
    op_id = uuid4()
    subj_id = uuid4()
    payment_uuid = uuid4()

    await _post_commit_enqueue(
        fake_pool,
        online_payment_id=op_id,
        subject_kind="membership",
        subject_id=subj_id,
        fiscal_receipt_id=None,
        payment_id=payment_uuid,
        kind="payment_succeeded",
    )

    fake_pool.enqueue_job.assert_awaited_once_with(
        "dispatch_payment_notification",
        _kwargs={"payment_id": str(payment_uuid), "kind": "payment_succeeded"},
        _max_tries=3,
        _expires=60,
    )


@pytest.mark.asyncio
async def test_post_commit_enqueue_no_notification_when_payment_id_is_none() -> None:
    """Phase 52 D-52-11: when ``payment_id`` is None (or ``kind`` is None), the
    notification enqueue guard short-circuits — only the fiscal enqueue fires
    when fiscal_receipt_id is present."""
    from app.api.v1._internal.yookassa.handlers import _post_commit_enqueue

    fake_pool = AsyncMock()
    fr_id = uuid4()

    await _post_commit_enqueue(
        fake_pool,
        online_payment_id=uuid4(),
        subject_kind="pt_package",
        subject_id=uuid4(),
        fiscal_receipt_id=fr_id,
        payment_id=None,
        kind=None,
    )

    # Only the fiscal dispatch fires; notification guard short-circuits.
    fake_pool.enqueue_job.assert_awaited_once_with(
        "dispatch_fiscal_receipt",
        str(fr_id),
        _max_tries=3,
        _expires=60,
    )
