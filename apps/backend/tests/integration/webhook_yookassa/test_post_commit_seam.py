"""Plan 51-06 D-51-15 — post-commit enqueue seam structural gate.

Replaces Plan 50-04 W-2 stub gate (``body is only _log.info``).

Tautology-resistant AST-level inspection of ``_post_commit_enqueue``'s body.
The previous Phase 50 gate (``test_post_commit_enqueue_body_is_only_log_info``)
asserted the body was a single ``_log.info(...)`` call. Plan 51-06 flips that
in-place: the body now MUST contain (a) the log call AND (b) a guarded
``await arq_pool.enqueue_job("dispatch_fiscal_receipt", ...)`` enqueue.

Why the runtime-spy approach in the original revision was tautological is
preserved in the docstring history: the Phase 50 handler passed
``arq_pool=None`` positionally to ``_post_commit_enqueue``, so any spy
mounted on ``app.state.arq_pool`` was never reached. The AST gate inspects
function source directly, so it catches structural drift regardless of
runtime call paths — that property carries forward into Phase 51.

When Phase 52 NOT-02/NOT-04 fills the notification branches, this test MUST
be updated again in lockstep with the body change (PATTERNS.md errata #3).
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
_HANDLERS_PATH = (
    _BACKEND_ROOT / "app" / "api" / "v1" / "_internal" / "yookassa" / "handlers.py"
)


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
    """Phase 51 D-51-15 — body MUST be (a) a ``_log.info`` call AND (b) a
    guarded ``await arq_pool.enqueue_job('dispatch_fiscal_receipt', ...)``.

    Tautology-resistant structural gate. The test inspects the function's
    AST directly, so it fails on any structural drift away from the locked
    2-statement shape — even if the function signature still accepts
    ``fiscal_receipt_id``. This is what carries the invariant forward
    into Phase 52 (which must update this gate in lockstep with any
    additional branches).
    """
    fn = _load_post_commit_enqueue_fn()
    body = _non_docstring_body(fn)
    assert len(body) == 2, (
        "Phase 51 _post_commit_enqueue must call _log.info AND conditionally "
        f"enqueue dispatch_fiscal_receipt; got {len(body)} non-docstring "
        f"statements: {[ast.unparse(s) for s in body]}"
    )

    # Statement 1: Expr wrapping a Call to _log.info(...).
    log_stmt = body[0]
    assert isinstance(log_stmt, ast.Expr), (
        "Phase 51 _post_commit_enqueue body[0] must be an Expr wrapping a Call; "
        f"got {ast.dump(log_stmt)}"
    )
    assert isinstance(log_stmt.value, ast.Call), (
        "Phase 51 _post_commit_enqueue body[0] must wrap a Call; "
        f"got {ast.dump(log_stmt.value)}"
    )
    log_target = ast.unparse(log_stmt.value.func)
    assert log_target == "_log.info", (
        f"Phase 51 _post_commit_enqueue body[0] must call _log.info; got {log_target}"
    )

    # Statement 2: If whose test is BoolOp(And, [IsNot None, IsNot None]).
    if_stmt = body[1]
    assert isinstance(if_stmt, ast.If), (
        "Phase 51 _post_commit_enqueue body[1] must be an If guard; "
        f"got {ast.dump(if_stmt)}"
    )
    assert isinstance(if_stmt.test, ast.BoolOp) and isinstance(
        if_stmt.test.op, ast.And
    ), (
        "Phase 51 _post_commit_enqueue if-guard must be a BoolOp(And, ...); "
        f"got {ast.dump(if_stmt.test)}"
    )
    bool_values = if_stmt.test.values
    assert len(bool_values) == 2, (
        f"Phase 51 _post_commit_enqueue if-guard must combine exactly 2 "
        f"clauses (arq_pool is not None AND fiscal_receipt_id is not None); "
        f"got {len(bool_values)}"
    )
    for clause in bool_values:
        assert isinstance(clause, ast.Compare), (
            f"if-guard clause must be a Compare; got {ast.dump(clause)}"
        )
        assert len(clause.ops) == 1 and isinstance(clause.ops[0], ast.IsNot), (
            f"if-guard clause must use ``is not``; got {ast.dump(clause.ops[0])}"
        )
        assert (
            len(clause.comparators) == 1
            and isinstance(clause.comparators[0], ast.Constant)
            and clause.comparators[0].value is None
        ), f"if-guard clause must compare against None; got {ast.dump(clause)}"
    guard_names = {ast.unparse(c.left) for c in bool_values}  # type: ignore[union-attr]
    assert guard_names == {"arq_pool", "fiscal_receipt_id"}, (
        f"if-guard must combine arq_pool + fiscal_receipt_id; got {guard_names}"
    )

    # If.body: single Expr wrapping an Await of arq_pool.enqueue_job(...).
    inner_body = if_stmt.body
    assert len(inner_body) == 1, (
        f"Phase 51 _post_commit_enqueue if-body must have exactly 1 statement; "
        f"got {len(inner_body)}"
    )
    enq_stmt = inner_body[0]
    assert isinstance(enq_stmt, ast.Expr) and isinstance(enq_stmt.value, ast.Await), (
        f"if-body must be Expr(Await(Call(...))); got {ast.dump(enq_stmt)}"
    )
    await_val = enq_stmt.value.value
    assert isinstance(await_val, ast.Call), (
        f"awaited expression must be a Call; got {ast.dump(await_val)}"
    )
    enq_target = ast.unparse(await_val.func)
    assert enq_target == "arq_pool.enqueue_job", (
        f"if-body must call arq_pool.enqueue_job; got {enq_target}"
    )
    # First positional arg is the locked task name.
    assert len(await_val.args) >= 1, (
        f"enqueue_job must receive at least the task name; got {await_val.args}"
    )
    first_arg = await_val.args[0]
    assert (
        isinstance(first_arg, ast.Constant)
        and isinstance(first_arg.value, str)
        and first_arg.value == "dispatch_fiscal_receipt"
    ), (
        "first enqueue_job argument must be the literal "
        f"'dispatch_fiscal_receipt'; got {ast.dump(first_arg)}"
    )
    # _max_tries=3 + _expires=60 are part of the ARQ retry contract.
    kw_map: dict[str, ast.expr] = {kw.arg: kw.value for kw in await_val.keywords if kw.arg}
    assert "_max_tries" in kw_map, "enqueue_job must pass _max_tries"
    assert "_expires" in kw_map, "enqueue_job must pass _expires"
    max_tries = kw_map["_max_tries"]
    expires = kw_map["_expires"]
    assert (
        isinstance(max_tries, ast.Constant)
        and max_tries.value == 3
    ), f"_max_tries must be the literal 3; got {ast.dump(max_tries)}"
    assert (
        isinstance(expires, ast.Constant) and expires.value == 60
    ), f"_expires must be the literal 60; got {ast.dump(expires)}"


# ---------------------------------------------------------------------------
# Runtime auxiliary tests — exercise the actual function body against a
# fake arq_pool. Together with the AST gate these lock both the structural
# shape AND the runtime contract.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_commit_enqueue_calls_arq_enqueue_when_fiscal_receipt_id_present() -> (
    None
):
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
async def test_post_commit_enqueue_does_not_enqueue_when_fiscal_receipt_id_is_none() -> (
    None
):
    """Plan 51-06: with a real pool but no fiscal_receipt_id, the enqueue
    guard short-circuits — no enqueue happens. (Phase 52 will add the
    notification branches behind their own guards.)"""
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
