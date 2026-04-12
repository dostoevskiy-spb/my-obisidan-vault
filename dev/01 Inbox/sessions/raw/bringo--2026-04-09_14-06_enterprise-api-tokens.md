---
type: session-log-raw
project: bringo
submodule: backend, shared-models, client-api
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-09_14-06_enterprise-api-tokens.md
session_date: 2026-04-09
tags: [session-log-raw, bringo, enterprise, api-tokens, grpc]
created: 2026-04-13
status: unprocessed
---

# Сессия: [backend, shared-models, client-api] Enterprise-подписка и управление API-токенами из ЛК
**Дата:** 2026-04-09 14:06
**Субмодули:** backend, shared-models, client-api, front (задача для фронтендера)
**Цель:** Спроектировать и реализовать Enterprise-подписку + управление API-токенами из личного кабинета сайта

---

## Лог

### 14:06 — Начало
- Задача: добавить Enterprise-подписку (ручная активация) + управление API-токенами client-api из ЛК сайта
- Контекст: client-api уже имеет полноценную систему токенов (SHA256, soft delete, Filament UI), но управление только через отдельный портал

### 14:08 — Исследование кодовой базы (3 параллельных агента)
- Что: запущены 3 Explore-агента для анализа backend (подписки/биллинг), client-api (токены), front (ЛК)
- Результат: получена полная картина архитектуры
- Детали:
  - Backend: подписки в `billing.subscription`, 3 периода (MONTHLY/ANNUALLY/DAILY), 2 платёжные системы (STRIPE/NONE), gRPC BillingService с 10 методами
  - Client-API: Laravel 13 + FrankenPHP, таблицы `api.clients` и `api.tokens`, TokenService (create/resolve/revoke), SHA256 хеширование, Filament Admin + Client Portal
  - Front: Next.js 16, Pages Router, ЛК через `/account/profile/*`, gRPC для связи с backend, уже есть компонент EnterpriseSubscription.tsx (карточка "Contact us")
  - Критически: backend и client-api используют ОДНУ PostgreSQL БД, разные schema (public/billing vs api)

### 14:15 — Архитектурное проектирование (Plan-агент)
- Что: запущен Plan-агент для проектирования архитектуры
- Результат: получен детальный план с 5 фазами
- Ключевые решения:
  - Backend напрямую работает с `api.*` таблицами через DBAL (не REST/gRPC между сервисами)
  - Новый enum SubscriptionTypeEnum (STANDARD/ENTERPRISE) вместо расширения SubscriptionPeriod
  - Новый gRPC-сервис ApiTokenService (отдельно от BillingService)
  - Связь User→ApiClient через `website_user_id` в `api.clients`

### 14:20 — Уточнение файлов для плана
- Что: прочитаны критические файлы: Subscription.php (entity), BillingProtobufTransformer.php, SubscriptionService.php, ProfilePage, LeftMenu, consts.ts, AccountPage routing
- Результат: подтверждена архитектура, уточнены точки интеграции

### 14:25 — Первая итерация плана → замечания пользователя
- Решение пользователя (4 замечания):
  1. `user_id` → `website_user_id` (для ясности что это пользователь с сайта)
  2. Бамп версии shared-models в package.json (не забыть)
  3. FK constraint на `public.user(user_id)` нужен
  4. Enterprise выдаётся независимо от наличия обычной подписки

### 14:30 — Вторая итерация → замечания пользователя
- Решение пользователя (3 замечания):
  1. composer.json для shared-models бампить не надо
  2. Enterprise бессрочный (endDate=null), прекращение только командой revoke; при отзыве: подписка деактивируется + api.clients.is_active=false
  3. Фронт не реализовывать — описать задачу для фронтендера с контрактом API

### 14:35 — Третья итерация → замечание про SDK ссылки
- Решение пользователя: на странице API в ЛК сверху должно быть описание API и ссылки на документацию (Swagger), OpenAPI spec, SDK-пакеты
- Что: проверил GenerateSdksCommand.php — нашёл точные имена пакетов: bringo-co-uk/api-sdk-php, bringo-api-sdk, @bringo-co-uk/api-sdk, github.com/bringo-co-uk/api-sdk-go

### 14:40 — Четвёртая итерация → замечание про token_type
- Решение пользователя: на фронте не давать выбирать тип токена, бекенд всегда создаёт production, но вся логика sandbox остаётся в коде

### 14:42 — План утверждён
- План: [Enterprise API Tokens](plans/2026-04-09_14-06_enterprise-api-tokens.md)
- Краткое содержание: Enterprise-подписка (бессрочная, ручная активация/отзыв) + gRPC ApiTokenService для управления токенами client-api из ЛК + задача для фронтендера с контрактом API и ссылками на документацию/SDK

### 14:45 — Фаза 1: Proto-файлы
- Что: расширил Subscription.proto (SubscriptionType enum + поле field 12), создал ApiToken.proto и ApiTokenService.proto, бамп версии shared-models 0.0.407→0.0.408
- Файлы: shared-models/proto/Api/V2/Model/Billing/Subscription.proto, shared-models/proto/Api/V2/Model/ApiToken/ApiToken.proto, shared-models/proto/Api/V2/Grpc/ApiToken/ApiTokenService.proto, shared-models/package.json

### 14:50 — Фаза 2: Миграции
- Что: создал миграцию для billing.subscription.subscription_type_id (DEFAULT 0) и для api.clients.website_user_id (FK→public.user, ON DELETE SET NULL, unique partial index)
- Файлы: migration/migrations/db/1775733127_ddl_add_subscription_type_id.php, client-api/database/migrations/2026_04_09_000001_add_website_user_id_to_clients.php

### 14:55 — Фаза 3: Backend — enum, entity, сервисы
- Что: создал SubscriptionTypeEnum, расширил Subscription entity (subscriptionType field, конструктор с enterprise-логикой endDate=null), создал EnterpriseApiClientService (DBAL для api.* таблиц), расширил SubscriptionService (createEnterprise, getActiveEnterpriseSubscription, cancel guard), создал DTO CreateEnterpriseSubscription
- Файлы: backend/src/Billing/Enum/SubscriptionTypeEnum.php, backend/src/Billing/Entity/Subscription.php, backend/src/Billing/Service/EnterpriseApiClientService.php, backend/src/Billing/Service/SubscriptionService.php, backend/src/Billing/Service/Dto/CreateEnterpriseSubscription.php

### 15:00 — Фаза 3: Консольные команды
- Что: создал billing:enterprise-subscription:create (email + --credits) и billing:enterprise-subscription:revoke (деактивирует подписку + api.clients.is_active=false)
- Файлы: backend/src/Billing/Console/EnterpriseSubscriptionCreateCommand.php, backend/src/Billing/Console/EnterpriseSubscriptionRevokeCommand.php

### 15:05 — Фаза 3: gRPC, Transformer, Voter
- Что: обновил BillingProtobufTransformer (subscription_type mapping), создал gRPC контроллер ApiTokenService (GetClientInfo, ListTokens, CreateToken, RevokeToken — все с enterprise check), расширил UserSubscriptionVoter (HAS_ENTERPRISE_SUBSCRIPTION), добавил User::hasActiveEnterpriseSubscription()
- Файлы: backend/src/Billing/Transformer/BillingProtobufTransformer.php, backend/src/Controller/V2/Grpc/ApiToken/ApiTokenService.php, backend/src/Security/Voter/UserSubscriptionVoter.php, backend/src/Entity/User.php

### 15:10 — Фаза 3: Аудит проверок подписки
- Что: проверил все места где проверяется подписка
- Результат: всё корректно
- Детали: 
  - checkExpiredSubscriptions() — enterprise не попадёт (endDate=NULL, условие end_date < NOW() не сработает)
  - CancelSubscription gRPC — добавлен guard isEnterprise()
  - cancel() в SubscriptionService — guard добавлен  
  - UserSubscriptionVoter.HAS_ACTIVE_SUBSCRIPTION — enterprise тоже active, корректно
  - Файл: backend/src/Controller/V2/Grpc/Billing/BillingService.php (добавлен guard)

### 15:15 — Фаза 4: Client-API
- Что: добавил website_user_id в модель ApiClient ($fillable, casts), добавил поле в Filament ClientResource (disabled, с helperText)
- Файлы: client-api/app/Modules/Auth/Models/ApiClient.php, client-api/app/Filament/Resources/ClientResource.php
