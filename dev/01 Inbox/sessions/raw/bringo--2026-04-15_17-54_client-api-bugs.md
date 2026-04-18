---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-15_17-54_client-api-bugs.md
session_date: 2026-04-15
tags: [session-log-raw, bringo, client-api, qa, bugs]
created: 2026-04-19
status: unprocessed
---

# Сессия: [client-api] Пачка багов от тестировщика
**Дата:** 2026-04-15 17:54
**Субмодуль:** client-api (публичный API для клиентов)
**Цель:** проанализировать баги от QA и составить план фиксов

---

## Лог

### 17:54 — Начало
- Задача: разобрать 5 багов, составить план исправлений, после фиксов — lint/phpstan/tests
- Баги:
  1. GET /companies/09301329 — `sic_codes: []` для компании, у которой они должны быть
  2. GET /exports/fields?type=PSCs — 422 validation_error, принимает только lowercase `pscs` (регистрозависимость)
  3. GET /companies/09301329/related-companies — пустой массив
  4. GET /companies/13637908/related-companies — пустой массив (на скрине есть связи в UI)
  5. Лимиты не повышаются со временем как должны
