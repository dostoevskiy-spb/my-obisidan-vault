---
type: session-log
project: bringo
submodule: api
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-05_00-52_api-webhooks.md
session_date: 2026-04-05
tags: [session-log, bringo, api, webhooks]
created: 2026-04-07
---

# [api] Webhook-система — relay, подписки, доставка, биллинг

**Проект:** [[Bringo]]
**Субмодуль:** api (Laravel 13 REST API, Filament 5, PostgreSQL + ClickHouse)
**Дата:** 2026-04-05

## Бизнес-контекст
Клиенты Public API должны получать уведомления об изменениях данных Companies House (обновления компаний, директоров, PSC) в реальном времени, без необходимости поллинга. Это была запланированная фича из "будущие фичи после MVP" (EPIC.md, секция 8).

## Цель
Реализовать полную webhook-систему: от получения событий из backend до доставки клиентам с подписью, retry и мониторингом.

## Что реализовано

### База данных
- Таблица `api.webhook_subscriptions` (PostgreSQL): client_id (FK→api.clients), url VARCHAR(2048), secret VARCHAR(64), events JSON, company_numbers JSON (обязательное поле), active BOOL, timestamps
- Поля `webhook_*` в `api.clients`: webhook_enabled, webhook_max_subscriptions
- ClickHouse: расширена таблица логов — добавлены 3 поля для webhook delivery (event_type, subscription_id, delivery_status)

### API эндпоинты (9 штук)
- `POST /v1/webhooks` — создание подписки (валидация URL через SafeWebhookUrl rule + DNS resolve, генерация HMAC secret)
- `GET /v1/webhooks` — список подписок клиента с пагинацией
- `GET /v1/webhooks/{id}` — детали подписки
- `PUT /v1/webhooks/{id}` — обновление (url, events, company_numbers, active)
- `DELETE /v1/webhooks/{id}` — удаление с проверкой ownership
- `POST /v1/webhooks/{id}/test` — отправка тестового payload
- `POST /v1/webhooks/{id}/retry` — повторная отправка failed delivery
- `GET /v1/webhooks/{id}/deliveries` — список доставок с фильтрацией
- `GET /v1/webhooks/{id}/deliveries/{delivery_id}` — детали доставки (request/response body)

### Ключевые компоненты
- `WebhookDispatchService` (app/Modules/Webhook/) — основной сервис: формирование payload, HMAC-SHA256 подпись (payload + timestamp + secret), HTTP доставка
- `DispatchWebhookJob` (app/Jobs/) — async доставка через Horizon, retry 3×, exponential backoff, биллинг: каждый delivery списывает кредиты через BillingService
- `ProcessWebhookInboxCommand` — Laravel scheduler: обработка входящих событий из Redis inbox
- `WebhookSubscriptionCache` + Observer — Redis кеш подписок для производительности, инвалидация через Observer при CRUD
- `WebhookDeliveryLogger` — логирование в ClickHouse (полный request/response body)
- `WebhookEventType` enum — типы событий (company.updated, officer.updated, psc.updated, etc.)
- `SafeWebhookUrl` Rule — валидация URL (DNS resolve, запрет private IP)
- `WebhookController` + 3 Request класса + Resource

### Backend (Symfony) интеграция
- `ApiWebhookRelayHandler` (Symfony MessageHandler) — получает EntityUpdatedEvent, relay через Redis в API
- `CompanyDao.getCompanyNumberById()` — lookup company_number по entity ID
- `messenger.yaml` — новый transport `api-webhook-relay` + consumer
- `compose.d/backend/` — новый consumer container

### Filament UI
- `ClientResource` — секция Webhooks + `WebhookSubscriptionsRelationManager` (CRUD подписок на странице клиента)
- `WebhookDeliveryResource` — list из ClickHouse, view с request/response body, retry action из админки
- `WebhookDeliveryQueryService` — прослойка для ClickHouse запросов
- Horizon ссылка в AdminPanelProvider для мониторинга очередей

### Конфигурация
- `config/horizon.php` + HorizonServiceProvider — queue `webhooks`, 3 workers, maxTries: 3, timeout: 30s
- EndpointPrice seed: `webhook.delivery` с ценой за доставку
- Settings: webhook_enabled (global toggle)

### Тесты
- 16 feature-тестов для webhook API: CRUD подписок, валидация, delivery, retry, billing
- Общий suite после сессии: 176 тестов, 763 assertions — все зелёные
- Проблемы в тестах: `api_client` vs `client` attribute key (fix: переименование), custom validation error format (fix: assertJsonPath)

## Архитектурные решения

- **JSON relay через Redis** (не RabbitMQ) — Backend (Symfony) → EntityUpdatedEvent (Protobuf) → fanout exchange → Symfony consumer → Redis → API Laravel consumer → dispatch. **Почему:** API (Laravel) не подключён к RabbitMQ, Redis уже используется. Loose coupling между модулями.
- **Full payload** (не notification-only) — клиент получает полные данные в webhook, не нужен callback на API. **Почему:** меньше нагрузки, проще для клиента.
- **Horizon** вместо ручного queue:work — управление workers, мониторинг, auto-scaling. **Почему:** production-ready решение, dashboard.
- **Кеш подписок в Redis** — при dispatch не ходим в PostgreSQL за подписками. **Почему:** webhook dispatch на горячем пути, latency критична.
- **ClickHouse для delivery logs** — полный request/response body каждой доставки. **Почему:** объём данных будет расти быстро, ClickHouse оптимизирован для append-only аналитических запросов.
- **company_numbers обязательное** — клиент ДОЛЖЕН указать за какие компании хочет webhooks. **Почему:** без фильтра клиент получал бы все события — слишком много шума.

## Проблемы и решения
- `api_client` vs `client` в тестах — attribute key в request validation отличался от factory key. Fix: унифицировали на `api_client`.
- Custom validation error format `error.errors` — стандартный `assertJsonValidationErrors` не работал. Fix: `assertJsonPath('error.errors.url.0', ...)`.

## Связи
- [[Bringo]]
- [[bringo--2026-04-04--client-portal-plan|План клиентского портала]]
