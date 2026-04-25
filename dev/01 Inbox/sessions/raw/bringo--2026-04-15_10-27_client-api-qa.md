---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-15_10-27_client-api-qa.md
session_date: 2026-04-15
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [client-api] QA прогона публичного REST API на стейдже
**Дата:** 2026-04-15 10:27
**Субмодуль:** client-api
**Цель:** Протестировать все endpoints публичного API на стейджинге через curl, зафиксировать баги.

---

## Лог

### 10:27 — Начало
- Задача: подготовить набор curl для всех endpoints + прогон на stage
- Контекст: 37 paths, 44 operations из OpenAPI-спеки, client-api на Laravel 13 + Octane+FrankenPHP

### 10:30 — Собрал план тестирования
- План: [fluffy-humming-kurzweil.md](plans/../../../../../.claude/plans/fluffy-humming-kurzweil.md)
- Источники: `client-api/openapi-current.json` + FormRequest-классы
- Секции 1–12: smoke / account / directories / sandbox / search / company / officer+psc / webhooks / exports / negative / headers
- Базовый URL изначально указал неверный (`api.int.bringo.co.uk`), исправил на `api.stg.int.bringo.co.uk` после диагностики 401

### 10:38–11:00 — Диагностика 401 invalid_token
- Проблема: пользователь получал 401 на `/account/me` при валидном токене
- Симптомы: хэш токена в БД stg совпадал с `sha256($plain)`, клиент active, allowed_ips null
- Tinker в stg-поде: `resolveToken()` корректно возвращал объект
- Причина: **запросы шли на другой environment** (`api.int.bringo.co.uk` — не stage, там БД без токена). После смены домена на `api.stg.int.bringo.co.uk` — 200.
- Урок: при 401 на якобы валидный токен — сравнивать `db_name`/`env` на pod, в который реально уходит HTTP, а не на соседний удобный pod

### 11:15–11:30 — Смоук + free endpoints
- `/v1/status` → 200, все сервисы ok (pg, redis, clickhouse, opensearch)
- `/v1/account/me` → 200, client_id=1816, balance=0
- `/v1/directories` → 200 (58 секций, в CLAUDE.md заявлено 51 → выросло)
- `/v1/sandbox/companies` → 200 (16+ FTSE-компаний: TESCO, BP, BARCLAYS...)
- `/v1/search/suggest?q=tesco` → 200, реальные данные

### 11:35 — Billable endpoints все вернули 402
- Баланс клиента 1816 = 0, grace = 0
- Middleware корректно считает стоимость ДО выполнения (export с limit=10 → 402 Required: 10)
- `/companies/bulk` вернул 200 `requested=3, found=0` — bulk не списывает за ненайденное

### 11:40 — Webhooks CRUD — полный цикл работает
- Create 201 с `whsec_...` в meta (одноразово)
- List/show/update/add-companies/list-companies/remove-companies/test/delete — все 200
- Test-доставка вернула `success: false, status_code: 404` — webhook.site URL заглушечный, это ок

### 11:45 — Negative scenarios — НАЙДЕНЫ БАГИ
- 10.3 `GET /companies/ZZ999999` → **402** (должно 404). Причина: billing раньше валидации path params
- 10.5 `?sort=invalid_sort` → **402** (должно 422). То же.
- 10.6 `GET /directories/unknown_section_xyz` → первый раз 404, **все следующие 500**. Причина: `Cache::remember` пустой Collection, падает десериализация из Redis.
- 10.11 body > 1MB → **422** (должно **413 RFC 9110 §15.5.14**).
- Headers: **x-powered-by: PHP/8.5.5** — security leak.
- `/account/usage.daily` — **не группирует по дате** (три записи с date=2026-04-15 вместо одной с requests=3).
- 10.10 Rate limit работает: 57×200 + 13×429 из 70 параллельных.

### 11:50 — Отчёт собран
- Файл: `/tmp/bringo-qa/QA-REPORT.md`
- Артефакты: `/tmp/bringo-qa/*.json` — все ответы сохранены
- Утилита прогона: `/tmp/bringo-qa/req.sh` — переиспользуема

---

## Итоги
- **Выполнено:** прогон 44 endpoints по плану из 12 секций, собран QA-отчёт с 6 багами
- **Не завершено:** 18 billable endpoints не протестированы функционально (нужен баланс >0 у клиента 1816)
- **Планы:** [fluffy-humming-kurzweil.md](../../../.claude/plans/fluffy-humming-kurzweil.md)
- **В память:** 6 багов в API + заметка про диагностику 401 (проверять environment pod'а)

## Реализация

### Артефакты
- `/tmp/bringo-qa/req.sh` — bash-утилита `req <METHOD> <label> <path> [body]`, сохраняет ответ в `<label>.json`, статус+time в `<label>.status`
- `/tmp/bringo-qa/QA-REPORT.md` — полный отчёт, 6 багов с root cause и фиксами
- `/tmp/bringo-qa/*.json` — 60+ ответов API с сохранёнными request_id для поиска в логах

### Баги найдены (подробности — в QA-REPORT.md)
1. **BUG-1 критичный**: 500 на повторе `GET /directories/{unknown}` — Cache::remember кеширует пустую Collection → ломает десериализацию. Фикс: exists() до remember. Файл: `client-api/app/Modules/Directory/Controllers/DirectoryController.php:61`
2. **BUG-2**: `billing.check` раньше валидации path/params → 402 вместо 404/422. Файл: `client-api/routes/api.php:98`
3. **BUG-3**: body > 1MB → 422 вместо 413. Middleware: `App\Shared\Middleware\RequestBodyLimit`
4. **BUG-4**: `/account/usage.daily` не группирует по дате (SQL). Файл: `client-api/app/Modules/Account/Controllers/AccountController.php`
5. **BUG-5 minor**: `X-Powered-By: PHP/8.5.5` — expose_php
6. **BUG-6 minor**: `request_id: null` при default Laravel 404

### Подтверждения работоспособности
- Auth (Bearer + X-API-Key), brute-force protection
- Rate limit 60/min (13×429 из 70 параллельных запросов)
- Concurrency 50 (X-Concurrent-* headers)
- ETag / If-None-Match → 304
- ClickHouse request log (виден в `/account/requests`)
- Webhooks CRUD полный цикл с HMAC secret в response
- Billing cost estimation (403 на export с limit=10 → Required: 10)
- Security headers (nosniff, DENY, noindex, XSS-0)

## Расхождения с планом
- В плане `10.11` ожидал 413, по факту 422 → зафиксирован как BUG-3
- В плане `10.3` ожидал 404, по факту 402 → BUG-2 (было ожидание «404/422», но билинг ошибочно срабатывает первым)
- В плане `10.6` ожидал стабильный 404, по факту первый 404 / все следующие 500 → BUG-1
