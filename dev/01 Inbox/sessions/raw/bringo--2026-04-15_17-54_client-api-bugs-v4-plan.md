---
type: session-plan-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-15_17-54_client-api-bugs-v4.md
session_date: 2026-04-15
tags:
  - session-plan
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Пачка багов от QA: client-api (v4 — с учётом нового раунда от тестера)

## Context

QA прислал второй раунд багов: детальный ETag/Cache-отчёт (5 пунктов), concurrency/rate-limit-наблюдения, webhook `event_type=test` не в enum, dedup чувствителен к порядку значений внутри `include=`-CSV, доменные наблюдения по `company.type` и `/insolvency`. Плюс — остаются 5 багов из первой пачки (sic_codes, exports type, related-companies, rate-limit cascade, опц. concurrency/billing tests) из v3.

Все правки — в `client-api/`. После каждого PR: `pint` + `phpstan` + `artisan test` на затронутое. Warmup (progressive rate-limit) остаётся отклонённым.

Второй план-источник: `/home/pavel/.claude/plans/fluffy-humming-kurzweil.md` (v3 от коллеги).

---

## Первая пачка — PR20-PR26 (перечисление для полноты, без изменений от v3)

- **PR20** — `sic_codes` / `previous_company_names` PG-casts + audit всех `public.*` моделей. [Company.php:41-42](client-api/app/Modules/Company/Models/Company.php#L41-L42).
- **PR21** — `ExportType` backed enum (case-insensitive) — [ExportController.php:309-316](client-api/app/Modules/Export/Controllers/ExportController.php#L309-L316), [CreateExportRequest.php:21](client-api/app/Modules/Export/Requests/CreateExportRequest.php#L21), [ExportService.php](client-api/app/Modules/Export/Services/ExportService.php), [ProcessExportJob.php](client-api/app/Modules/Export/Jobs/ProcessExportJob.php).
- **PR22** — `RelatedCompaniesService` + UNION ALL 5 источников (matched_company_to_ch_company / _to_officer / _to_psc + matched_person_to_officer / _to_psc). Смена формы ответа: `relation_type` → `relation_types` array. [CompanyRelatedController.php](client-api/app/Modules/Company/Controllers/CompanyRelatedController.php).
- **PR23** — Rate-limit cascade bug fix (не `return` в foreach, инкрементировать все окна). [RateLimitService.php:27-34](client-api/app/Modules/RateLimit/Services/RateLimitService.php#L27-L34) — объясняет симптом "лимиты не повышаются / не срабатывают со временем".
- **PR24** — warmup (progressive rate-limit): **НЕ ДЕЛАЕМ** (отклонено).
- **PR25** — Concurrency: `KEY_TTL 30→60` + тесты release/exception.
- **PR26** — Billing: расширенное покрытие refund/grace/dedup.

Детали — см. блок ниже и v3. Ниже прибавляются PR27-PR35 по второму раунду.

---

## Второй раунд — PR27-PR35 (свежие баги от QA)

### PR27 — CacheHeaders: ETag + If-None-Match (ядерный фикс 5 багов)

**Файл:** [client-api/app/Shared/Middleware/CacheHeaders.php](client-api/app/Shared/Middleware/CacheHeaders.php)

**Баг 27.1 (HIGH) — cross-endpoint ETag collision**

[CacheHeaders.php:28](client-api/app/Shared/Middleware/CacheHeaders.php#L28) берёт md5 от нормализованного body — `routeName` и `path` НЕ включены. Четыре разных URL с одинаковым пустым `data:[]` возвращают одинаковый ETag `"6f5a72a056c0423845a8f7e4246da3c3"` → при отправке этого ETag на другой endpoint получаем 304 + кэш заменяется чужим ответом (data substitution).

**Подтверждено эмпирически:**
- `/companies/14610796/charges`, `/companies/14610796/contacts`, `/companies/14610796/related-companies`, `/search/companies?q=xzz_nonexistent` — все отдают идентичный ETag.
- Запрос `/charges` с `If-None-Match: <ETag от /contacts>` → 304. Классическая cache-collision уязвимость (RFC 7232 §2.3).

**Баг 27.2-27.4 (MED/LOW) — If-None-Match неполно обрабатывает стандарт**
- Multi-value: `"bogus", "real-etag", "bogus2"` → 200 вместо 304 (RFC 7232 §3.2).
- Weak comparison: `W/"x"` не матчится с `"x"` (RFC 7232 §2.3.2).
- Wildcard: `If-None-Match: *` на существующий ресурс → 200 вместо 304 (RFC 7232 §3.2).

Все четыре проблемы в [CacheHeaders.php:31-32](client-api/app/Shared/Middleware/CacheHeaders.php#L31-L32): `if ($ifNoneMatch === $etag)` — строгое сравнение строки целиком.

**Баг 27.5 (LOW) — `/status` и `/sdks` не навешивают CacheHeaders middleware**

Подтверждено в [routes/api.php:35-43](client-api/routes/api.php#L35-L43):
```php
Route::get('v1/status', StatusController::class)
    ->middleware([AssignRequestId::class, ForceJsonResponse::class]);
Route::get('v1/sdks', SdkController::class)
    ->middleware([AssignRequestId::class, ForceJsonResponse::class]);
```
Нет `CacheHeaders::class`. При этом в `CACHEABLE_ROUTES = [..., 'status']` — намерение было сделать кэшируемым, но middleware не подключён.

**Фикс (единым patchем):**

```php
// app/Shared/Middleware/CacheHeaders.php

public function handle(Request $request, Closure $next): Response
{
    $response = $next($request);
    if ($request->method() !== 'GET' || $response->getStatusCode() >= 300) {
        return $response;
    }

    $routeId = $request->route()?->getName() ?? $request->path();
    $body    = $this->normalizeContentForEtag((string) $response->getContent());
    $etag    = '"'.md5($routeId.'|'.$body).'"';   // ← fix 27.1

    if ($this->ifNoneMatchMatches($request->header('If-None-Match'), $etag)) {  // ← fix 27.2-27.4
        return response('', 304)->withHeaders([
            'ETag' => $etag,
            'Cache-Control' => $response->headers->get('Cache-Control', 'private, max-age=0'),
        ]);
    }

    $response->headers->set('ETag', $etag);
    $response->headers->set('Cache-Control', in_array($request->route()?->getName(), self::CACHEABLE_ROUTES, true)
        ? 'public, max-age=3600'
        : 'private, no-cache');

    return $response;
}

private function ifNoneMatchMatches(?string $header, string $etag): bool
{
    if ($header === null || $header === '') return false;

    $header = trim($header);
    if ($header === '*') return true;

    $target = $this->stripWeakPrefix($etag);
    foreach (explode(',', $header) as $candidate) {
        if ($this->stripWeakPrefix(trim($candidate)) === $target) return true;
    }
    return false;
}

private function stripWeakPrefix(string $tag): string
{
    return str_starts_with($tag, 'W/') ? substr($tag, 2) : $tag;
}
```

Для **27.5** — добавить `CacheHeaders::class` к middleware на `v1/status` и `v1/sdks` (routes/api.php).

**Опционально (27.6):** решить судьбу `-gzip` суффикса от nginx (в `compose.d/nginx/conf.d/nginx.conf` отключить `gzip` или `etag off` в nginx). Обычно достаточно задокументировать.

**Тесты (`tests/Feature/Shared/CacheHeadersTest.php` — новый):**
- `test_etag_differs_across_endpoints_with_identical_bodies` — два разных URL с пустым body → разные ETag.
- `test_cross_endpoint_etag_does_not_yield_304` — ETag от `/contacts`, запрос `/charges` с ним → 200.
- `test_if_none_match_multi_value_any_match_returns_304` — `"bogus", <real>, "x"` → 304.
- `test_weak_comparison_if_none_match` — `W/"<strong>"` → 304.
- `test_if_none_match_wildcard_returns_304` — `*` → 304.
- `test_status_returns_etag` — `/v1/status` имеет ETag header.
- `test_sdks_returns_etag` — `/v1/sdks` имеет ETag header.
- Регрессии: 4xx не имеет ETag, 304 не тарифицирует кредиты (0), CACHEABLE_ROUTES отдают `public, max-age=3600`.

---

### PR28 — Concurrency: per-client headers + pipeline порядок

**Файл:** [client-api/app/Shared/Middleware/ConcurrencyLimiter.php](client-api/app/Shared/Middleware/ConcurrencyLimiter.php)

**Баг 28.1 — `X-Concurrent-Limit` показывает global (50), а клиентам заявлен per-client (10).**

[ConcurrencyLimiter.php:70-72, 98-100](client-api/app/Shared/Middleware/ConcurrencyLimiter.php#L70-L100): middleware пишет в request.attributes `concurrent_global_current/limit` и отдаёт их как `X-Concurrent-Limit` в response. Но для клиента полезнее видеть **его собственный** лимит и текущее потребление (per-client), или хотя бы `min(client_limit, global_remaining)`.

**Фикс:** при acquire per-client slot сохранять также `concurrent_client_current / concurrent_client_limit`, и в response-финализации:
```php
$response->headers->set('X-Concurrent-Requests', (string) $clientCurrent);
$response->headers->set('X-Concurrent-Limit', (string) $clientLimit);
// дополнительно:
$response->headers->set('X-Concurrent-Global-Limit', (string) $globalLimit);
```
Клиенту нужны **оба** показателя, но первичный `X-Concurrent-Limit` должен отражать per-client (как обещает доки).

**Баг 28.2 — по факту лимит с одной машины не достижим (max cr=4) — артефакт теста, не баг кода.**

Подтверждено QA: 120 параллельных HTTP/2 streams → server seeing max cr=4. Причина — Octane+FrankenPHP обрабатывает req за 1-78мс, окно для накопления concurrent слишком короткое при network latency клиента ~150мс. Документация должна добавить секцию "как воспроизвести concurrency limit" (распределённый клиент с разных IP). **Это doc-issue, не код.**

**Баг 28.3 — 429 concurrency vs rate-limit неразличимы в ошибке для клиента.**

В [ApiException.php:47-55](client-api/app/Shared/Exceptions/ApiException.php#L47-L55) error codes разные (`rate_limit_exceeded` / `concurrency_limit_exceeded`) — фактически работают. Но QA видит все 429 как `rate_limit_exceeded` потому что concurrency по факту не срабатывает (см. 28.2). **Фикс не нужен**, только задокументировать, что у клиента реально выйдет rate-limit первым.

**Баг 28.4 — `Retry-After: 1` для concurrency-429**

В [ConcurrencyLimiter.php:223](client-api/app/Shared/Middleware/ConcurrencyLimiter.php#L223) пишется `concurrency_retry_after=1` в attributes, но сам `Retry-After` header на concurrency-429 не ставится (видимо, эти attr нигде не читаются). Нужно в ExceptionHandler (где оборачивается `ApiException::concurrencyLimitExceeded` в response) добавить `Retry-After: 1`.

Проверить в `App\Exceptions\Handler` / `bootstrap/app.php` соответствующий renderable — и если там ловится `concurrency_limit_exceeded`, добавить header.

**Тесты:** расширить [client-api/tests/Feature/Middleware/ConcurrencyLimiterTest.php](client-api/tests/Feature/Middleware/ConcurrencyLimiterTest.php):
- `test_x_concurrent_limit_reflects_client_limit_not_global`.
- `test_concurrency_429_includes_retry_after_1`.
- `test_concurrency_error_code_is_concurrency_limit_exceeded` (отличает от rate_limit_exceeded).

**PR28 частично перекрывается с PR25 (release/TTL tests) — объединить в один PR.**

---

### PR29 — Per-endpoint rate-limits → документирование как "не поддерживается" (решено)

**Решение:** фичу не реализуем. Убрать упоминания per-endpoint rate-limits из документации и OpenAPI-спеки — чтобы не было расхождения между docs и реальностью.

**Что поправить:**
- [client-api/openapi-current.json](client-api/openapi-current.json) и копии в [client-api/public/specs/](client-api/public/specs/) — удалить / переформулировать секции про per-endpoint throttling.
- `resources/views/docs/*` или markdown-файлы в `client-api/` — если есть упоминание.
- Если есть пометки в Scramble-аннотациях в контроллерах — проверить и убрать.

**Тесты:** не требуются (только doc-изменение).

---

### PR30 — Dedup: нормализация CSV-значений внутри query-параметров

**Файл:** [client-api/app/Modules/Dedup/Services/DedupService.php](client-api/app/Modules/Dedup/Services/DedupService.php)

**Симптом (QA-скрин):** `GET /companies/:cn?include=enriched.info,enriched.rating,enriched.vat,enriched.description` vs тот же запрос с другим порядком значений внутри CSV → каждый считается новым, оба списываются.

**Root cause:** [DedupService::sortQueryString()](client-api/app/Modules/Dedup/Services/DedupService.php#L34-L44) сортирует только **ключи** (`ksort`), а значения — как пришли. `include=A,B,C` ≠ `include=C,A,B` для hash, хотя семантически это один запрос.

**Фикс:** добавить нормализацию значений — для параметров, где значение — CSV (или multi-value), раскладывать → сортировать → склеивать:

```php
private function sortQueryString(string $queryString): string
{
    if ($queryString === '') return '';
    parse_str($queryString, $params);
    ksort($params);

    // Для CSV-параметров сортируем значения
    foreach ($params as $key => $value) {
        if (is_string($value) && str_contains($value, ',')) {
            $parts = array_map('trim', explode(',', $value));
            sort($parts);
            $params[$key] = implode(',', $parts);
        } elseif (is_array($value)) {
            sort($value);
            $params[$key] = $value;
        }
    }
    return http_build_query($params);
}
```

**Альтернатива (точечнее):** нормализация только для известных CSV-параметров (`include`, `fields`, и т.д.) — через whitelist.

**Тесты (`tests/Feature/Dedup/DedupKeyNormalizationTest.php` — новый):**
- `test_dedup_key_normalizes_csv_include_order` — `?include=a,b,c` и `?include=c,a,b` → одинаковый dedup-key → второй запрос возвращает `X-Dedup-Hit: true`, 0 кредитов.
- `test_dedup_key_normalizes_param_order` — `?a=1&b=2` vs `?b=2&a=1` → uniform (регрессия существующего поведения).
- `test_dedup_key_csv_different_values_still_miss` — `?include=a,b` vs `?include=a,c` → разные ключи.

---

### PR31 — Webhook `event_type=test` не допустимое значение

**Симптом (QA-скрин):** `GET /v1/account/webhook-deliveries?status=success&event_type=test` → 422 `"Invalid event type. Allowed: company.updated, officer.changed, filing.new, ..."`. При этом в body `data.event_type = "test"` (такая запись уже есть в БД).

**Источник валидации:** Вероятнее всего в `WebhookDeliveriesController::index()` или связанном FormRequest. В [WebhookEventType.php](client-api/app/Shared/Enums/WebhookEventType.php) значения `test` нет. Но dispatch тестового вебхука (см. `WebhookController::test()` / `test-delivery` action) записывает delivery с `event_type='test'`.

**Решение:** Вариант Б — разрешить `test` только в фильтре, enum не трогаем.

В request-validator фильтра `/account/webhook-deliveries` по `event_type` добавить `test`:
```php
'event_type' => ['sometimes', 'string', Rule::in([...WebhookEventType::values(), 'test'])],
```
Enum [WebhookEventType](client-api/app/Shared/Enums/WebhookEventType.php) остаётся неизменным — test-события служебные, не входят в доменный перечень.

**Тесты:**
- `test_webhook_deliveries_filter_by_event_type_test_ok` — `?event_type=test` → 200.
- Регрессия `?event_type=bogus` → 422.

**Critical files:**
- Controller для `/account/webhook-deliveries` (найти точное место) + его Request-класс.

---

### PR32 — Документация: 413 vs 422 для Body-Limit

**Ситуация:** OpenAPI/доки обещают 422, реально `RequestBodyLimit` middleware бросает [ApiException::payloadTooLarge()](client-api/app/Shared/Exceptions/ApiException.php#L62-L65) → 413. **413 правильнее** (RFC 9110 §15.5.14) — фикс **только в документации**.

**Фикс:** найти и поправить все упоминания 422 для body-limit в:
- [client-api/openapi-current.json](client-api/openapi-current.json)
- [client-api/public/specs/](client-api/public/specs/)
- markdown-докам в [client-api/README.md](client-api/README.md) / `resources/views` если есть
- Scramble-конфиг [client-api/config/scramble.php](client-api/config/scramble.php) (если там hardcoded)

**Тест:** `test_oversized_body_returns_413_not_422` (новый, если нет) — POST с body > 1MB → 413 + `error.code = payload_too_large`.

---

### PR33 — `company.type` возвращается как объект, QA ожидает массив

**Наблюдение (Tigран):** на endpoint `/companies/:cn/insolvency` поле `type_of_case` — объект `{"key":"","value":""}`, ожидается массив (вероятно, у компании может быть несколько case_types).

**Нужно уточнить у продукта:**
- Это `type_of_case` внутри insolvency record, или `company.type` (на уровне компании)?
- Реальная структура в БД — array/single?

**Предположение по коду:** в [CompanyResource.php:40](client-api/app/Modules/Company/Resources/CompanyResource.php#L40) `'company_type' => $this->type ? ($this->type['key'] ?? $this->type) : null` — возвращает string (key). Значит issue **не здесь**, а скорее в insolvency controller/resource. Проверить нужные файлы при имплементации.

**Статус:** требует уточнения у QA/продукта. Оставляю placeholder-раздел.

---

### PR34 — `/directories/officers` → 404

**Наблюдение (из ETag отчёта, info).** Побочно замечено: `GET /v1/directories/officers` → 404, хотя секция директорий вроде должна существовать.

**Действие:** проверить `routes/api.php` и `DirectoryController` — либо добавить секцию `officers` в common_directory seed/справочник, либо убрать из документации. Небольшой фикс — отдельный PR.

---

### PR35 — `/companies/{cn}/insolvency` возвращает пустой список компаний (?)

**Скрин:** "Этот запрос отдает пустой список компаний" — надо уточнить у QA контекст (скрин двусмысленный). Возможно, речь идёт об `insolvency_events` внутри компании (как на следующем скрине), а не о списке company-to-insolvency. **Требует уточнения.**

---

## Порядок реализации (обновлённый)

**Волна 1 — data bugs (быстро):**
1. PR20 (sic_codes cast + audit)
2. PR21 (ExportType enum)
3. PR32 (docs 413/422)
4. PR34 (directories/officers)

**Волна 2 — функциональность:**
5. PR22 (related-companies service)
6. PR23 (rate-limit cascade fix + regression)
7. PR30 (dedup CSV normalization)

**Волна 3 — корректность каширования и concurrency:**
8. PR27 (CacheHeaders ETag + /status/sdks)
9. PR25+PR28 merged (Concurrency: TTL bump, release tests, per-client headers, retry-after)
10. PR26 (billing coverage)

**Волна 4 — уточнения от продукта/QA:**
11. PR29 (per-endpoint limits — ждём product-решения)
12. PR31 (webhook event_type=test — выбрать вариант А/Б)
13. PR33 (company.type структура — уточнить)
14. PR35 (insolvency пустой — уточнить контекст)

PR24 (warmup) — **не делаем**.

**Финал:** `pint`, `phpstan`, `php artisan test --testdox` — всё зелёное.

---

## Команды (в контейнере api)

```bash
./compose.sh exec -T api bash -lc 'vendor/bin/pint'
./compose.sh exec -T api bash -lc 'vendor/bin/phpstan analyze --memory-limit=512M'
./compose.sh exec -T api bash -lc 'php artisan test --testdox'
```

---

## Верификация E2E

(v3 п.1-7 оставляем), добавляем:

8. **ETag cross-endpoint:** `get_etag /companies/X/charges` ≠ `get_etag /companies/X/contacts`; `curl -H "If-None-Match: <etag от /contacts>" /charges` → 200.
9. **ETag multi-value:** `"bogus", <real>, "x"` → 304.
10. **ETag weak:** `W/"<real>"` → 304.
11. **ETag wildcard:** `*` → 304.
12. **Status/SDKs имеют ETag:** `curl -D- /v1/status | grep -i etag:` → не пусто.
13. **Concurrency headers:** client с per-client-limit=10 → `X-Concurrent-Limit: 10` (не 50); 429 concurrency → `Retry-After: 1`, `error.code: concurrency_limit_exceeded`.
14. **Dedup CSV:** `GET ?include=a,b,c` → charge; `GET ?include=c,a,b` → `X-Dedup-Hit: true`, 0 cred.
15. **Webhook deliveries:** `?event_type=test` → 200, `?event_type=bogus` → 422.
16. **Body limit:** POST >1MB → 413 + `error.code=payload_too_large` (docs синхронизированы).

---

## Критические файлы (итог)

| PR | Файл | Действие |
|---|---|---|
| PR20 | [Company.php](client-api/app/Modules/Company/Models/Company.php) | casts → `PostgresArray/PostgresJsonArray` + audit |
| PR21 | `app/Modules/Export/Enums/ExportType.php` | новый backed enum |
| PR21 | [CreateExportRequest.php](client-api/app/Modules/Export/Requests/CreateExportRequest.php), [ExportController.php](client-api/app/Modules/Export/Controllers/ExportController.php), [ExportService.php](client-api/app/Modules/Export/Services/ExportService.php), [ProcessExportJob.php](client-api/app/Modules/Export/Jobs/ProcessExportJob.php) | применение enum + strtolower |
| PR22 | `app/Modules/Company/Services/RelatedCompaniesService.php` | новый сервис, UNION ALL 5 источников |
| PR22 | [CompanyRelatedController.php](client-api/app/Modules/Company/Controllers/CompanyRelatedController.php) | DI сервиса |
| PR23 | [RateLimitService.php:27-34](client-api/app/Modules/RateLimit/Services/RateLimitService.php#L27-L34) | убрать early-return, инкрементировать все окна |
| PR25+28 | [ConcurrencyLimiter.php](client-api/app/Shared/Middleware/ConcurrencyLimiter.php) | KEY_TTL 30→60, X-Concurrent-Limit per-client, Retry-After на 429 |
| PR27 | [CacheHeaders.php](client-api/app/Shared/Middleware/CacheHeaders.php) | routeId в ETag hash, `ifNoneMatchMatches()` helper |
| PR27 | [routes/api.php:35-43](client-api/routes/api.php#L35-L43) | добавить `CacheHeaders::class` на status/sdks |
| PR30 | [DedupService.php](client-api/app/Modules/Dedup/Services/DedupService.php) | sortQueryString + CSV-values sort |
| PR31 | Webhook deliveries controller/request | разрешить `event_type=test` в фильтре |
| PR32 | [openapi-current.json](client-api/openapi-current.json), доки | 422 → 413 для body-limit |
| PR34 | routes/api.php + DirectoryController | починить `/directories/officers` |

## Новые тесты

| PR | Тест | Файл |
|---|---|---|
| PR20 | Unit + Feature для sic_codes/previous_company_names cast | `tests/Unit/Models/CompanySicCodesTest.php`, `tests/Feature/Api/CompanyProfileTest.php` |
| PR21 | case-insensitive export type | `tests/Feature/Export/ExportControllerTest.php` |
| PR22 | 5 SQL-путей + E2E BOHD→CEDAR | `tests/Unit/Services/RelatedCompaniesServiceTest.php`, `tests/Feature/Api/RelatedCompaniesTest.php` |
| PR23 | fixed-window + cascade regression | `tests/Feature/Api/RateLimitWindowTest.php` |
| PR25+28 | release on exception, TTL, X-Concurrent-Limit per-client, Retry-After | `tests/Feature/Middleware/ConcurrencyLimiterTest.php` |
| PR26 | billing refund/grace/dedup | `tests/Feature/Api/BillingTest.php` |
| PR27 | ETag per-route, multi/weak/wildcard If-None-Match, /status+/sdks ETag | `tests/Feature/Shared/CacheHeadersTest.php` |
| PR30 | CSV normalization in dedup | `tests/Feature/Dedup/DedupKeyNormalizationTest.php` |
| PR31 | event_type=test допустимо в фильтре | `tests/Feature/Webhook/DeliveriesFilterTest.php` |
| PR32 | body >1MB → 413 | `tests/Feature/Api/BodyLimitTest.php` |

---

## Открытые вопросы (решены / остаются)

1. ~~PR29 per-endpoint limits~~ — **решено: документируем как не поддерживается**.
2. ~~PR31 webhook test~~ — **решено: разрешаем `test` только в фильтре**.
3. **PR33 company/insolvency type** — в каком поле и какой ожидается формат (array vs object)? Уточнить у QA при имплементации.
4. **PR35 insolvency empty** — какой именно запрос и что должен отдавать? Уточнить у QA.

---

## Ссылки

- План коллеги v3: `/home/pavel/.claude/plans/fluffy-humming-kurzweil.md`.
- Cache report от QA: вложен в сообщение пользователя (api-etag-caching.md) — использован как источник истины для PR27.
