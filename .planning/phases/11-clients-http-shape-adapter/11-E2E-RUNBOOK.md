# Phase 11 Live E2E Runbook

Closes Phase 11 success criterion #4. Run after plans 11-01 and 11-02 are merged.
No E2E framework is wired in this repo, so this is the human-verify gate.

## Prerequisites

- [ ] `docker compose up -d postgres redis` — Postgres + Redis healthy
- [ ] `cd apps/backend && uv run alembic upgrade head` — migrations applied
- [ ] `cd apps/backend && uv run python -m app.main` (or equivalent dev runner) — API up on port 8000
- [ ] Owner user seeded (default `seed_demo_data.py` from Phase 5)
- [ ] In `apps/admin-web/.env.development` set `VITE_API_MODE=http` and `VITE_API_BASE_URL=http://localhost:8000`
- [ ] `pnpm -F admin-web dev` running on port 5173

## Walkthrough

### 1. Login
- [ ] Open http://localhost:5173/login
- [ ] Enter seeded owner email + password, submit
- [ ] Network tab: `POST /api/v1/auth/login` returns 200; `sz_access` and `sz_refresh` cookies appear; redirected to `/`

### 2. List clients (closes F-01 part 1)
- [ ] Navigate to `/clients`
- [ ] Network tab: `GET /api/v1/clients?page=1&pageSize=20` returns 200 with `{ data: { items: [...], total, page, pageSize } }`
- [ ] In the table, every row's "ФИО" column shows a real name (e.g. "Иванов Иван Иванович") — NOT `undefined`, NOT empty
- [ ] Sorting / pagination work (page 2 fetches with the correct query string)

### 3. Create client (closes F-02)
- [ ] Click "Добавить клиента"
- [ ] Fill: Фамилия = "Тестов", Имя = "Тест", Отчество = "Тестович", Телефон = "+79990001122"
- [ ] Leave Email, Дата рождения, Заметки empty
- [ ] Submit
- [ ] Network tab: `POST /api/v1/clients` returns 201; request body in DevTools contains `{"lastName":"Тестов","firstName":"Тест","middleName":"Тестович","phone":"+79990001122"}` (NO `birthDate` key, NO `email: ""`)
- [ ] New client appears at the top of the list with full name "Тестов Тест Тестович"

### 4. Create client with all optional fields populated
- [ ] Click "Добавить клиента"
- [ ] Fill: Фамилия = "Полный", Имя = "Иван", Email = "ivan@example.com", Дата рождения = "1990-04-12", Телефон = "+79990003344"
- [ ] Submit
- [ ] Network tab: `POST /api/v1/clients` returns 201; request body contains `"birthday":"1990-04-12"` (NOT `birthDate`) and `"email":"ivan@example.com"`

### 5. Edit client (closes F-01 optimistic-update guard)
- [ ] Click "Тестов Тест Тестович" → opens detail / edit form
- [ ] Change Имя to "Сергей", submit
- [ ] Network tab: `PATCH /api/v1/clients/{id}` returns 200; request body is `{"firstName":"Сергей"}` (only the changed field)
- [ ] Optimistic update: row updates immediately to "Тестов Сергей Тестович" before the request resolves; no `TypeError` in console
- [ ] After settle, the row remains "Тестов Сергей Тестович"

### 6. Delete client (owner-only)
- [ ] As owner, click delete on "Тестов Сергей Тестович"
- [ ] Confirm
- [ ] Network tab: `DELETE /api/v1/clients/{id}` returns 204
- [ ] Row disappears from the list

### 7. Negative checks
- [ ] Console is clean: NO `TypeError: Cannot read properties of undefined`
- [ ] Network tab: NO 422 `Unprocessable Entity` on any of the create/update calls

## Sign-off

- [ ] All boxes ticked → comment "approved" in the checkpoint to release the phase
