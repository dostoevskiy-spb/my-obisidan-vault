---
type: adr
project: bringo
submodule: api
tags: [adr, bringo, api]
updated: 2026-04-07
---

# ADR: Bringo API

Архитектурные решения модуля API (Laravel 13 REST API для Companies House).

## Решения

### 2026-04-05: Redis relay для webhooks (не RabbitMQ)
**Контекст:** Backend (Symfony) генерирует EntityUpdatedEvent, API (Laravel) должен dispatch webhooks клиентам. Модули разделены.
**Решение:** Symfony consumer → Redis inbox → Laravel ProcessWebhookInboxCommand → DispatchWebhookJob
**Альтернативы:** Прямое подключение Laravel к RabbitMQ (новая зависимость, tight coupling)
**Статус:** реализовано

### 2026-04-05: Full payload в webhooks (не notification-only)
**Контекст:** Клиент получает webhook — нужно ли ему дополнительно запрашивать данные через API?
**Решение:** Полные данные в payload — клиенту не нужен callback
**Альтернативы:** Notification с ID → клиент запрашивает данные (дополнительная нагрузка на API)
**Статус:** реализовано

### 2026-04-05: ClickHouse для webhook delivery logs
**Контекст:** Каждый webhook delivery логируется с полным request/response body. Объём растёт быстро.
**Решение:** ClickHouse — append-only, быстрая аналитика, колоночное хранение
**Альтернативы:** PostgreSQL (медленнее на объёме, дорогой storage)
**Статус:** реализовано

### 2026-04-05: Laravel Horizon вместо ручного queue:work
**Контекст:** Webhook dispatch — async job, нужен reliable queue processing
**Решение:** Horizon — dashboard, auto-scaling, monitoring, retry management
**Альтернативы:** Ручной `queue:work` в Docker (нет мониторинга, нет dashboard)
**Статус:** реализовано

### 2026-04-05: Обязательный фильтр company_numbers в webhook подписках
**Контекст:** Клиент подписывается на webhooks — по каким компаниям?
**Решение:** company_numbers — обязательное поле, клиент выбирает конкретные компании
**Альтернативы:** Опциональное (все события) — слишком много шума для клиента
**Статус:** реализовано
