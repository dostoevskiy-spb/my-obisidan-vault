---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-13_16-07_openapi-spec-validation.md
session_date: 2026-04-13
tags:
  - session
  - bringo
  - client-api
  - openapi
created: 2026-04-15
status: unprocessed
---

# Сессия: [client-api] Валидация билда OpenAPI спеки

**Дата:** 2026-04-13 16:07
**Субмодуль:** client-api
**Цель:** Проверить файл `~/Загрузки/openapi-v1.0.0.json` на корректность и соответствие реальному API

---

## Лог

### 16:07 — Начало
- Задача: валидировать билд OpenAPI спеки v1.0.0 против фактической реализации API
- Контекст: файл 203KB / 4376 строк, в проекте есть эталонный `client-api/openapi-current.json` (4555 строк) — источник истины генерится Scramble из контроллеров
- Подход: (1) сравнить с openapi-current.json, (2) валидировать структуру JSON, (3) сверить с реальными роутами Laravel

### 16:15 — Метаданные сравнения
- Что: сравнил версии и кол-во путей
- Результат: расхождения
- Детали: uploaded `1.0.0` vs current `1.0.1`; 33 vs 37 paths; 16 vs 15 schemas; servers URL `http://localhost/v1` — placeholder; tags нет ни в одной

### 16:18 — Diff endpoints
- Что: посчитал symmetric difference paths
- Результат: 6 пропущенных в uploaded, 2 лишних
- Детали:
  - В uploaded НЕТ (но есть в коде/current): `/account/requests`, `/account/webhook-deliveries`, `/exports` (POST/GET), `/exports/fields`, `/exports/{id}` (GET/DELETE), `/exports/{id}/download`
  - В uploaded ЕСТЬ (но в коде закомментирован): `/contacts/{person_id}/reveal` (POST) — `routes/api.php:148` явно `// Route::post('contacts/{person_id}/reveal', ...) // Contact reveal — temporarily disabled (coming soon)`
  - `/companies/{company_number}/contacts` есть и там и там; в openapi-current.json его нет, а в uploaded — есть → uploaded свежее по contacts, но старее по exports/account
- Schemas: uploaded имеет `ContactResource`, `RevealedContactResource`, в current есть `CreateExportRequest`

### 16:23 — Redocly lint
- Что: прогнал `npx @redocly/cli lint` против uploaded
- Результат: ❌ 17 errors + 31 warnings
- Детали:
  - 17 errors `struct rule` — нелегитимные ключи `additionalItems` (legacy JSON Schema draft-04, в OpenAPI 3.1 / JSON Schema 2020-12 не поддерживается) и `items` на объектах без `type: array`. Места: `CompanyResource.sic_codes`, `CompanyResource.previous_company_names`, `ContactResource.departments`, `RevealedContactResource.{departments,emails,phone_numbers}`, `CompanyListResource.sic_codes`, `WebhookSubscriptionResource.company_numbers`, и в response-схемах `/account/usage`, `/companies/{n}`, `/companies/{n}/contacts`, `/companies/{n}/filing-history/{id}`, `/companies/{n}/financial-data`, `/search/officers`, `/search/pscs`, `/webhooks/{id}/companies`
  - 29 warnings `operation-4xx-response` — у операций нет описаний 4xx ошибок
  - 1 warning `info-license` — нет `info.license`
  - 1 warning сервер-плейсхолдер `http://localhost/v1`
- Файлы: —

---

## Итоги

- **Выполнено:** Валидация uploaded openapi-v1.0.0.json — найдены расхождения с кодом и OpenAPI 3.1 schema-нарушения
- **Не завершено:** пофиксить генерацию (Scramble) чтобы убрать `additionalItems`; перегенерить спеку с актуальной ветки
- **Планы:** —
- **В память:** — (тривиально, в CLAUDE.md уже описан Scramble)

## Реализация

Ничего не реализовано — только аудит.

## Расхождения uploaded-спеки с реальным API

### Отсутствуют в спеке (есть в routes/api.php)
- `GET /account/requests` (routes/api.php:48)
- `GET /account/webhook-deliveries` (routes/api.php:49)
- `POST /exports`, `GET /exports`, `GET /exports/fields`, `GET /exports/{id}`, `GET /exports/{id}/download`, `DELETE /exports/{id}` (routes/api.php:79-89)

### Лишние в спеке (в коде закомментировано)
- `POST /contacts/{person_id}/reveal` (routes/api.php:148 — `// temporarily disabled (coming soon)`)

### OpenAPI 3.1 structural errors (17)
- `additionalItems` в anyOf-ветках array-типов — не валидно в JSON Schema 2020-12 (используемом OpenAPI 3.1). Scramble генерит draft-04-стильные артефакты
- Несколько `items` на не-array schema

### Версия и метаданные
- `info.version: 1.0.0` — отстаёт от `openapi-current.json` (1.0.1)
- `servers[0].url: http://localhost/v1` — локальный плейсхолдер, не production
- `info.license` отсутствует
- 29 операций без 4xx responses
