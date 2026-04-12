---
type: session-plan-raw
project: bringo
submodule: backend, shared-models, client-api
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-09_14-06_enterprise-api-tokens.md
session_date: 2026-04-09
tags: [session-plan-raw, bringo, enterprise, api-tokens, architecture]
created: 2026-04-13
status: unprocessed
---

# Plan: Enterprise-подписка + управление API-токенами из ЛК

## Context

Нужно дать пользователям с Enterprise-подпиской возможность управлять API-токенами клиентского модуля (`client-api`) прямо из личного кабинета на сайте. Сейчас токены управляются только через Filament-портал client-api. Enterprise — новый тип подписки, активируемый вручную (не через Stripe).

## Архитектурное решение: Backend напрямую работает с `api.*` таблицами

**Выбор**: Вариант A — backend (Symfony) напрямую читает/пишет в `api.clients` и `api.tokens` через DBAL.

**Почему**:
- Обе системы используют одну PostgreSQL БД (backend: `public`/`billing` schema, client-api: `api` schema)
- Логика управления токенами тривиальна (~30 строк): generate prefix + random hex, SHA256 hash, INSERT/SELECT/UPDATE
- Нет необходимости в REST/gRPC между сервисами — это добавит сетевую зависимость и проблему аутентификации (chicken-and-egg)
- Client-API продолжает быть authority для валидации токенов при API-запросах; backend только управляет lifecycle

**Связь User → ApiClient**: добавить колонку `website_user_id` в `api.clients` (nullable, unique index, FK на `public.user(user_id)`). При активации enterprise создаётся запись в `api.clients` привязанная к user.

---

## Фазы реализации

### Фаза 1: Shared Models (Proto)

**1.1. Расширить `Subscription.proto`**
- Файл: `shared-models/proto/Api/V2/Model/Billing/Subscription.proto`
- Добавить enum `SubscriptionType { STANDARD = 0; ENTERPRISE = 1; }` внутри message Subscription
- Добавить поле `SubscriptionType subscription_type = 12;`

**1.2. Новый proto-файл `ApiTokenService.proto`**
- Файл: `shared-models/proto/Api/V2/Grpc/ApiToken/ApiTokenService.proto`
- Новый сервис:
  ```protobuf
  service ApiTokenService {
    rpc ListTokens(ListApiTokensRequest) returns (ListApiTokensResponse);
    rpc CreateToken(CreateApiTokenRequest) returns (CreateApiTokenResponse);
    rpc RevokeToken(RevokeApiTokenRequest) returns (RevokeApiTokenResponse);
    rpc GetClientInfo(GetApiClientInfoRequest) returns (GetApiClientInfoResponse);
  }
  ```

**1.3. Новый proto-файл `ApiToken.proto`**
- Файл: `shared-models/proto/Api/V2/Model/ApiToken/ApiToken.proto`
- Message `ApiToken`: id, name, token_prefix, token_type (production/sandbox), credit_limit, credits_used, last_used_at, expires_at, created_at, is_active
- Message `ApiClientInfo`: id, name, email, credit_balance, is_active

**1.4. Поднять версию пакета shared-models**
- Файл: `shared-models/package.json` — бампнуть версию (minor)

**1.5. Регенерация proto-классов**
- Backend: обновить `bringo/shared-models` в composer.json, `composer update bringo/shared-models`, `composer gen-proto`
- Front: обновить `@bringo/shared-models` в package.json, `yarn install`

### Фаза 2: Миграции БД

**2.1. Backend миграция — добавить `subscription_type_id` в `billing.subscription`**
- SQL: `ALTER TABLE billing.subscription ADD COLUMN subscription_type_id INTEGER NOT NULL DEFAULT 0;`

**2.2. Client-API миграция — добавить `website_user_id` в `api.clients`**
- SQL:
  ```sql
  ALTER TABLE api.clients ADD COLUMN website_user_id INTEGER DEFAULT NULL REFERENCES public.user(user_id) ON DELETE SET NULL;
  CREATE UNIQUE INDEX idx_clients_website_user_id ON api.clients(website_user_id) WHERE website_user_id IS NOT NULL;
  ```

### Фаза 3: Backend (Symfony)

- SubscriptionTypeEnum (STANDARD=0, ENTERPRISE=1)
- Subscription entity: subscription_type_id, isEnterprise()
- EnterpriseApiClientService: DBAL для api.* таблиц
- SubscriptionService: createEnterprise(), getActiveEnterpriseSubscription()
- Консольные команды: enterprise-subscription:create, enterprise-subscription:revoke
- BillingProtobufTransformer: subscription_type mapping
- gRPC ApiTokenService: GetClientInfo, ListTokens, CreateToken, RevokeToken
- UserSubscriptionVoter: HAS_ENTERPRISE_SUBSCRIPTION

### Фаза 4: Client-API (Laravel)

- ApiClient model: website_user_id
- Filament ClientResource: показать website_user_id

### Фаза 5: Frontend — задача для фронтендера

- Раздел "API" в ЛК: управление токенами, описание API, ссылки на документацию/SDK
- gRPC-контракт ApiTokenService с 4 методами
