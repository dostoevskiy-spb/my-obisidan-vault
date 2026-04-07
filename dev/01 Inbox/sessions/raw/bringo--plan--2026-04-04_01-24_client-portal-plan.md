---
type: session-plan-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-04_01-24_client-portal-plan.md
session_date: 2026-04-04
tags: [session-plan, raw, bringo]
created: 2026-04-07
status: unprocessed
---

# План: Клиентский портал API — роли, invite, ЛК, логи, финансы

## Контекст

API-проект (`api/`) — Laravel 13 + Filament 5 REST API для UK Companies House. Сейчас есть только админ-панель (`/admin`) и API-аутентификация через Bearer-токены. Нужно добавить:
1. Клиентский портал с ролями (admin vs client)
2. Создание клиентов админом с invite-email
3. ЛК клиента (дашборд + токены)
4. Импорт пользователей из `public.user` (таблица backend Symfony)
5. Просмотр/фильтрация API request logs (из ClickHouse)
6. Новый эндпоинт с иерархическими финансовыми таблицами

**Решения пользователя:**
- Несколько ClientUser на один ApiClient (multi-user)
- Всегда invite-ссылка (не копируем пароль при импорте)
- Реальная отправка email (SMTP, Mailcatcher на локалке)
- Иерархическая структура финансов (как в backend)
- Все письма на английском, шаблон как в backend (base-new.html.twig)
- Панель логов запросов и для клиента, и для админа (в т.ч. на странице просмотра клиента)

---

## Фаза 1: Модель ClientUser + Auth

### 1.1 Миграция `api.client_users`

**Создать:** `database/migrations/2026_04_04_000008_create_client_users_table.php`

```sql
CREATE TABLE api.client_users (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES api.clients(id) ON DELETE CASCADE,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) DEFAULT NULL,  -- NULL до принятия инвайта
    invite_token VARCHAR(64) DEFAULT NULL,
    invite_expires_at TIMESTAMP(0) DEFAULT NULL,
    last_login_at TIMESTAMP(0) DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    imported_from_user_id INTEGER DEFAULT NULL,  -- ссылка на public.user.user_id
    remember_token VARCHAR(100) DEFAULT NULL,
    created_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_client_users_client_id ON api.client_users(client_id);
```

**Без UNIQUE на client_id** — несколько пользователей на одного клиента.

### 1.2 Миграция `api.client_password_resets`

**Создать:** `database/migrations/2026_04_04_000009_create_client_password_resets_table.php`

Стандартная Laravel-таблица для password reset tokens в schema `api`.

### 1.3 Модель ClientUser

**Создать:** `app/Modules/Auth/Models/ClientUser.php`

- Extends `Authenticatable` (для Filament login)
- `$connection = 'api'`, `$table = 'api.client_users'`
- `belongsTo(ApiClient::class, 'client_id')`
- Реализует `FilamentUser` interface → `canAccessPanel('client')` returns true
- `getFilamentName()` возвращает `"{first_name} {last_name}"`
- `getFullNameAttribute()`: accessor для полного имени

### 1.4 Обновить `config/auth.php`

**Изменить:** `config/auth.php`

```php
'guards' => [
    'web' => [...],     // существующий (admin)
    'client' => [
        'driver' => 'session',
        'provider' => 'client_users',
    ],
],
'providers' => [
    'users' => [...],   // существующий (admin)
    'client_users' => [
        'driver' => 'eloquent',
        'model' => ClientUser::class,
    ],
],
'passwords' => [
    'users' => [...],
    'client_users' => [
        'provider' => 'client_users',
        'table' => 'api.client_password_resets',
        'expire' => 60,
        'throttle' => 60,
    ],
],
```

---

## Фаза 2: Клиентская панель Filament

### 2.1 ClientPanelProvider

**Создать:** `app/Providers/Filament/ClientPanelProvider.php`

Ключевые настройки:
- `->id('client')`, `->path('client')`, `->login()`, `->authGuard('client')`
- Bringo branding (те же цвета что в AdminPanelProvider)
- `->brandName('Bringo API Portal')`
- Plugins: `FilamentApexChartsPlugin`
- Middleware: те же что у admin (TrustProxyPrefix, EncryptCookies, etc.)
- Discovery: `app/Filament/Client/` (Resources, Pages, Widgets)

URL: `https://nginx/public-api/client`

### 2.2 Структура клиентской панели

```
app/Filament/Client/
    Pages/
        Dashboard.php                   -- дашборд с виджетами
        AcceptInvitePage.php            -- публичная страница принятия инвайта
    Resources/
        TokenResource.php               -- управление своими токенами
        TokenResource/Pages/
            ListTokens.php
        RequestLogResource.php          -- просмотр своих API-запросов
        RequestLogResource/Pages/
            ListRequestLogs.php
            ViewRequestLog.php          -- детали запроса/ответа
    Widgets/
        ClientStatsOverview.php         -- баланс, запросы за сегодня, error rate
        ClientUsageChart.php            -- график использования за 14 дней
```

### 2.3 Dashboard клиента

**Создать:** `app/Filament/Client/Pages/Dashboard.php`

Виджеты:
- **ClientStatsOverview**: credit_balance, requests_today, error_rate, active_tokens_count
- **ClientUsageChart**: ApexChart — daily requests за 14 дней из ClickHouse `api_daily_usage`

Данные скоупятся через `auth('client')->user()->client_id`.

### 2.4 TokenResource (клиент)

**Создать:** `app/Filament/Client/Resources/TokenResource.php`

- Table: name, prefix, type (badge), credit_limit, credits_used, is_active, last_used_at, created_at
- Create: форма name + type (production/sandbox) → показать plain-text один раз (как в admin TokensRelationManager)
- Action: Revoke (с подтверждением)
- Query scope: `->where('client_id', auth('client')->user()->client_id)`
- Использует существующий `TokenService::createToken()` и `::revokeToken()`

---

## Фаза 3: Invite Flow + Email

### 3.1 InviteService

**Создать:** `app/Modules/Auth/Services/InviteService.php`

Методы:
- `createInvite(ClientUser $user): string` — генерирует `invite_token = bin2hex(random_bytes(32))`, `invite_expires_at = now() + 7 days`, возвращает signed URL
- `validateInvite(string $token, string $email): ?ClientUser` — проверяет токен + email + не истёк
- `acceptInvite(ClientUser $user, string $password): void` — хеширует пароль, очищает invite_token, ставит last_login_at
- `resendInvite(ClientUser $user): string` — перегенерирует токен + отправляет email
- `generateInviteUrl(ClientUser $user): string` — `/client/invite/accept?token={token}&email={email}`

### 3.2 AcceptInvitePage

**Создать:** `app/Filament/Client/Pages/AcceptInvitePage.php`

- Публичная страница (без auth middleware) на route `/client/invite/accept`
- GET: валидирует token+email → показывает форму "Set your password"
- POST: password + password_confirmation → `InviteService::acceptInvite()` → auto-login → redirect `/client`
- Если токен невалиден/истёк — сообщение об ошибке

### 3.3 Email-шаблон и Notification

**Создать:** `app/Notifications/ClientInviteNotification.php`

Laravel Notification класс. Отправляет email.

**Создать:** `resources/views/emails/client-invite.blade.php`

Email-шаблон на основе backend `base-new.html.twig`:
- Тот же HTML-каркас (Roboto, Bringo logo, #2A62F6 кнопка, footer с copyright)
- Язык: **английский** (как все письма в backend)
- Текст: "You've been invited to Bringo API Portal" → "Set your password" button → fallback URL
- Только заменить текст и ссылку кнопки

### 3.4 Настройка почты

**Изменить:** `compose.d/api/.env` — добавить:
```env
# Mail (Mailcatcher for local dev)
MAIL_MAILER=smtp
MAIL_HOST=mailcatcher
MAIL_PORT=1025
MAIL_USERNAME=null
MAIL_PASSWORD=null
MAIL_ENCRYPTION=null
MAIL_FROM_ADDRESS=noreply@bringo.co.uk
MAIL_FROM_NAME="Bringo API"
```

**Изменить:** `api/.env.example` (если есть) — добавить те же переменные.

### 3.5 ClientUsersRelationManager (в admin)

**Создать:** `app/Filament/Resources/ClientResource/RelationManagers/ClientUsersRelationManager.php`

- Таблица: first_name, last_name, email, is_active, last_login_at, invite status (pending/accepted badge)
- Create Action: форма (first_name, last_name, email) → создаёт ClientUser → отправляет invite email → показывает notification с invite URL (для копирования на всякий случай)
- Action: Resend Invite (перегенерирует токен + отправляет email повторно)
- Action: Deactivate/Activate

**Изменить:** `app/Filament/Resources/ClientResource.php` — добавить в `getRelations()`:
```php
return [
    TokensRelationManager::class,
    ClientUsersRelationManager::class,
];
```

---

## Фаза 4: Импорт пользователей из public.user

### 4.1 Модель LegacyUser

**Создать:** `app/Modules/Auth/Models/LegacyUser.php`

```php
class LegacyUser extends Model
{
    use ReadOnlyModel;
    protected $connection = 'pgsql';
    protected $table = 'public.user';
    protected $primaryKey = 'user_id';
}
```

Поля: user_id, email, first_name, last_name, roles, is_email_verified, last_login, date_added.

### 4.2 Import Action на странице клиентов

**Изменить:** `app/Filament/Resources/ClientResource/Pages/ListClients.php`

Добавить Header Action "Import User":
1. Открывает модалку с TextInput для поиска
2. При вводе (с debounce ~300ms) — запрос на поиск в `public.user`
3. Поиск: `WHERE first_name ILIKE '%query%' OR last_name ILIKE '%query%' OR email ILIKE '%query%'` LIMIT 5
4. Показываем как autocomplete: email, first_name, last_name
5. При выборе: создаём ApiClient (name = "{first_name} {last_name}", email, company_name пустая) + ClientUser (first_name, last_name, email, imported_from_user_id = user_id)
6. Отправляем invite email
7. Показываем notification с invite URL

---

## Фаза 5: Request Logs (ClickHouse)

### 5.1 RequestLogQueryService (shared)

**Создать:** `app/Infrastructure/ClickHouse/RequestLogQueryService.php`

```php
class RequestLogQueryService
{
    public function __construct(private ClickHouseClient $client) {}

    public function query(
        ?int $clientId = null,     // NULL = все клиенты (admin)
        ?string $endpoint = null,
        ?int $statusCode = null,
        ?string $method = null,
        ?string $from = null,
        ?string $to = null,
        ?string $search = null,    // поиск по path
        int $page = 1,
        int $perPage = 50,
    ): array { /* ClickHouse SELECT из api_request_logs с LIMIT/OFFSET */ }

    public function getRow(string $requestId): ?array { /* Детали одного запроса */ }

    public function countByFilters(...): int { /* COUNT для пагинации */ }

    public function getDistinctEndpoints(?int $clientId = null): array { /* Для dropdown фильтра */ }
}
```

### 5.2 RequestLogResource (клиент)

**Создать:** `app/Filament/Client/Resources/RequestLogResource.php` + Pages/

- Таблица (data from ClickHouse, кастомный data source):
  - Колонки: timestamp, method, path, status_code (badge: green 2xx, yellow 4xx, red 5xx), endpoint, credits_consumed, response_time_ms
  - Фильтры: endpoint (select), status_code (range), date range, method
  - Поиск: по path
- View action: показать полные request_body + response_body, headers, request_id
- Scope: `clientId = auth('client')->user()->client_id` — всегда

### 5.3 RequestLogResource (admin)

**Создать:** `app/Filament/Resources/RequestLogResource.php` + Pages/

То же самое + дополнительный **фильтр по клиенту** (Select с поиском из api.clients).

### 5.4 Логи на странице клиента (admin)

**Изменить:** `app/Filament/Resources/ClientResource/Pages/EditClient.php` (или ViewClient)

Добавить виджет/таблицу с последними запросами клиента (мини-версия RequestLogResource, prefiltred по client_id). Либо добавить RelationManager-like компонент для логов.

Реализация: виджет `ClientRequestLogWidget` на странице EditClient, показывающий последние 20 запросов + ссылку "View all" на RequestLogResource с prefilt по client_id.

**Создать:** `app/Filament/Resources/ClientResource/Widgets/ClientRequestLogWidget.php`

---

## Фаза 6: Финансовые таблицы (новый эндпоинт)

### 6.1 Модели

**Создать:** `app/Modules/Company/Models/FinancialData.php`
```php
class FinancialData extends Model {
    use ReadOnlyModel;
    protected $connection = 'pgsql';
    protected $table = 'public.financial_data';
    protected $primaryKey = 'financial_data_id';
    // financial_data_id, financial_code, company_number, value, year, weight
}
```

**Создать:** `app/Modules/Company/Models/Financial.php`
```php
class Financial extends Model {
    use ReadOnlyModel;
    protected $connection = 'pgsql';
    protected $table = 'public.financial';
    protected $primaryKey = 'code';
    public $incrementing = false;
    protected $keyType = 'string';
    // code, name, type, value_type, description
}
```

### 6.2 FinancialDataService

**Создать:** `app/Modules/Company/Services/FinancialDataService.php`

Порт логики из backend `HierarchicalFinancialTableService` (`backend/src/Service/CompanyFinance/`):
1. Загружает YAML-структуру таблиц (скопировать из backend)
2. Загружает справочник `public.financial` (кеш 24h)
3. Для конкретной компании: `SELECT DISTINCT ON (financial_code, year)` из `public.financial_data` JOIN `public.financial` WHERE company_number = ? ORDER BY financial_code, year, weight DESC
4. Строит иерархию: tabs → rows → children → values по годам (логика из `HierarchicalFinancialTableService::buildRowNode()`)
5. Возвращает структурированный массив

**Скопировать из backend:** YAML-файл со структурой финансовых таблиц (источник: backend parameter `app.financial.financial_structure`). Найти путь к файлу из backend `config/parameters.yaml` / `services.yaml`.

**Создать:** `config/financial_structure.yaml` (или `storage/app/financial_structure.yaml`)

### 6.3 Resource (FinancialDataResource)

**Создать:** `app/Modules/Company/Resources/FinancialDataResource.php`

Все поля документированы PHPDoc для Scramble (OpenAPI), по аналогии с `CompanyResource`, `OfficerResource`:

```php
class FinancialDataResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            /** The company's 8-character registered number. */
            'company_number' => ...,
            /** Available years for financial data, ordered descending. @var int[] */
            'years' => [...],
            /** Key financial indicators (net_assets, total_assets, total_liabilities). */
            'indicators' => [
                'net_assets' => [
                    /** Most recent value as string. */
                    'value' => ...,
                    /** Year of the most recent value. */
                    'year' => ...,
                ],
                ...
            ],
            /** Financial data grouped into tabs (e.g. Profit & Loss, Balance Sheet). @var FinancialTabResource[] */
            'tabs' => FinancialTabResource::collection(...),
        ];
    }
}
```

**Создать:** `app/Modules/Company/Resources/FinancialTabResource.php`

```php
class FinancialTabResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            /** Internal tab identifier code. */
            'code' => ...,
            /** Display name of the financial tab (e.g. "Profit & Loss", "Balance Sheet"). */
            'name' => ...,
            /** Rows within this tab. @var FinancialRowResource[] */
            'rows' => FinancialRowResource::collection(...),
        ];
    }
}
```

**Создать:** `app/Modules/Company/Resources/FinancialRowResource.php`

```php
class FinancialRowResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            /** Financial indicator code (e.g. "turnover", "net_assets"). See GET /v1/directories for reference. */
            'code' => ...,
            /** Display name of the financial indicator. */
            'name' => ...,
            /** Detailed description of the financial indicator. */
            'description' => ...,
            /** Whether this row is a section title (non-data grouping header). */
            'is_title' => ...,
            /** Data type of the value: bool, int, float, string, percent, date, date_period, link. */
            'value_type' => ...,
            /** Values keyed by year. Keys are year integers as strings, values are string representations. @var array<string, string> */
            'values' => ...,
            /** Child rows nested under this row. @var FinancialRowResource[] */
            'children' => FinancialRowResource::collection(...),
        ];
    }
}
```

### 6.4 Контроллер

**Создать:** `app/Modules/Company/Controllers/CompanyFinancialDataController.php`

```php
/**
 * Get financial data tables.
 *
 * Returns hierarchical financial data for a company, organized into tabs
 * (e.g. Profit & Loss, Balance Sheet, Cash Flow, Ratios). Each tab contains
 * rows with financial indicator values by year. Data is sourced from parsed
 * annual accounts filed at Companies House.
 *
 * The response includes:
 * - **indicators** — key summary metrics (net assets, total assets, total liabilities) with the most recent value
 * - **tabs** — hierarchical financial tables grouped by category
 * - **rows** — individual financial indicators with values across multiple years
 * - **children** — nested sub-indicators within a parent row
 *
 * Value types include: `bool`, `int`, `float`, `string`, `percent`, `date`, `date_period`, `link`.
 * All numeric values are returned as strings to preserve precision.
 *
 * **Credits:** 3 per request.
 *
 * @operationId listCompanyFinancialData
 * @tags Companies
 * @queryParam year integer Filter results to include only the specified year. Returns all available years if omitted.
 */
public function index(Request $request, string $company_number): JsonResponse
```

Пример ответа:
```json
{
    "data": {
        "company_number": "00000086",
        "years": [2023, 2022, 2021],
        "indicators": {
            "net_assets": { "value": "500000.50", "year": 2023 },
            "total_assets": { "value": "1200000", "year": 2023 },
            "total_liabilities": { "value": "700000", "year": 2023 }
        },
        "tabs": [
            {
                "code": "profit_and_loss",
                "name": "Profit & Loss",
                "rows": [
                    {
                        "code": "turnover",
                        "name": "Turnover",
                        "description": "Total revenue from goods and services",
                        "is_title": false,
                        "value_type": "float",
                        "values": { "2023": "1000000.0", "2022": "950000.0" },
                        "children": []
                    }
                ]
            }
        ]
    },
    "meta": { "request_id": "..." }
}
```

### 6.4 Роут и прайсинг

**Изменить:** `routes/api.php` — добавить в billable группу:
```php
Route::get('companies/{company_number}/financial-data', [CompanyFinancialDataController::class, 'index'])
    ->name('company.financial_data');
```

**Изменить:** `database/seeders/EndpointPriceSeeder.php` — добавить:
```php
['endpoint_slug' => 'company.financial_data', 'price_credits' => 3],
```

---

## Сводка файлов

### Новые файлы (38)

| # | Файл | Назначение |
|---|------|-----------|
| 1 | `database/migrations/..._create_client_users_table.php` | Таблица api.client_users |
| 2 | `database/migrations/..._create_client_password_resets_table.php` | Password reset для клиентов |
| 3 | `app/Modules/Auth/Models/ClientUser.php` | Модель клиентского пользователя |
| 4 | `app/Modules/Auth/Models/LegacyUser.php` | ReadOnly модель public.user |
| 5 | `app/Modules/Auth/Services/InviteService.php` | Генерация/валидация invite |
| 6 | `app/Notifications/ClientInviteNotification.php` | Email invite notification |
| 7 | `resources/views/emails/client-invite.blade.php` | Email шаблон (eng, base-new.html.twig стиль) |
| 8 | `app/Providers/Filament/ClientPanelProvider.php` | Filament panel /client |
| 9 | `app/Filament/Client/Pages/Dashboard.php` | Дашборд клиента |
| 10 | `app/Filament/Client/Pages/AcceptInvitePage.php` | Принятие инвайта (публичная) |
| 11 | `app/Filament/Client/Resources/TokenResource.php` | Управление токенами |
| 12 | `app/Filament/Client/Resources/TokenResource/Pages/ListTokens.php` | Список токенов |
| 13 | `app/Filament/Client/Resources/RequestLogResource.php` | Логи запросов клиента |
| 14 | `app/Filament/Client/Resources/RequestLogResource/Pages/ListRequestLogs.php` | Список логов |
| 15 | `app/Filament/Client/Resources/RequestLogResource/Pages/ViewRequestLog.php` | Детали запроса |
| 16 | `app/Filament/Client/Widgets/ClientStatsOverview.php` | Виджет статистики |
| 17 | `app/Filament/Client/Widgets/ClientUsageChart.php` | Виджет графика |
| 18 | `app/Filament/Resources/ClientResource/RelationManagers/ClientUsersRelationManager.php` | Управление юзерами клиента (admin) |
| 19 | `app/Filament/Resources/ClientResource/Widgets/ClientRequestLogWidget.php` | Логи запросов на странице клиента (admin) |
| 20 | `app/Filament/Resources/RequestLogResource.php` | Логи запросов (admin, все клиенты) |
| 21 | `app/Filament/Resources/RequestLogResource/Pages/ListRequestLogs.php` | Список логов (admin) |
| 22 | `app/Filament/Resources/RequestLogResource/Pages/ViewRequestLog.php` | Детали запроса (admin) |
| 23 | `app/Infrastructure/ClickHouse/RequestLogQueryService.php` | Shared-сервис запросов к ClickHouse |
| 24 | `app/Modules/Company/Models/FinancialData.php` | Модель public.financial_data |
| 25 | `app/Modules/Company/Models/Financial.php` | Модель public.financial |
| 26 | `app/Modules/Company/Services/FinancialDataService.php` | Иерархические финансовые таблицы |
| 27 | `app/Modules/Company/Controllers/CompanyFinancialDataController.php` | Контроллер financial-data |
| 28 | `app/Modules/Company/Resources/FinancialDataResource.php` | Resource: корневой (company_number, years, indicators, tabs) |
| 29 | `app/Modules/Company/Resources/FinancialTabResource.php` | Resource: tab (code, name, rows) |
| 30 | `app/Modules/Company/Resources/FinancialRowResource.php` | Resource: row (code, name, value_type, values, children) |
| 31 | `config/financial_structure.yaml` | YAML-структура таблиц (из backend) |
| 32 | `tests/Unit/Services/InviteServiceTest.php` | Unit-тесты InviteService |
| 33 | `tests/Unit/Services/FinancialDataServiceTest.php` | Unit-тесты FinancialDataService |
| 34 | `tests/Feature/Api/FinancialDataTest.php` | Feature-тесты API financial-data |
| 35 | `tests/Feature/Client/InviteFlowTest.php` | Feature-тесты invite flow |
| 36 | `tests/Feature/Client/ClientPortalTest.php` | Feature-тесты клиентского портала |
| 37 | `tests/Feature/Admin/ClientUserManagementTest.php` | Feature-тесты управления юзерами |
| 38 | `tests/Feature/Admin/ImportUserTest.php` | Feature-тесты импорта |

### Изменяемые файлы (7)

| # | Файл | Изменение |
|---|------|-----------|
| 1 | `config/auth.php` | + guard `client`, provider `client_users`, password broker |
| 2 | `app/Filament/Resources/ClientResource.php` | + `ClientUsersRelationManager` в `getRelations()` |
| 3 | `app/Filament/Resources/ClientResource/Pages/ListClients.php` | + Import Action в header |
| 4 | `app/Filament/Resources/ClientResource/Pages/EditClient.php` | + ClientRequestLogWidget |
| 5 | `routes/api.php` | + route `company.financial_data` |
| 6 | `database/seeders/EndpointPriceSeeder.php` | + pricing для `company.financial_data` |
| 7 | `compose.d/api/.env` | + MAIL_* переменные для почты |

---

## Фаза 7: Тесты

Полный комплект тестов, следуя паттерну существующих (`tests/Feature/Api/`, `tests/Unit/Services/`). Используется `DatabaseTransactions` на connection `api`.

### 7.1 Unit-тесты

**Создать:** `tests/Unit/Services/InviteServiceTest.php`
- `test_create_invite_generates_token_and_sets_expiry`
- `test_create_invite_sets_7_day_expiry`
- `test_validate_invite_returns_user_for_valid_token`
- `test_validate_invite_returns_null_for_expired_token`
- `test_validate_invite_returns_null_for_wrong_email`
- `test_validate_invite_returns_null_for_nonexistent_token`
- `test_accept_invite_hashes_password_and_clears_token`
- `test_resend_invite_generates_new_token`
- `test_generate_invite_url_contains_token_and_email`

**Создать:** `tests/Unit/Services/FinancialDataServiceTest.php`
- `test_get_table_returns_hierarchical_structure`
- `test_get_table_groups_by_tabs`
- `test_get_table_orders_by_year_desc`
- `test_get_table_handles_empty_data`
- `test_get_table_deduplicates_by_weight`
- `test_get_indicators_returns_latest_values`

### 7.2 Feature-тесты API

**Создать:** `tests/Feature/Api/FinancialDataTest.php`
По аналогии с `DataEndpointsTest.php`:
- `test_financial_data_returns_tabs_and_rows` — проверить структуру ответа
- `test_financial_data_charges_3_credits` — проверить списание
- `test_financial_data_404_for_unknown_company`
- `test_financial_data_requires_auth`
- `test_financial_data_sandbox_only_allowed_companies`
- `test_financial_data_year_filter_works`
- `test_financial_data_returns_indicators`
- `test_financial_data_response_structure` — assertJsonStructure

### 7.3 Feature-тесты Invite Flow

**Создать:** `tests/Feature/Client/InviteFlowTest.php`
- `test_accept_invite_page_loads_with_valid_token`
- `test_accept_invite_page_rejects_expired_token`
- `test_accept_invite_page_rejects_invalid_token`
- `test_accept_invite_sets_password_and_logs_in`
- `test_accept_invite_requires_password_confirmation`
- `test_accept_invite_rejects_weak_password`
- `test_used_invite_cannot_be_reused`

### 7.4 Feature-тесты Client Portal

**Создать:** `tests/Feature/Client/ClientPortalTest.php`
- `test_client_user_can_login`
- `test_client_user_cannot_access_admin_panel`
- `test_admin_user_cannot_access_client_panel`
- `test_inactive_client_user_cannot_login`
- `test_client_dashboard_loads`
- `test_client_sees_only_own_tokens`
- `test_client_can_create_token`
- `test_client_can_revoke_token`

### 7.5 Feature-тесты Admin (Client Users)

**Создать:** `tests/Feature/Admin/ClientUserManagementTest.php`
- `test_admin_can_create_client_user`
- `test_admin_can_list_client_users`
- `test_admin_can_deactivate_client_user`
- `test_admin_can_resend_invite`
- `test_invite_email_is_sent_on_create` — assertSent notification
- `test_multiple_users_per_client_allowed`

### 7.6 Feature-тесты Import

**Создать:** `tests/Feature/Admin/ImportUserTest.php`
- `test_search_legacy_users_by_email`
- `test_search_legacy_users_by_name`
- `test_search_returns_max_5_results`
- `test_import_creates_api_client_and_client_user`
- `test_import_sets_imported_from_user_id`
- `test_import_sends_invite_email`

### 7.7 Unit-тесты RequestLogQueryService

**Создать:** `tests/Unit/Services/RequestLogQueryServiceTest.php`
- `test_query_builds_correct_clickhouse_sql`
- `test_query_with_client_filter`
- `test_query_with_date_range`
- `test_query_with_endpoint_filter`
- `test_query_handles_clickhouse_down_gracefully`

### Сводка тестовых файлов (7)

| # | Файл | Кол-во тестов |
|---|------|--------------|
| 1 | `tests/Unit/Services/InviteServiceTest.php` | ~9 |
| 2 | `tests/Unit/Services/FinancialDataServiceTest.php` | ~6 |
| 3 | `tests/Feature/Api/FinancialDataTest.php` | ~8 |
| 4 | `tests/Feature/Client/InviteFlowTest.php` | ~7 |
| 5 | `tests/Feature/Client/ClientPortalTest.php` | ~8 |
| 6 | `tests/Feature/Admin/ClientUserManagementTest.php` | ~6 |
| 7 | `tests/Feature/Admin/ImportUserTest.php` | ~6 |
| 8 | `tests/Unit/Services/RequestLogQueryServiceTest.php` | ~5 |

**Итого: ~55 тестов**

---

## Порядок реализации

1. **Фаза 1** (Foundation): ClientUser модель + миграции + auth config
2. **Фаза 2** (Client Panel): ClientPanelProvider + Dashboard + TokenResource
3. **Фаза 3** (Invite): InviteService + AcceptInvitePage + Email + UsersRelationManager
4. **Фаза 4** (Import): LegacyUser + Import Action на ListClients
5. **Фаза 5** (Logs): RequestLogQueryService + RequestLogResource (обе панели) + виджет логов на странице клиента в admin
6. **Фаза 6** (Financial): Модели + Service + Controller + Route (независима, можно параллельно с 1-5)
7. **Фаза 7** (Тесты): Unit + Feature тесты для каждой фазы (~55 тестов, 8 файлов)

**Тесты пишутся после каждой фазы** (TDD или сразу после реализации), не откладываются до конца.

---

## Верификация

### Фаза 1-3 (Auth + Portal + Invite)
```bash
./compose.sh exec -T api php artisan migrate --force

# Создать тестового клиента с юзером через admin панель
# Открыть /admin → Clients → Edit → Client Users tab → Create
# Проверить что invite email пришёл в Mailcatcher (http://mailcatcher)
# Перейти по invite URL → задать пароль
# Войти в /client → проверить dashboard и токены
```

### Фаза 4 (Import)
```bash
# Открыть /admin → Clients → Import User
# Ввести email/имя существующего пользователя из public.user
# Проверить autocomplete (5 результатов)
# Выбрать → проверить создание ApiClient + ClientUser + invite email
```

### Фаза 5 (Logs)
```bash
# Сделать несколько API-запросов с токеном клиента
# Проверить /client → Request Logs → видны свои запросы
# Проверить фильтры: endpoint, status, date range
# Проверить /admin → Request Logs → видны все + фильтр по клиенту
# Проверить /admin → Clients → Edit client → виджет логов запросов
```

### Фаза 6 (Financial Data)
```bash
curl -H "Authorization: Bearer bcu_live_..." \
  https://nginx/public-api/v1/companies/00000086/financial-data

# Проверить: иерархическая структура tabs → rows → children → values
# Проверить: 3 credits charged
./compose.sh exec -T api php artisan test --filter=FinancialData
```

### Code quality
```bash
./compose.sh exec -T api vendor/bin/pint --test
./compose.sh exec -T api vendor/bin/phpstan analyze --memory-limit=512M
./compose.sh exec -T api php artisan test --testdox
```
