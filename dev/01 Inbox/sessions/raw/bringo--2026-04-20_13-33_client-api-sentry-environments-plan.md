---
type: session-plan-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-20_13-33_client-api-sentry-environments.md
session_date: 2026-04-20
tags:
  - session-plan
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# План: Sentry в client-api — разделение окружений stg/prod и диагностика отсутствия events

## Context

На дашборде Sentry проекта `bcu-client-api` видна активность:
- **Transactions**: 27 164 за 14 дней, Apdex строится, Failure Rate до 70% пиков
- **Events (Issues)**: 0 — "Waiting for events"

Две проблемы, которые нужно решить:

1. **Основная (по сообщению пользователя)**: сейчас **stg и prod шлют события в Sentry с одинаковым `environment=production`** — их невозможно различить на дашборде. Нужно настроить разные environments.
2. **Производная**: почему вообще 0 events при явном наличии failed-транзакций.

## Первопричины

### Проблема 1 — environment не различается

[client-api/config/sentry.php:10](client-api/config/sentry.php#L10):
```php
'environment' => env('APP_ENV', 'production'),
```

[client-api/helmfile.d/values/common/client-api.yaml:3](client-api/helmfile.d/values/common/client-api.yaml#L3):
```yaml
APP_ENV: "production"
```

`commonEnvs` применяется и в stg (`helmfile.d/values/stg/ie/dc1/client-api.yaml`), и в prod (`.../prod/ie/dc1/...`) — ни один из них `APP_ENV` **не переопределяет**. Итого: оба кластера идентифицируются в Sentry как `production`.

### Проблема 2 — видны transactions, но 0 events

Это **не "нет событий от Sentry"**, а "нет error-событий в Issues". Transactions — отдельный поток performance-трейсинга (`SENTRY_TRACES_SAMPLE_RATE=1.0` в [common/client-api.yaml:11](client-api/helmfile.d/values/common/client-api.yaml#L11)), они идут независимо от error-reporting. Failure Rate на графике — это доля transactions, у которых `status != ok` (обычно HTTP 5xx в response), а не отдельные event'ы.

Error-события отсылаются только через `report($e)` → Sentry SDK → `before_send` → отправка. Возможные блокираторы в порядке вероятности:

1. **Фильтр `SentryBeforeSend`** — [client-api/app/Infrastructure/Sentry/SentryBeforeSend.php:18-46](client-api/app/Infrastructure/Sentry/SentryBeforeSend.php#L18-L46) отбрасывает `HttpExceptionInterface(4xx)`, `ApiException(4xx)`, `ValidationException`. Это **намеренно** (комментарий в [config/sentry.php:18](client-api/config/sentry.php#L18)). 5xx должны проходить.
2. **Реальное отсутствие 5xx** — в логике [bootstrap/app.php:137-151](client-api/bootstrap/app.php#L137-L151) catch-all Throwable вызывает `report($e)` только если `$request->is('v1/*')` и тип не ApiException/ValidationException/NotFoundHttpException. Если 5xx пики на графике — это failed transactions внутри 4xx response (например, validation), events не будет.
3. **Octane request isolation** — в некоторых конфигурациях Octane событие может не успеть уйти до переиспользования воркера. Маловероятно на 4.24 sentry-laravel, но проверить стоит.
4. **DSN в secrets битый/не тот** — DSN зашифрован в `helmfile.d/values/{stg,prod}/**/client-api.secrets.yaml`. Если DSN указывает на другой проект Sentry или ключ отозван — performance может идти (на ингест performance другой endpoint), а events нет. **Маловероятно** (обычно performance тоже через тот же DSN), но проверить.

## Рекомендуемый фикс

### Шаг 1. Разделить environments в Sentry (основная задача)

Подход: отдельная переменная `SENTRY_ENVIRONMENT`, не трогаем `APP_ENV` (Laravel-логика может на него завязана: `app()->isProduction()` уже используется в [bootstrap/app.php:145](client-api/bootstrap/app.php#L145)).

**Изменения:**

1. [client-api/config/sentry.php:10](client-api/config/sentry.php#L10)
   ```php
   'environment' => env('SENTRY_ENVIRONMENT', env('APP_ENV', 'production')),
   ```

2. [client-api/helmfile.d/values/stg/ie/dc1/client-api.yaml](client-api/helmfile.d/values/stg/ie/dc1/client-api.yaml) — в `commonEnvs`:
   ```yaml
   SENTRY_ENVIRONMENT: "staging"
   ```

3. [client-api/helmfile.d/values/prod/ie/dc1/client-api.yaml](client-api/helmfile.d/values/prod/ie/dc1/client-api.yaml) — в `commonEnvs`:
   ```yaml
   SENTRY_ENVIRONMENT: "production"
   ```

4. Для локалки (опционально, но желательно для консистентности): [compose.d/client-api/.env](compose.d/client-api/.env) рядом с пустым `SENTRY_LARAVEL_DSN=` добавить:
   ```
   SENTRY_ENVIRONMENT=local
   ```
   Эффекта не даст пока DSN пуст, но избавит от будущих сюрпризов если кто-то включит Sentry локально.

После деплоя в Sentry появятся два environments в dropdown; текущие ретроспективные данные останутся помеченными `production` — это нормально, разделение работает с момента деплоя.

### Шаг 2. Диагностика events=0 (после Шага 1)

Выполняется отдельно, **не блокирует** Шаг 1. Порядок минимального вмешательства:

**2.1. Test capture** — `php artisan tinker` на stg pod'е:
```php
\Sentry\captureException(new \RuntimeException('sentry-smoke-test'));
```
Если событие появилось в Sentry с `environment=staging` → DSN и SDK рабочие, осталось понять почему реальные ошибки не ловятся. Если нет → проблема в DSN/доставке.

**2.2. Проверить реальные 5xx в ClickHouse** — `request_log` таблица (упомянута в [CLAUDE.md#monitoring](client-api/CLAUDE.md)):
```sql
SELECT count() FROM request_log
WHERE status_code >= 500 AND timestamp > now() - INTERVAL 14 DAY
```
Если `0` — events и не должно быть. Failure Rate на графике — это failed transactions с 4xx (например, concurrency-rejected 429 или validation 422), их beforeSend отбрасывает. Вопрос закрыт.

**2.3. Если 5xx есть, а events нет** — включить отладку Sentry-транспорта: временно в catch-all [bootstrap/app.php:139](client-api/bootstrap/app.php#L139) рядом с `report($e)` добавить прямой вызов `\Sentry\captureException($e)` и посмотреть логи `storage/logs/laravel.log` на stg — sentry-laravel пишет в Laravel log warnings при ошибке транспорта.

**2.4. Последняя ступень** — проверить DSN: расшифровать `client-api.secrets.yaml` на stg (`sops -d ...`), сверить `https://<key>@<host>/<project_id>` с проектом `bcu-client-api` в Sentry UI (Settings → Client Keys).

### Критичные файлы

- [client-api/config/sentry.php](client-api/config/sentry.php) — изменить строку 10
- [client-api/helmfile.d/values/stg/ie/dc1/client-api.yaml](client-api/helmfile.d/values/stg/ie/dc1/client-api.yaml) — добавить `SENTRY_ENVIRONMENT`
- [client-api/helmfile.d/values/prod/ie/dc1/client-api.yaml](client-api/helmfile.d/values/prod/ie/dc1/client-api.yaml) — добавить `SENTRY_ENVIRONMENT`
- [client-api/helmfile.d/values/common/client-api.yaml](client-api/helmfile.d/values/common/client-api.yaml) — **не трогаем** (общие настройки)
- [compose.d/client-api/.env](compose.d/client-api/.env) — опционально, для локалки

### Файлы-ссылки для контекста (не меняем)

- [client-api/bootstrap/app.php#L137-L151](client-api/bootstrap/app.php#L137-L151) — catch-all handler с `report($e)`
- [client-api/app/Infrastructure/Sentry/SentryBeforeSend.php](client-api/app/Infrastructure/Sentry/SentryBeforeSend.php) — фильтр 4xx/ValidationException (оставляем как есть — это бизнес-правило)
- [client-api/app/Infrastructure/Sentry/SentryContextMiddleware.php](client-api/app/Infrastructure/Sentry/SentryContextMiddleware.php) — контекст-теги в Sentry scope

## Что НЕ делаем

- Не меняем `SentryBeforeSend` — фильтрация 4xx намеренна, подтверждена комментарием в config и CLAUDE.md (раздел Monitoring).
- Не меняем `APP_ENV` в helmfile — `app()->isProduction()` в [bootstrap/app.php:145](client-api/bootstrap/app.php#L145) и, вероятно, другие места завязаны на это значение. Разделение окружений делаем отдельной переменной.
- Не трогаем `SENTRY_TRACES_SAMPLE_RATE` — пользователь сам видит, что performance данные полезны.
- Не мигрируем на `Sentry\Laravel\Integration::handles($exceptions)` в bootstrap/app.php — текущий `report($e)` в catch-all делает то же самое через стандартный Laravel механизм.

## Верификация

После деплоя stg (первым):

1. **Sentry UI → Environments dropdown** — должны появиться `staging` и `production` как разные значения; старые записи остаются с текущим environment.
2. **Sentry UI → bcu-client-api → фильтр `environment:staging`** — должны идти новые transactions с этим тегом в течение нескольких минут после деплоя.
3. **Smoke test в tinker на stg pod**:
   ```bash
   kubectl exec -n bcu-stg deploy/client-api-api -- php artisan tinker --execute='\Sentry\captureException(new \RuntimeException("env-split-smoke-test"));'
   ```
   Ожидание: событие появляется в Issues с `environment=staging` в течение ~30 секунд.
4. **После фикса stg повторить для prod** — аналогично в `environment=production`.
5. **Отделить в alerts**: в Sentry → Alerts → проверить, что правила умеют фильтровать по environment (типично — умеют). Это позволит не поднимать тревогу на stg-ошибках.

Если Шаг 2 диагностики покажет, что 5xx просто нет в request_log — считаем проблему "events=0" ложной тревогой и закрываем.
