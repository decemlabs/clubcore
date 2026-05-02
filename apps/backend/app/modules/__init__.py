"""Business modules namespace.

Each submodule (auth, clients, memberships, visits, trainers, schedule, bookings,
billing, notifications) is a self-contained vertical slice. Modules MUST NOT
import each other directly — enforced by import-linter's `modules-independent`
contract (apps/backend/importlinter.ini).
"""
