---
type: session-plan-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-09_14-06_enterprise-api-tokens.md
session_date: 2026-04-09
tags:
  - session-plan
  - raw
  - bringo
created: 2026-04-26
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
- Через `php bin/console db:create-migration` в backend
- SQL: `ALTER TABLE billing.subscription ADD COLUMN subscription_type_id INTEGER NOT NULL DEFAULT 0;`
- DEFAULT 0 = STANDARD для всех существующих записей

**2.2. Client-API миграция — добавить `user_id` в `api.clients`**
- Новый файл: `client-api/database/migrations/2026_04_10_000001_add_user_id_to_clients.php`
- SQL:
  ```sql
  ALTER TABLE api.clients ADD COLUMN website_user_id INTEGER DEFAULT NULL REFERENCES public.user(user_id) ON DELETE SET NULL;
  CREATE UNIQUE INDEX idx_clients_website_user_id ON api.clients(website_user_id) WHERE website_user_id IS NOT NULL;
  ```

### Фаза 3: Backend (Symfony)

**3.1. Новый enum `SubscriptionTypeEnum`**
- Новый файл: `backend/src/Billing/Enum/SubscriptionTypeEnum.php`
- Значения: `STANDARD = 0`, `ENTERPRISE = 1`

**3.2. Расширить entity `Subscription`**
- Файл: `backend/src/Billing/Entity/Subscription.php`
- Добавить поле `subscription_type_id` (Column, enumType: SubscriptionTypeEnum, default STANDARD)
- Добавить методы: `getSubscriptionType()`, `isEnterprise(): bool`
- В конструкторе: новый параметр `SubscriptionTypeEnum $type = SubscriptionTypeEnum::STANDARD`
- Для Enterprise: `endDate = null`, `nextPaymentDate = null` (бессрочная). Конструктор сейчас вычисляет endDate через match по period — нужно обойти для enterprise (если `$type === ENTERPRISE`, ставить `endDate = null`)

**3.3. Новый сервис `EnterpriseApiClientService`**
- Новый файл: `backend/src/Billing/Service/EnterpriseApiClientService.php`
- Использует DBAL (не ORM) для работы с `api.*` таблицами
- Методы:
  - `findOrCreateApiClient(int $userId, string $email, string $name): int` — возвращает client_id (ищет по `website_user_id`)
  - `getApiClientByUserId(int $userId): ?array` — данные клиента (по `website_user_id`)
  - `listTokens(int $clientId): array` — все токены (без plain-text)
  - `createToken(int $clientId, string $name, string $type = 'production'): array` — возвращает `['id' => ..., 'plain_text' => 'bcu_live_...']`
  - `revokeToken(int $tokenId, int $clientId): void` — `UPDATE SET revoked_at = NOW()`
- Логика создания токена (зеркалит client-api `TokenService`):
  ```php
  $prefix = $type === 'sandbox' ? 'bcu_sand_' : 'bcu_live_';
  $plain = $prefix . bin2hex(random_bytes(32));
  $hash = hash('sha256', $plain);
  $tokenPrefix = substr($plain, 0, 13);
  // INSERT INTO api.tokens ...
  ```

**3.4. Консольная команда `billing:enterprise-subscription:create`**
- Новый файл: `backend/src/Billing/Console/EnterpriseSubscriptionCreateCommand.php`
- Аргументы: `email` (required), `--credits` (optional — начальный баланс кредитов API-клиента)
- Enterprise подписка **бессрочная** (`endDate = null`, `nextPaymentDate = null`). Прекратить можно только командой отзыва.
- Флоу:
  1. Найти пользователя по email
  2. Проверить нет ли уже активной **enterprise** подписки (обычная подписка не мешает — enterprise выдаётся независимо)
  3. Создать Subscription с `SubscriptionTypeEnum::ENTERPRISE`, `PaymentSystemEnum::NONE`, `SubscriptionPeriodEnum::ANNUALLY`, `endDate = null`, `nextPaymentDate = null`
  4. `activate()`, `changeStatus(ACTIVE)`
  5. Создать RowBalance для подписки
  6. Создать/найти `api.clients` запись через `EnterpriseApiClientService::findOrCreateApiClient()`
  7. Если указан `--credits` — установить `credit_balance`

**3.4b. Консольная команда `billing:enterprise-subscription:revoke`**
- Новый файл: `backend/src/Billing/Console/EnterpriseSubscriptionRevokeCommand.php`
- Аргументы: `email` (required)
- Флоу:
  1. Найти пользователя по email
  2. Найти активную enterprise подписку
  3. Деактивировать подписку (`deactivate()`, `changeStatus(CANCELED)`)
  4. Пометить `api.clients` как неактивный (`is_active = false`) — все токены клиента перестанут работать (client-api проверяет `client.is_active` при аутентификации)
  5. Обычная подписка пользователя (если есть) НЕ затрагивается

**3.5. Расширить `SubscriptionService`**
- Файл: `backend/src/Billing/Service/SubscriptionService.php`
- Новый DTO `CreateEnterpriseSubscription` (userId, credits)
- Новый метод `createEnterprise(CreateEnterpriseSubscription $dto): Subscription`
- Новый метод `getActiveEnterpriseSubscription(int $userId): ?Subscription` — поиск активной enterprise-подписки
- В `cancel()`: добавить guard — enterprise подписки нельзя отменять через gRPC (только через консольную команду)
- В `getActiveSubscription()`: оставить как есть (возвращает первую активную) — но учесть что теперь может быть две активных (standard + enterprise)

**3.5b. Аудит существующих мест проверки подписки**

Важно: у пользователя может быть одновременно обычная подписка И enterprise. Нужно проверить все места где проверяется `hasActiveSubscription()` / `HAS_ACTIVE_SUBSCRIPTION` и убедиться что они корректно работают с двумя подписками:

- `UserSubscriptionVoter` — `HAS_ACTIVE_SUBSCRIPTION` проверяет `user.hasActiveSubscription()`. Это поле основано на коллекции subscriptions у User. Если хотя бы одна активна — true. **Работает корректно**, обе подписки удовлетворяют условию.
- `BillingService.php` (gRPC) — `GetActiveSubscription` возвращает одну подписку. Нужно решить: возвращать обычную или enterprise? **Решение**: возвращать обычную (standard) подписку, enterprise доступна через отдельный метод `GetClientInfo` в `ApiTokenService`.
- `BillingScheduler` — проверка истечения подписок. Enterprise бессрочная (`endDate = null`), значит не попадёт в `checkExpiredSubscriptions()`. **Работает корректно**.
- `SubscriptionPriceService.getSubscriptionAmount()` — match по period. Enterprise использует ANNUALLY формально, но price не важна (PaymentSystem = NONE). **Работает корректно**.
- Фронт — `user.activeSubscription` используется для показа информации о подписке в Billing. Нужно возвращать обе подписки или enterprise отдельно. **См. задачу для фронта.**

**3.6. Обновить `BillingProtobufTransformer`**
- Файл: `backend/src/Billing/Transformer/BillingProtobufTransformer.php`
- В `transformSubscriptionToProtobuf()`: маппить `subscription_type` на proto

**3.7. Новый gRPC контроллер `ApiTokenService`**
- Новый файл: `backend/src/Controller/V2/Grpc/ApiToken/ApiTokenService.php`
- Методы: `ListTokens`, `CreateToken`, `RevokeToken`, `GetClientInfo`
- Каждый метод: `#[IsGranted('ROLE_USER')]` + проверка `subscription.isEnterprise()`
- Проверка изоляции: фильтрация по `website_user_id` текущего пользователя

**3.8. Новый Voter атрибут (опционально)**
- Файл: `backend/src/Security/Voter/UserSubscriptionVoter.php`
- Добавить `HAS_ENTERPRISE_SUBSCRIPTION` — проверяет наличие active enterprise подписки

### Фаза 4: Client-API (Laravel)

**4.1. Обновить модель `ApiClient`**
- Файл: `client-api/app/Modules/Auth/Models/ApiClient.php`
- Добавить `website_user_id` в `$fillable` и `casts`

**4.2. Обновить Filament admin panel**
- Файл: `client-api/app/Filament/Resources/ClientResource.php`
- Показать `website_user_id` как read-only поле (информационно)

### Фаза 5: Frontend — задача для фронтендера

**Что нужно сделать:**

В личном кабинете на сайте добавить новый раздел "API" для пользователей с Enterprise-подпиской. Раздел позволяет управлять API-токенами для нашего публичного API (client-api).

**Поведение:**

1. В левом меню ЛК (`/account/profile/...`) появляется пункт "API". Пункт виден **только** если у пользователя есть активная enterprise-подписка. Определяется по новому полю `subscription_type` в proto-модели Subscription (значение `ENTERPRISE = 1`). У пользователя может быть одновременно и обычная подписка, и enterprise — нужно проверять через новый gRPC-метод `ApiTokenService.GetClientInfo` (если вернул данные — enterprise есть).

2. На странице `/account/profile/api` сверху — краткое описание API и ссылки:
   - Текст: краткое описание что такое Bringo Public API (доступ к данным UK Companies House через REST API)
   - Ссылки:
     - **API Documentation (Swagger UI)**: `https://api.bringo.co.uk/docs/api`
     - **OpenAPI Spec (JSON)**: `https://api.bringo.co.uk/docs/api.json`
     - **OpenAPI Spec (версионированные)**: `https://api.bringo.co.uk/specs/latest.json`
     - **SDKs**:
       - PHP: `bringo-co-uk/api-sdk-php` (Packagist, `composer require bringo-co-uk/api-sdk-php`)
       - Python: `bringo-api-sdk` (PyPI, `pip install bringo-api-sdk`)
       - TypeScript: `@bringo-co-uk/api-sdk` (npm, `npm install @bringo-co-uk/api-sdk`)
       - Go: `github.com/bringo-co-uk/api-sdk-go` (`go get github.com/bringo-co-uk/api-sdk-go`)
     - **MCP Server**: ссылка на документацию MCP-сервера для AI-агентов
   
   Ниже — основной контент:
   - Информация об API-клиенте: имя, email, баланс кредитов (`credit_balance`)
   - Таблица API-токенов: prefix (например `bcu_live_a1b2`), название, тип (production/sandbox бейджем), статус (active/revoked), последнее использование, дата создания
   - Кнопка "Create Token" — открывает модалку с формой: только название токена (текст, обязательное). Тип токена НЕ выбирается пользователем — всегда создаётся `production` (захардкожено на бекенде). Вся логика поддержки sandbox остаётся в коде, но на UI не выводится.
   - После создания токена — показать plain-text токен **один раз** с предупреждением "Скопируйте токен сейчас — он больше не будет показан". Кнопка copy-to-clipboard.
   - Кнопка "Revoke" на каждом активном токене — с подтверждением ("Вы уверены? Токен перестанет работать немедленно")

3. Карточка "Enterprise" на странице выбора плана (Billing) — если у пользователя уже есть enterprise подписка, вместо "Contact us" показывать ссылку "Manage API" на `/account/profile/api`.

**gRPC-контракт (ApiTokenService):**

```protobuf
service ApiTokenService {
  // Получить информацию об API-клиенте текущего пользователя.
  // Если у пользователя нет enterprise подписки — вернёт ошибку PERMISSION_DENIED.
  rpc GetClientInfo(GetApiClientInfoRequest) returns (GetApiClientInfoResponse);

  // Список всех токенов (включая отозванные). Plain-text НЕ возвращается.
  rpc ListTokens(ListApiTokensRequest) returns (ListApiTokensResponse);

  // Создать новый токен. Возвращает plain-text ОДИН РАЗ.
  rpc CreateToken(CreateApiTokenRequest) returns (CreateApiTokenResponse);

  // Отозвать токен (soft delete). Токен перестаёт работать немедленно.
  rpc RevokeToken(RevokeApiTokenRequest) returns (RevokeApiTokenResponse);
}

// === Requests/Responses ===

message GetApiClientInfoRequest {}
message GetApiClientInfoResponse {
  ApiClientInfo client = 1;
}

message ListApiTokensRequest {}
message ListApiTokensResponse {
  repeated ApiToken tokens = 1;
}

message CreateApiTokenRequest {
  string name = 1;          // Название токена (обязательное)
  // token_type не передаётся — бекенд всегда создаёт "production".
  // Поле оставлено в proto для будущей расширяемости, но игнорируется.
  string token_type = 2;
}
message CreateApiTokenResponse {
  ApiToken token = 1;       // Метаданные токена
  string plain_text = 2;    // Полный plain-text токен (bcu_live_...) — показать один раз!
}

message RevokeApiTokenRequest {
  uint64 token_id = 1;
}
message RevokeApiTokenResponse {
  bool success = 1;
}

// === Models ===

message ApiToken {
  uint64 id = 1;
  string name = 2;
  string token_prefix = 3;   // Первые 13 символов (bcu_live_a1b2)
  string token_type = 4;     // "production" или "sandbox"
  int64 credit_limit = 5;    // Лимит кредитов на токен (0 = unlimited)
  int64 credits_used = 6;    // Использовано кредитов
  string last_used_at = 7;   // ISO 8601 datetime или пусто
  string expires_at = 8;     // ISO 8601 datetime или пусто (бессрочный)
  string created_at = 9;     // ISO 8601 datetime
  bool is_active = 10;       // true если не отозван и не истёк
}

message ApiClientInfo {
  uint64 id = 1;
  string name = 2;
  string email = 3;
  int64 credit_balance = 4;  // Баланс кредитов
  bool is_active = 5;
}
```

**Расширение Subscription.proto:**
К существующему message `Subscription` добавляется:
```protobuf
enum SubscriptionType {
  STANDARD = 0;
  ENTERPRISE = 1;
}
SubscriptionType subscription_type = 12;
```

---

## Ключевые файлы

| Файл | Действие |
|------|----------|
| `shared-models/proto/Api/V2/Model/Billing/Subscription.proto` | Расширить (SubscriptionType enum + поле) |
| `shared-models/proto/Api/V2/Grpc/ApiToken/ApiTokenService.proto` | Создать |
| `shared-models/proto/Api/V2/Model/ApiToken/ApiToken.proto` | Создать |
| `shared-models/package.json` | Бамп версии |
| `backend/src/Billing/Enum/SubscriptionTypeEnum.php` | Создать |
| `backend/src/Billing/Entity/Subscription.php` | Расширить (subscription_type_id, isEnterprise) |
| `backend/src/Billing/Service/EnterpriseApiClientService.php` | Создать (DBAL-сервис для api.*) |
| `backend/src/Billing/Service/SubscriptionService.php` | Расширить (createEnterprise, getActiveEnterprise) |
| `backend/src/Billing/Console/EnterpriseSubscriptionCreateCommand.php` | Создать |
| `backend/src/Billing/Console/EnterpriseSubscriptionRevokeCommand.php` | Создать |
| `backend/src/Controller/V2/Grpc/ApiToken/ApiTokenService.php` | Создать (gRPC контроллер) |
| `backend/src/Billing/Transformer/BillingProtobufTransformer.php` | Расширить (subscription_type) |
| `backend/src/Security/Voter/UserSubscriptionVoter.php` | Расширить (HAS_ENTERPRISE_SUBSCRIPTION) |
| `client-api/database/migrations/..._add_website_user_id.php` | Создать |
| `client-api/app/Modules/Auth/Models/ApiClient.php` | Расширить (website_user_id) |

## Верификация

1. **Создание enterprise**: `php bin/console billing:enterprise-subscription:create yearly-active@bcu.localhost` → подписка создалась (type=ENTERPRISE, endDate=null, isActive=true) + запись в `api.clients` с `website_user_id`
2. **Отзыв enterprise**: `php bin/console billing:enterprise-subscription:revoke yearly-active@bcu.localhost` → подписка деактивирована + `api.clients.is_active = false`
3. **Сосуществование**: создать enterprise для пользователя с обычной подпиской → обе активны, `GetActiveSubscription` возвращает обычную, `GetClientInfo` возвращает enterprise-клиента
4. **gRPC токены**: вызвать CreateToken → получить plain-text → ListTokens показывает токен (без plain-text) → RevokeToken → токен помечен revoked
5. **Изоляция**: gRPC-методы ApiTokenService для пользователя БЕЗ enterprise → PERMISSION_DENIED
6. **Интеграция с client-api**: созданный через gRPC токен работает в client-api (`curl -H "Authorization: Bearer bcu_live_..." https://nginx/public-api/v1/status`)
