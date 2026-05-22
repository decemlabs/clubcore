"""W-2 fix (revision 2): post-commit enqueue seam structural gate (Phase 50 D-50-19).

Tautology-resistant AST-level inspection of _post_commit_enqueue's body.
Revision 1 used a runtime spy (arq_pool_spy.enqueue_calls == []) but the
handler passes arq_pool=None directly to _post_commit_enqueue, so the spy
mounted on app.state.arq_pool was never reached — the assertion passed
trivially even if the stub body deviated from no-op. The AST gate inspects
the function's source directly, so it catches any drift toward real
enqueue logic regardless of runtime call paths.

When Phase 52 NOT-04/05 fills the body, this test MUST be updated or
removed in lockstep (the failure mode signals the seam is being consumed
for real). See DEFER-50-04 in deferred-items.md.
"""

import ast
from pathlib import Path

# parents[0]=webhook_yookassa, [1]=integration, [2]=tests, [3]=backend,
# [4]=apps, [5]=repo root. The handlers.py path is reachable from the
# backend root via app/api/v1/_internal/yookassa/handlers.py.
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_HANDLERS_PATH = (
    _BACKEND_ROOT / "app" / "api" / "v1" / "_internal" / "yookassa" / "handlers.py"
)


def test_post_commit_enqueue_body_is_only_log_info() -> None:
    """Phase 50 — _post_commit_enqueue body MUST be a single _log.info(...) call.

    Tautology-resistant structural gate. The runtime spy approach fails
    because the handler passes arq_pool=None directly (the spy on
    app.state.arq_pool is never reached). AST-level inspection of the
    function body catches any drift toward real enqueue logic before
    Phase 52 lands the real body.
    """
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

    # Body should be exactly: docstring (optional Expr) + one _log.info(...) Expr
    non_docstring_stmts = [
        s
        for s in fn.body
        if not (
            isinstance(s, ast.Expr)
            and isinstance(s.value, ast.Constant)
            and isinstance(s.value.value, str)
        )
    ]
    assert len(non_docstring_stmts) == 1, (
        f"Phase 50 _post_commit_enqueue must be a single _log.info(...) call; "
        f"got {len(non_docstring_stmts)} non-docstring statements"
    )

    only_stmt = non_docstring_stmts[0]
    assert isinstance(only_stmt, ast.Expr), "single stmt must be an Expr"
    assert isinstance(only_stmt.value, ast.Call), "single stmt must be a Call"
    call = only_stmt.value
    func_dotted = ast.unparse(call.func)
    assert func_dotted == "_log.info", (
        f"Phase 50 _post_commit_enqueue must call _log.info only; got {func_dotted}"
    )
