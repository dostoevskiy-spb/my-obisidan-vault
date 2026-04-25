---
type: session-plan-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-15_qa-3-pr20-pr25.md
session_date: 2026-04-15
tags:
  - session-plan
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# План фиксов v3 — QA-отчёт #3 (тестировщик, 15.04.2026)

## Context

Тестировщик прислал 5 багов после прогона stage; коллега подготовил параллельный анализ (`frolicking-prancing-wadler.md` v2). После кросс-валидации планов root causes подтверждены в обе стороны. Пользователь явно **отклонил** warmup (progressive rate limit) как гипотезу симптома "лимиты не повышаются" — реальная причина оказалась в **cascade-баге** RateLimitService (это совпадает между планами).

Баги:
1. 🔴 `sic_codes: []` у `09301329` при реальном `{64999}` в БД.
2. 🟡 `GET /exports/fields?type=PSCs` → 422 (регистрозависимо).
3. 🔴 `GET /companies/{cn}/related-companies` всегда `[]` — SQL-алгоритм в корне неверный.
4. ⚠️ «Лимиты не повышаются как должны с течением времени» → scope от пользователя: **только регрессионные тесты fixed-window**, без warmup.

Все правки — в субмодуле `client-api/`. Порядок: фикс → тест → `pint`/`phpstan`/`artisan test` по каждому PR. Коммитов не делаю.

---

## PR20 — `sic_codes` / `previous_company_names`: правильные PG-casts

**Root cause (подтверждено SQL):**
- `public.company.sic_codes :: _varchar` — для 09301329: `{64999}` (Postgres text-array).
- `public.company.previous_company_names :: _varchar` — массив JSON-строк: `{"{\"ceasedOn\":...}","{\"ceasedOn\":...}"}`.
- [Company.php:41](client-api/app/Modules/Company/Models/Company.php#L41) использует Laravel `'array'` cast (JSON). `json_decode('{64999}')` возвращает `null` → Resource отдаёт `[]`.

В проекте уже существуют оба нужных cast'а:
- [PostgresArray.php](client-api/app/Shared/Casts/PostgresArray.php) — для плоских `text[]/varchar[]` (trim + explode).
- [PostgresJsonArray.php](client-api/app/Shared/Casts/PostgresJsonArray.php) — для `jsonb[]`/`text[]` с JSON-строками внутри (создан в PR16).

**Фикс:**
```php
// app/Modules/Company/Models/Company.php
use App\Shared\Casts\PostgresArray;
use App\Shared\Casts\PostgresJsonArray;

protected function casts(): array {
    return [
        // ...
        'sic_codes' => PostgresArray::class,
        'previous_company_names' => PostgresJsonArray::class,
    ];
}
```

**Аудит:** пройти по всем read-only `public.*` моделям и проверить оставшиеся Laravel-cast'ы `'array'` / `'json'` на реальный тип колонки. SQL-чек:
```sql
SELECT table_name, column_name, udt_name
FROM information_schema.columns
WHERE table_schema='public' AND udt_name ~ '^_'  -- PG array types
ORDER BY table_name;
```
Правило:
- `_varchar|_text|_bpchar` → `PostgresArray`
- `_json|_jsonb` → `PostgresJsonArray`
- одиночные `json|jsonb` → `'json'`

Основное уже сделано в PR16 (CompanyCharge, CompanyFilingHistory, CompanyExemption, CompanyUkEstablishment, CompanyInsolvency). В этом PR добавить то, что всплывёт при аудите Company + CompanyOfficerAppointment (`former_names`, `nationality_codes`, `country_of_residence_codes`), CompanyRating (`red_flags`, `*_flags_list`).

**Тесты:**
- `tests/Unit/Models/CompanySicCodesTest.php` (новый) — `Company::forceFill(['sic_codes' => '{64999,62010}'])` → ожидаем `['64999','62010']`. Аналогично для `previous_company_names` с реальным JSON-payload из БД.
- `tests/Feature/Api/CompanyProfileTest::test_sic_codes_populated_from_pg_array` (новый) — реальная компания из `public.company` с непустыми sic_codes → ответ API содержит `data.sic_codes` как массив, не пустой.
- Усилить [tests/Feature/E2E/FullLifecycleTest.php](client-api/tests/Feature/E2E/FullLifecycleTest.php) — `assertIsArray` → `assertNotEmpty` для seed-компаний с непустыми sic.

**Critical files:** [client-api/app/Modules/Company/Models/Company.php](client-api/app/Modules/Company/Models/Company.php) + возможно другие по результатам аудита.

---

## PR21 — `ExportType` backed enum (case-insensitive + type-safe)

**Root cause:** Тип экспорта сравнивается регистрозависимо в 5 местах:
- [CreateExportRequest.php:21](client-api/app/Modules/Export/Requests/CreateExportRequest.php#L21) — `in:companies,officers,pscs`
- [CreateExportRequest.php:113-118](client-api/app/Modules/Export/Requests/CreateExportRequest.php#L113) — `isValidFieldForType` match
- [ExportController.php:309-316](client-api/app/Modules/Export/Controllers/ExportController.php#L309) — `match($type)` в `fields()`
- [ExportService.php:189+](client-api/app/Modules/Export/Services/ExportService.php) — `buildQueryBody`, `resolveIndex`
- [ProcessExportJob.php:68](client-api/app/Modules/Export/Jobs/ProcessExportJob.php#L68)

**Решение — backed enum (не минимальный strtolower):** единая точка нормализации, type-safety в Service/Job, автоматический enum в OpenAPI через Scramble, PHPStan проверит `match`-exhaustiveness. Добавление нового типа в будущем — 1 case, а не 5 мест.

```php
// app/Modules/Export/Enums/ExportType.php (новый)
namespace App\Modules\Export\Enums;

enum ExportType: string
{
    case Companies = 'companies';
    case Officers  = 'officers';
    case Pscs      = 'pscs';

    /**
     * Case-insensitive factory.
     *
     * @throws \ValueError
     */
    public static function fromAny(string $value): self
    {
        return self::from(strtolower(trim($value)));
    }

    public static function tryFromAny(?string $value): ?self
    {
        if ($value === null) {
            return null;
        }
        return self::tryFrom(strtolower(trim($value)));
    }
}
```

**Применение:**
1. `CreateExportRequest::prepareForValidation()` — опустить `type` в lowercase ДО валидации:
   ```php
   protected function prepareForValidation(): void
   {
       if ($this->has('type')) {
           $this->merge(['type' => strtolower((string) $this->input('type'))]);
       }
   }
   ```
2. `CreateExportRequest::rules` — заменить `'in:companies,officers,pscs'` на `Rule::enum(ExportType::class)` (Laravel 11+).
3. `ExportController::fields()` — `ExportType::tryFromAny($request->query('type', 'companies'))` → при null кинуть 422.
4. `ExportService::buildQueryBody()`, `resolveIndex()`, `ProcessExportJob::handle()` — принимать `ExportType` (не строку) в сигнатуре, `match` по case'ам.

**Тесты `tests/Feature/Export/ExportControllerTest.php`:**
- `test_exports_fields_type_case_insensitive` — `?type=PSCs`, `?type=Companies`, `?type=OFFICERS` → 200, `data` идентично lowercase-версии.
- `test_exports_fields_invalid_type_returns_422` — `?type=bogus` → 422 (регрессия).
- `test_exports_create_type_case_insensitive` — `POST /v1/exports {"type":"PSCs"}` → 201, в БД `export_jobs.type='pscs'` (нормализовано).
- `test_exports_fields_lowercase_still_works` — регрессия `?type=pscs`.

Unit тесты `tests/Unit/Export/ExportTypeTest.php` (новый) — `fromAny('PSCs')`, `tryFromAny('bogus')=null`, все case'ы.

**Critical files:**
- `client-api/app/Modules/Export/Enums/ExportType.php` (новый)
- [CreateExportRequest.php](client-api/app/Modules/Export/Requests/CreateExportRequest.php)
- [ExportController.php](client-api/app/Modules/Export/Controllers/ExportController.php)
- [ExportService.php](client-api/app/Modules/Export/Services/ExportService.php)
- [ProcessExportJob.php](client-api/app/Modules/Export/Jobs/ProcessExportJob.php)

---

## PR22 — related-companies: `RelatedCompaniesService` + 3 источника связей

**Root cause (подтверждено SQL + кросс-валидация):**

[CompanyRelatedController.php:44-56](client-api/app/Modules/Company/Controllers/CompanyRelatedController.php#L44) делает self-join `matching_v2.matched_company_to_ch_company` по `matched_company_id`. Эта таблица группирует **дубликаты** одной компании (same_group), а не связи между разными компаниями. Для 09301329 (company_id=6055947) и 13637908 (company_id=1721184, BOHD) каждая компания одна в своей группе → результат **всегда пуст**.

**Правильные источники связей** (референс — [backend/src/Dao/MatchedCompanyDao.php](backend/src/Dao/MatchedCompanyDao.php)):

| Таблица | Ключи | Для чего |
|---|---|---|
| `matched_company_to_ch_company` | `matched_company_id, ch_company_id, block_name` | same_group (дубли) — сохраняем |
| `matched_person_to_officer` | `matched_person_id, officer_id, officer_for_company_ids int4[]` | Для officer_id сразу даёт все company_id, где этот человек директор |
| `matched_person_to_psc` | `matched_person_id, psc_id, psc_for_company_ids int4[]` | То же для PSC |

Проверено эмпирически: BOHD (1721184) через `matched_person_to_officer.officer_for_company_ids` → `[10576303]` (CEDAR COURT RESIDENTS 01132393). Совпадает с UI Bringo.

**Решение:**

Вынести логику в сервис `app/Modules/Company/Services/RelatedCompaniesService.php` (чище тестировать, тоньше контроллер).

```php
// RelatedCompaniesService::findFor(Company $company, int $perPage, int $offset)
$cid = $company->company_id;

$sql = <<<'SQL'
SELECT c.company_number, c.company_name,
       string_agg(DISTINCT r.relation_type, ',') AS relation_types,
       count(*) OVER () AS total_rows
FROM (
    -- 1. same_group (matched_company дубли)
    SELECT mcc2.ch_company_id AS company_id, 'same_group' AS relation_type
    FROM matching_v2.matched_company_to_ch_company mcc1
    JOIN matching_v2.matched_company_to_ch_company mcc2
         ON mcc1.matched_company_id = mcc2.matched_company_id
    WHERE mcc1.ch_company_id = :cid
      AND mcc2.ch_company_id != :cid

    UNION ALL

    -- 2. Общие officers (через person-dedupe)
    SELECT DISTINCT UNNEST(mpto.officer_for_company_ids) AS company_id,
           'shared_officer' AS relation_type
    FROM public.company_officer_appointment coa
    JOIN matching_v2.matched_person_to_officer mpto ON mpto.officer_id = coa.officer_id
    WHERE coa.company_id = :cid

    UNION ALL

    -- 3. Общие PSCs
    SELECT DISTINCT UNNEST(mptp.psc_for_company_ids) AS company_id,
           'shared_psc' AS relation_type
    FROM public.company_psc cp
    JOIN matching_v2.matched_person_to_psc mptp ON mptp.psc_id = cp.psc_id
    WHERE cp.company_id = :cid
) r
JOIN public.company c ON c.company_id = r.company_id
WHERE r.company_id != :cid
GROUP BY c.company_id, c.company_number, c.company_name
ORDER BY c.company_name
LIMIT :limit OFFSET :offset
SQL;
```

`count(*) OVER ()` возвращает total в каждой строке — избавляет от отдельного COUNT-запроса.

**Форма ответа:** `relation_type` (string) → `relation_types` (array of string). Компания может быть связана сразу несколькими способами (same_group + shared_officer). Обратно совместимое расширение (клиенты, проверявшие `in_array('shared_officer', ...)`, не ломаются; если кто-то сравнивает `relation_type === 'shared_officer'` — сломается, но таких клиентов мало).

**Проверить имена таблиц перед правкой SQL:** в проекте встречается `company_person_with_significant_control` (старое имя) vs `company_psc`. Посмотреть модель [CompanyPsc.php](client-api/app/Modules/Company/Models/CompanyPsc.php) → там `$table = 'public.company_psc'`. Использовать это имя.

**Тесты:**
- `tests/Unit/Services/RelatedCompaniesServiceTest.php` (новый) — unit с fixture (вставка в matching_v2 через `DB::statement`) проверяет каждый из 3 путей независимо.
- `tests/Feature/Api/RelatedCompaniesTest.php` (новый):
  - `test_related_via_shared_officer` — для BOHD 13637908 ожидаем CEDAR COURT 01132393, `relation_types` содержит `shared_officer`.
  - `test_related_via_same_group` — подобрать seed-пример.
  - `test_related_via_shared_psc` — при наличии данных в `matched_person_to_psc`.
  - `test_related_isolated_company_returns_empty` — компания без матчинга → `data: []`, `meta.total: 0`.
  - `test_related_404_for_unknown_company`.
  - `test_related_pagination` — `per_page/page`.
  - `test_related_response_structure_has_array_relation_types` — backcompat check.

**Critical files:**
- `client-api/app/Modules/Company/Services/RelatedCompaniesService.php` (новый)
- [client-api/app/Modules/Company/Controllers/CompanyRelatedController.php](client-api/app/Modules/Company/Controllers/CompanyRelatedController.php) — тонкий контроллер, DI сервиса.

---

## PR23 — Rate-limit cascade bug + регрессионные тесты fixed-window

**Root cause (это и есть реальная причина симптома "лимиты не повышаются"):**

[RateLimitService.php:27-34](client-api/app/Modules/RateLimit/Services/RateLimitService.php#L27):
```php
foreach ($limits as $window) {
    $key = $this->buildKey($client->id, $window['key_suffix']);
    $result = $this->checkWindow($key, $window['limit'], $window['ttl']);
    if ($result !== null) {
        return $result;   // ← БАГ: hour/day НЕ инкрементируются при reject per-minute
    }
}
```

`checkWindow` сам делает `INCR` для своего окна. При прохождении `min` инкрементируются `hour` и `day`. Но как только на `min` приходит 429, **hour/day перестают накапливать попытки**. Клиент, знающий тайминг, может превышать `per_hour` без блокировки: ждать границы минуты, делать 60 запросов, ловить 429, повторять — суммарно `per_hour` никогда не сработает.

**Это и объясняет жалобу QA "лимиты не повышаются со временем как должны"** — счётчики hour/day фактически не растут при минутных reject'ах.

**Фикс:**
```php
// RateLimitService::check()
$rejection = null;
foreach ($limits as $window) {
    $key = $this->buildKey($client->id, $window['key_suffix']);
    $result = $this->checkWindow($key, $window['limit'], $window['ttl']);
    if ($result !== null && $rejection === null) {
        $rejection = $result;   // сохраняем первое отклонение
    }
    // но НЕ return — продолжаем INCR остальных окон
}
return $rejection;
```

Без DECR на отклонённых окнах — всё равно клиент не «выпьёт» бо́льшие окна в пределах одного цикла; важнее иметь корректный счётчик для последующих запросов.

**Тесты `tests/Feature/Api/RateLimitWindowTest.php` (новый):**
- `test_rate_limit_window_resets_after_ttl` — выдать `per_minute=3`, сделать 3 req, `Redis::expire('api:rl:{id}:min', 1)` + `usleep(1_200_000)` → 4-й req проходит с `X-RateLimit-Remaining = 2`.
- `test_remaining_header_decrements_with_each_request` — 3 запроса → `X-RateLimit-Remaining` = N, N-1, N-2.
- `test_rate_limit_all_windows_incremented_even_on_reject` ← cascade bug regression — `per_minute=2, per_hour=10`, 3 запроса, 3-й → 429, `Redis::get('api:rl:{id}:hour')` должно быть `3`, а не `2`.
- `test_x_ratelimit_reset_matches_redis_ttl` — `X-RateLimit-Reset` = `time() + Redis::ttl(key)` (±1 сек).

**Critical files:** [client-api/app/Modules/RateLimit/Services/RateLimitService.php](client-api/app/Modules/RateLimit/Services/RateLimitService.php)

**Warmup НЕ делаем** — пользователь отклонил; cascade bug полностью объясняет симптом.

---

## PR24 — ConcurrencyLimiter: тесты release + TTL bump

**Мотивация:** QA-жалоба "лимиты не повышаются" не различает подсистемы — если concurrency-слоты не освобождаются, клиент видит тот же симптом. [ConcurrencyLimiter.php](client-api/app/Shared/Middleware/ConcurrencyLimiter.php) имеет `finally` → release при exception, но это **не покрыто тестами**. `KEY_TTL=30` сек — при запросе дольше 30с теоретически double-booking.

**Фикс:** `KEY_TTL` → 60 сек (с запасом для долгих запросов на границе `DB_STATEMENT_TIMEOUT=30s`).

**Тесты `tests/Feature/Middleware/ConcurrencyLimiterTest` (расширение):**
- `test_concurrency_slot_released_after_controller_runtime_exception` — mock контроллер → throw `\RuntimeException` → после запроса `api:concurrent:client:{id}` = 0.
- `test_concurrency_slot_released_after_api_exception` — то же через `ApiException`.
- `test_concurrency_key_has_ttl_after_acquire` — после acquire `Redis::ttl(...)` ∈ (0, `KEY_TTL`].
- `test_concurrency_double_release_does_not_go_negative` — прямой вызов release() на ключе = 0 → остаётся 0 (не −1).

**Critical files:** [ConcurrencyLimiter.php](client-api/app/Shared/Middleware/ConcurrencyLimiter.php) + тесты.

---

## PR25 — Billing: расширить покрытие (balance / refund / dedup / grace)

**Мотивация:** QA-жалоба "лимиты не повышаются" в обратной трактовке = **кредит-баланс не восстанавливается** (refund сломан) или **баланс не уменьшается при dedup hit** (тест отсутствует). Существующий [BillingTest.php](client-api/tests/Feature/Api/BillingTest.php) покрывает успех/404/sandbox/insufficient/token_limit/bulk, но не exception-refund, dedup-refund, grace и low-balance header.

**Пропущенные кейсы (дополнения в `BillingTest.php`):**
- `test_balance_decremented_after_successful_request` — явный before/after через `BillingService::getBalance()`. Прямая проверка симптома «лимит не повышается» — баланс **должен** уменьшаться.
- `test_x_credit_balance_header_equals_actual_balance` — после charge `X-Credit-Balance` = balance после списания.
- `test_refund_on_controller_exception_non_deferred` — mock `CompanyController::show` throw `\RuntimeException` → 500 → balance восстановлен (refund через terminable).
- `test_dedup_hit_refunds_charged_credits` — 2 идентичных запроса; первый списывает, второй `X-Dedup-Hit: true`, balance равен (refund в terminable при `is_dedup=true`).
- `test_charge_with_grace_allows_negative_balance` — `grace_period_enabled=true`, balance=0, grace=10, price=5 → success, balance=−5.
- `test_low_balance_header_triggered_below_threshold` — balance=50, price=1, threshold=100 → `X-Low-Balance: true`, `X-Credit-Balance` присутствует.

**Critical files:** [tests/Feature/Api/BillingTest.php](client-api/tests/Feature/Api/BillingTest.php) (расширение, без изменений кода).

---

## Порядок работы

**Волна 1 — data fixes:**
1. PR20 (sic_codes / previous_company_names cast + audit) → тест → pint/phpstan/test.
2. PR21 (ExportType enum) → тесты (unit + feature) → pint/phpstan/test.

**Волна 2 — логика и покрытие (всё обязательно, т.к. QA-жалоба «лимиты не повышаются» не различает rate-limit/concurrency/billing):**
3. PR22 (related-companies rewrite через `RelatedCompaniesService`) → seed/тесты → pint/phpstan/test.
4. PR23 (rate-limit cascade fix + 4 регрессионных теста) → тесты → pint/phpstan/test.
5. PR24 (concurrency: TTL bump + 4 теста release) → тесты → pint/phpstan/test.
6. PR25 (billing: 6 тестов на balance/refund/dedup/grace/low-balance) → pint/phpstan/test.

**Финал:** `pint` + `phpstan` + `php artisan test --testdox` по всему client-api.

---

## Критические файлы (summary)

| PR | Файл | Действие |
|---|---|---|
| PR20 | [Company.php](client-api/app/Modules/Company/Models/Company.php) | `sic_codes → PostgresArray`, `previous_company_names → PostgresJsonArray` |
| PR20 | остальные `public.*` модели | audit + fix по результатам |
| PR21 | `app/Modules/Export/Enums/ExportType.php` (новый) | backed enum с `fromAny/tryFromAny` |
| PR21 | [CreateExportRequest.php](client-api/app/Modules/Export/Requests/CreateExportRequest.php) | `prepareForValidation` + `Rule::enum` |
| PR21 | [ExportController.php](client-api/app/Modules/Export/Controllers/ExportController.php) | `ExportType::tryFromAny` в `fields()` |
| PR21 | [ExportService.php](client-api/app/Modules/Export/Services/ExportService.php) + [ProcessExportJob.php](client-api/app/Modules/Export/Jobs/ProcessExportJob.php) | принимать `ExportType` в сигнатуре |
| PR22 | `app/Modules/Company/Services/RelatedCompaniesService.php` (новый) | UNION ALL 3 источников + window COUNT |
| PR22 | [CompanyRelatedController.php](client-api/app/Modules/Company/Controllers/CompanyRelatedController.php) | тонкий контроллер, DI сервиса |
| PR23 | [RateLimitService.php](client-api/app/Modules/RateLimit/Services/RateLimitService.php) | убрать `return` в foreach → `$rejection` |
| PR24 | [ConcurrencyLimiter.php](client-api/app/Shared/Middleware/ConcurrencyLimiter.php) | KEY_TTL 30→60s + 4 теста release/ttl |
| PR25 | [tests/Feature/Api/BillingTest.php](client-api/tests/Feature/Api/BillingTest.php) | +6 тестов без изменений кода |

## Новые тесты

| PR | Тест | Файл |
|---|---|---|
| PR20 | Unit: cast sic_codes / previous_company_names | `tests/Unit/Models/CompanySicCodesTest.php` (новый) |
| PR20 | Feature: реальная компания → не-пустой sic_codes | `tests/Feature/Api/CompanyProfileTest.php` |
| PR21 | Unit: ExportType enum (fromAny/tryFromAny) | `tests/Unit/Export/ExportTypeTest.php` (новый) |
| PR21 | Feature: PSCs/OFFICERS/Companies + bogus 422 + POST | `tests/Feature/Export/ExportControllerTest.php` |
| PR22 | Unit: 3 SQL-пути независимо | `tests/Unit/Services/RelatedCompaniesServiceTest.php` (новый) |
| PR22 | Feature: BOHD→CEDAR, same_group, shared_psc, isolated, 404, pagination, relation_types array | `tests/Feature/Api/RelatedCompaniesTest.php` (новый) |
| PR23 | Feature: window reset, remaining decrement, cascade fix, reset timestamp | `tests/Feature/Api/RateLimitWindowTest.php` (новый) |
| PR24 | Feature: release on exception, TTL, double-release | `tests/Feature/Middleware/ConcurrencyLimiterTest.php` (+4 кейса) |
| PR25 | Feature: balance decrement, refund exception, dedup refund, grace, low-balance | `tests/Feature/Api/BillingTest.php` (+6 кейсов) |

---

## Верификация (E2E, после всех PR20-PR25)

```bash
./compose.sh exec -T api bash -lc 'vendor/bin/pint'
./compose.sh exec -T api bash -lc 'vendor/bin/phpstan analyze --memory-limit=512M'
./compose.sh exec -T api bash -lc 'php artisan test --testdox'
```

E2E на `https://nginx/public-api`:

1. **sic_codes:** `GET /v1/companies/09301329` → `data.sic_codes = ["64999"]` (не `[]`). `data.previous_company_names` — массив объектов с `ceasedOn/effectiveFrom/name`.
2. **Exports type:** `GET /v1/exports/fields?type=PSCs` → 200, идентично `?type=pscs`. `?type=Companies` / `?type=OFFICERS` → 200. `?type=bogus` → 422. `POST /v1/exports {"type":"PSCs"}` → 201.
3. **Related companies:**
   - `GET /v1/companies/13637908/related-companies` → `data` содержит `company_number=01132393` (CEDAR COURT) с `relation_types: ["shared_officer"]`.
   - `GET /v1/companies/09301329/related-companies` → список связанных через officers/PSC при наличии. Локально пусто — подтянуть: из backend `php bin/console app:company:pull-remote 13637908`.
4. **Rate limit:**
   - 3 запроса `/v1/account/me` подряд → `X-RateLimit-Remaining` = 59, 58, 57.
   - `Redis::expire('api:rl:{id}:min', 1)` + `sleep 2` → следующий запрос → Remaining 59.
   - Клиент с `per_minute=2, per_hour=10`, 3 запроса → 3-й 429; `Redis::get('api:rl:{id}:hour')` = `3` (cascade fix).
5. **Concurrency:** 20 параллельных запросов → `api:concurrent:client:{id}=0` после. Exception в контроллере → слот освобождён. `Redis::ttl('api:concurrent:...') ∈ (0, 60]`.
6. **Billing:** before=100 → `GET /companies/...(price=1)` → after=99, header `X-Credit-Balance=99`. Retry → `X-Dedup-Hit: true`, balance=99 (refund). Mock 500 → balance=99 (refund). Grace: balance=0 + grace=10 + price=5 → success, balance=−5.

---

## Cross-refs

- План коллеги: `/home/pavel/.claude/plans/frolicking-prancing-wadler.md` v2.
- Совпадающие находки: cascade bug, UNION ALL схема, необходимость сервиса для related.
- Расхождения: PR21 — взяли **enum** (архитектурно чище, type-safe через PHPStan, 1 точка нормализации, OpenAPI-enum в Scramble). Коллега предложил strtolower как минимальный фикс — но раз не коммитим сразу, делаем правильно. Warmup убрали (пользователь отклонил). PR24/PR25 сделаны обязательными — QA-жалоба не различает подсистемы «лимитов».
- Взаимное усиление: коллега дал SQL-пруфы (BOHD → CEDAR через `matched_person_to_officer.officer_for_company_ids=[10576303]`); я дал audit `public.*` моделей и cascade bug root cause в RateLimit.
