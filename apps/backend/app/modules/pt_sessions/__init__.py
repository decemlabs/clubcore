"""PT-sessions module (Phase 34 PT-14..PT-22).

Module marker. Phase 34 introduces ZERO new Protocol slots in
`core.dependencies` (D-34-13a — resolver-only consumer of TrainerById +
ActivePtPackage; no `register_pt_session_*` calls in `app.main.create_app`).

No public re-exports at module level — `app.modules.pt_packages.__init__`
re-exports `resolve_active_pt_package` because Phase 33 wired a resolver;
Phase 34 wires none.
"""
