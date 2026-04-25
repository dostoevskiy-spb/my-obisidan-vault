---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-09_15-18_api-webhook-relay-research.md
session_date: 2026-04-09
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [client-api] Исследование ApiWebhookRelay
**Дата:** 2026-04-09 15:18
**Субмодуль:** client-api, backend
**Цель:** Понять назначение ApiWebhookRelay, какие события попадают, есть ли фильтрация для защиты от перегрузки

---

## Лог

### 15:18 — Начало
- Задача: исследовать модуль ApiWebhookRelay — назначение, фильтрация событий, нагрузка
- Контекст: пользователь открыл ApiTokenService.php, спрашивает про webhook relay

### 15:19 — Исследование ApiWebhookRelay и event system
- Что: параллельный запуск двух Explore-агентов — один на webhook relay, второй на event system бэкенда
- Результат: успех, полная картина
- Детали:
  - ApiWebhookRelayHandler (backend) подписан на fanout exchange `entity-updated-event` через отдельную очередь `api-webhook-relay`
  - 6 уровней фильтрации: event type mapping → company ID validation → DB lookup → subscription company filter → event type filter → is_active check
  - 8 типов событий релеятся (company.updated, officer.changed, filing.new, psc.changed, insolvency.changed, charge.changed, exemptions.changed, uk_establishment.changed)
  - rating и statement НЕ релеятся — отфильтрованы на уровне EVENT_TYPE_MAP
  - Подписки фильтруют по конкретным company_numbers (PostgreSQL array) и по типам событий
  - Redis используется как мост между Symfony (backend) и Laravel (client-api)
  - ProcessWebhookInboxCommand опрашивает Redis каждые 10 секунд
  - DispatchWebhookJob: HMAC-SHA256 подпись, DNS rebinding protection, retry 8 раз с exponential backoff, логирование в ClickHouse
  - Авто-отключение подписки после 3 consecutive failures

### 16:40 — Feature flag + Redis cap для ApiWebhookRelay
- Что: добавлен feature flag `API_WEBHOOK_RELAY_ENABLED` (по умолчанию `false`) и Lua-скрипт с cap 100K для Redis list
- Результат: успех
- Файлы:
  - `backend/config/parameters.yaml` — добавлен `app.api_webhook_relay.enabled`
  - `backend/config/services.yaml` — прокинут `$enabled` в DI
  - `backend/src/Service/ApiWebhook/ApiWebhookRelayHandler.php` — early return + Lua PUSH_CAPPED
  - `backend/helmfile.d/values/common/backend.yaml` — consumer закомментирован, `API_WEBHOOK_RELAY_ENABLED=false` в commonEnvs
  - `compose.d/backend/.env` — `API_WEBHOOK_RELAY_ENABLED=false`
