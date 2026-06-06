---
status: passed
phase: 86-gym-info-cms
source: [86-VERIFICATION.md]
started: 2026-06-06
updated: 2026-06-06
verified_in_browser: 2026-06-06 (client-pwa :5175, dev client +79999999999, SW/cache cleared)
---

## Current Test

[✅ VERIFIED in browser 2026-06-06 — GymInfoSheet renders live DB data; owner `PUT /gym` → client `GET /client/gym` round-trip confirmed; Europe/Moscow open/closed badge live]

## Tests

### 1. End-to-end render of GymInfoSheet from DB (GYM-01/03)
steps: client-pwa :5175 (SW unregistered + gym-v3 cache cleared), dev login +79999999999 / OTP 111111, Home → «ЗАЛ · Расписание» tile
expected: Sheet renders gym name/address/hours/amenities/rules/contacts from DB (not data/gym.js)
result: ✅ PASS — title «Информация о зале»; hero «Мой зал · Тверская» / «Круглосуточный клуб в центре» / «Тверская, 18, 3 этаж» / «5 мин от м. Пушкинская»; full 7-day ЧАСЫ РАБОТЫ; УДОБСТВА + ПРАВИЛА + КОНТАКТЫ (tel:/mailto:) + Telegram social (t.me/mygym_tverskaya — confirms socialUrl replaceAll('@') fix). Notably the sheet showed the **4 amenities + 3 rules set via the owner `PUT /gym`** (not the 8+5 seed) — proving GYM-02 owner-write → GYM-01 client-read round-trip live. Screenshot: /tmp/v24-verify/03-gym-info.png

### 2. Open/closed badge time-dependent behavior (Europe/Moscow)
steps: open GymInfoSheet; current MSK = Saturday within 09:00–22:00
expected: today row listed first with «Сейчас открыто» (chip-accent) when open
result: ✅ PASS — today «Сб · сегодня · до 22:00» listed first, green «Сейчас открыто» badge rendered; client-side Intl Europe/Moscow derivation correct.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None — both items verified live in the browser.
