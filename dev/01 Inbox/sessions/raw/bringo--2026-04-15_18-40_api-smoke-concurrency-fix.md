---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-15_18-40_api-smoke-concurrency-fix.md
session_date: 2026-04-15
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [client-api] Smoke API через ЛК-токен + root cause 429 concurrency
**Дата:** 2026-04-15 18:40
**Субмодуль:** client-api
**Цель:** Протестировать публичный API с выданным `bcu_live_*` токеном, прогнать все endpoints с компанией `07150887`, разобраться почему идут 429 при последовательных запросах.

---

## Лог

### 18:40 — Начало
- Задача: пользователь получил API-ключ и хочет понять как тестировать API
- Контекст: токен создан в рамках Enterprise-флоу вчерашней сессии (2026-04-13_23-54), баланс 100000 кредитов
- Первый запрос компании 12345678 → 404 (такой компании нет). Переключились на `07150887`

### 18:45 — Подготовка тестового скрипта
- Что: написал bash-скрипт `/tmp/api_test.sh` с вызовами всех endpoints через `curl -k https://localhost/public-api/v1/...`
- Детали: 14 free endpoints + 14 paid с CN=07150887. Обращение через `https://localhost` напрямую (self-signed SSL, `-k`), а не через `https://nginx` — nginx resolve с хоста не даёт nginx-upstream маршрутизации
- jq есть на хосте, в контейнерах api нет (только curl). Запускал с хоста

### 18:50 — Первый прогон: 429 concurrency
- Что: прогнал все endpoints с `sleep 1.1` между запросами
- Результат: **половина запросов получили 429** `"Too many concurrent requests for this client"`
- Детали: первые ~7 запросов проходили, потом 429 почти на всё подряд; часть потом снова 200. Рестарт `docker compose restart api` + `sleep 5` сбрасывал симптом. Подозрение на Octane state leak

### 19:00 — Пользователь: "rate limit не может быть, запросы последовательные"
- Пользователь резонно напомнил: `sleep 1.5s` между запросами не может вызвать **concurrency**, это не parallel-load. Значит внутри ConcurrencyLimiter что-то не работает
- Ошибка с моей стороны: изначально подумал что это проблема лимитов, а не release-логики

### 19:05 — Изучение ConcurrencyLimiter
- Файл: [client-api/app/Shared/Middleware/ConcurrencyLimiter.php](client-api/app/Shared/Middleware/ConcurrencyLimiter.php)
- Что: прочёл целиком — 201 строка до фикса
- Находка: middleware держит instance-поля (`$globalAcquired`, `$clientAcquired`, `$clientId`, `$globalUsingFallback`, `$clientUsingFallback`) и release делается из `terminate()`

### 19:10 — Моя первая гипотеза (оказалась неточной)
- Утверждение: "terminate() не вызывается при exceptions" + "в Octane instance переживает между запросами → `$this->globalAcquired = true` протекает"
- Предложил fix: `try/finally` + локальные переменные + убрать `terminate()`
- Пользователь применил фикс (с доп. улучшениями: `markConcurrencyRejected` для rate-limit headers, reset per-request fallback state)

### 19:20 — Пользователь: "проверь свою находку"
- Пользователь попросил верифицировать обе теории по коду и логам, не спекулятивно

### 19:25 — Проверка теории 2 (Redis::eval fail → static fallback)
- Что: `grep -c "ConcurrencyLimiter: Redis unavailable" storage/logs/laravel.log` → **0 вхождений**
- Что: `Redis::eval("return 42", 0)` в tinker → `int(42)`; атомарный `INCR + EXPIRE` → `int(1)`
- Вывод: **теория опровергнута** — Redis::eval работал всё время, static fallback ни разу не запускался

### 19:30 — Проверка теории 1 (instance state leak)
- Файл: [vendor/laravel/framework/src/Illuminate/Foundation/Http/Kernel.php:243-263](client-api/vendor/laravel/framework/src/Illuminate/Foundation/Http/Kernel.php#L243-L263)
- Находка: `terminateMiddleware` вызывает `$this->app->make($name)` → **создаёт новый instance** каждый раз
- Файл: [vendor/laravel/framework/src/Illuminate/Pipeline/Pipeline.php:208](client-api/vendor/laravel/framework/src/Illuminate/Pipeline/Pipeline.php#L208)
- Находка: `$pipe = $this->getContainer()->make($name)` — handle() создаёт свой instance
- **Уточнённая причина:** instance state теряется не между запросами, а **между handle() и terminate() в одном запросе**. Instance A в handle, instance B в terminate — разные. `$this->globalAcquired` на B = default `false`, release не вызывается

### 19:35 — Итог аудита
- Что: написал честный аудит в plan-файл (`/home/pavel/.claude/plans/playful-giggling-map.md`)
- Результат: признал ошибку формулировки в теории 1, опроверг теорию 2
- Реальная механика: release **никогда не вызывался** (разные instance), ключи в Redis жили TTL=30s, счётчик рос до limit=10, на 11-м запросе → 429. Рестарт api + пауза 5+ сек → TTL истекал → сброс (не магия Octane)

### 19:40 — Применённый фикс верифицирован
- Решение пользователя: `try/finally` внутри handle() + локальные `$globalAcquired/$clientAcquired/$clientKey` — release на том же instance, гарантирован при exception из `$next($request)`
- terminate() удалён — не нужен
- `$globalUsingFallback`/`$clientUsingFallback` остались instance-полями, но читаются/пишутся в пределах одного handle() — корректно

### 18:40 — Фиксирую сессию
- По просьбе пользователя через скилл session-log

---

## Итоги

- **Выполнено:**
  - Прогон 28 endpoints публичного API с токеном на CN=07150887 — работают все read-only (status, account/*, directories, sandbox, search, company/*, exports, webhooks)
  - Найдена и пофикшена причина 429 в ConcurrencyLimiter (release никогда не выполнялся из-за разных instance в handle/terminate)
  - Признал ошибку формулировки своих гипотез после честной проверки по коду + логам
- **Не завершено:**
  - Не прогнаны: 11 других багов из QA-отчёта (`.claude/sessions/2026-04-15_10-27_client-api-qa.md`) и плана PR20-PR25 (`/home/pavel/.claude/plans/fluffy-humming-kurzweil.md`)
  - `KEY_TTL=30s` в ConcurrencyLimiter коротковат для `DB_STATEMENT_TIMEOUT=30s` — рекомендую 60s
  - Регрессионные тесты на release after exception — отсутствуют (есть в PR24)
- **Планы:** [playful-giggling-map.md](../../../.claude/plans/playful-giggling-map.md) — аудит ошибочных утверждений + точная механика бага
- **В память:**
  - Distributed state (release) в middleware ломается на переходе handle→terminate из-за двух разных instance — всегда использовать `try/finally` внутри handle
  - Не называть "instance state переживает запросы в Octane" как причину, если middleware не singleton — эта частая гипотеза неверна (Octane flush'ит scopes, middleware создаётся через make на каждый запрос)

## Реализация

### Ключевые компоненты

**Было (до фикса) — [ConcurrencyLimiter.php](client-api/app/Shared/Middleware/ConcurrencyLimiter.php):**
- instance-поля `$globalAcquired`/`$clientAcquired`/`$clientId`
- release в `terminate()`
- **Баг:** Laravel `Kernel::terminateMiddleware` делает `$this->app->make($name)` → новый instance, `$this->globalAcquired = false` default → release пропускается

**Стало:**
- `handle()` с `try/finally`, release внутри finally
- Локальные переменные `$globalAcquired`, `$clientAcquired`, `$clientKey` — нет instance state для слотов
- `terminate()` удалён
- `$globalUsingFallback`/`$clientUsingFallback` сбрасываются в начале handle() (safety для singleton-сценария)
- Добавлен `markConcurrencyRejected()` для передачи контекста в RateLimit headers при rejection
- `ApiException::concurrencyLimitExceeded()` вместо `rateLimitExceeded()` (разделение 429 по причине)

### Тестовые артефакты
- `/tmp/api_test.sh` — bash-скрипт прогона 28 endpoints через curl с jq-парсингом, баланс до/после
- Переменные окружения: `API_TOKEN=bcu_live_*`, `API_URL=https://localhost/public-api/v1`
- Первый поиск через `/search/companies?q=limited` → берём `.data[0].company_number` → использовать дальше. Если фиксированный CN не существует — 404 до billing (или 402 из-за bug-2 в QA-отчёте на stage)

## Расхождения с анализом

- **Утверждал:** "terminate не вызывается при exceptions" → **реально:** вызывается всегда, но на новом instance без state
- **Утверждал:** "instance state переживает запросы в Octane worker'а" → **реально:** Octane flush'ит scopes, instance создаётся новый на каждый запрос; leak между handle и terminate ОДНОГО запроса из-за двух разных `make()`
- **Утверждал:** "Redis::eval → fail → static fallback залипает" → **реально:** Redis работал, 0 логов "Redis unavailable", static никогда не запускался
