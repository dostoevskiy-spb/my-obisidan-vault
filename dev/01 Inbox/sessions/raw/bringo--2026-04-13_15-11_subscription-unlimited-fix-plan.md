---
type: session-plan-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-13_15-11_subscription-unlimited-fix.md
session_date: 2026-04-13
tags:
  - session-plan
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# План: Фикс отсутствия subscription в gRPC ответах для ENTERPRISE подписок

## Контекст

Пользователь сообщил два связанных бага:
1. В ответе `UserProfileService.GetFull` перестал приходить объект `subscription`
2. То же самое в `BillingService.GetActiveSubscription`

Уточнение: проблема воспроизводится **только когда у пользователя ENTERPRISE-подписка**.

## Root cause

Рассинхронизация PHP enum с БД и proto-схемой по полю `period_id`:

- Миграция [migration/migrations/db/1775733130_data_add_unlimited_subscription_period.php](../../dev/www/bringo/bringo-co-uk/main/migration/migrations/db/1775733130_data_add_unlimited_subscription_period.php) добавила в `billing.subscription_period` запись `(3, 'Unlimited')`. Этот период используется для Enterprise-подписок.
- proto [shared-models/proto/Api/V2/Model/Billing/Subscription.proto:12](../../dev/www/bringo/bringo-co-uk/main/shared-models/proto/Api/V2/Model/Billing/Subscription.proto#L12) уже содержит `UNLIMITED = 3`.
- Но в [backend/src/Billing/Enum/SubscriptionPeriodEnum.php](../../dev/www/bringo/bringo-co-uk/main/backend/src/Billing/Enum/SubscriptionPeriodEnum.php) есть только `MONTHLY=0`, `ANNUALLY=1`, `DAILY=2` — `UNLIMITED=3` отсутствует.
- [Subscription entity:42-43](../../dev/www/bringo/bringo-co-uk/main/backend/src/Billing/Entity/Subscription.php#L42-L43) маппит колонку `period_id` через `enumType: SubscriptionPeriodEnum::class`.
- `SubscriptionService::getActiveSubscription()` ([SubscriptionService.php:150-160](../../dev/www/bringo/bringo-co-uk/main/backend/src/Billing/Service/SubscriptionService.php#L150-L160)) вызывает `findOneBy(['userId' => ..., 'isActive' => true])`. Для Enterprise-юзера в БД есть запись с `period_id=3, is_active=true`, и при hydrate Doctrine вызывает `SubscriptionPeriodEnum::from(3)` → `\ValueError`.
- Exception всплывает из обоих gRPC-методов — фронт получает ошибку или пустой ответ, отсюда симптом "не приходит subscription".

Оба бага — один и тот же дефект, поскольку оба эндпоинта зовут одну и ту же `SubscriptionService::getActiveSubscription()`:
- [UserProfileService.php:198](../../dev/www/bringo/bringo-co-uk/main/backend/src/Controller/V2/Grpc/Account/UserProfileService.php#L198)
- [BillingService.php:121](../../dev/www/bringo/bringo-co-uk/main/backend/src/Controller/V2/Grpc/Billing/BillingService.php#L121)

## Решение

### Шаг 1 (обязательный) — добавить case UNLIMITED в enum

Файл: `backend/src/Billing/Enum/SubscriptionPeriodEnum.php`

```php
enum SubscriptionPeriodEnum: int
{
    case MONTHLY = 0;
    case ANNUALLY = 1;
    case DAILY = 2;
    case UNLIMITED = 3;

    public function getTitle(): string
    {
        return match ($this) {
            SubscriptionPeriodEnum::MONTHLY => 'Monthly Subscription',
            SubscriptionPeriodEnum::ANNUALLY => 'Annual Subscription',
            SubscriptionPeriodEnum::DAILY => 'Daily Subscription',
            SubscriptionPeriodEnum::UNLIMITED => 'Unlimited Subscription',
        };
    }
}
```

Примечание: добавление кейса в `getTitle()` обязательно — иначе `UnhandledMatchError` при вызове.

После этого изменения:
- `Doctrine` сможет загрузить Enterprise-подписку
- `BillingProtobufTransformer::transformSubscriptionToProtobuf()` корректно отдаст `period = 3` в proto (поле принимает int)
- Внутри `transformSubscriptionToProtobuf` вызов `findStripeSubscriptionBySubscription` для Enterprise вернёт `null` (Stripe-подписки нет) — это безопасно, transformer уже обрабатывает этот случай

### Шаг 2 (защитный) — проверить остальные `match($period)` без default

Места, которые могут упасть с `UnhandledMatchError` если код когда-нибудь дойдёт до них с UNLIMITED-подпиской:

| Файл | Строка | Контекст |
|---|---|---|
| `backend/src/Billing/Entity/Subscription.php` | 88-92 | `__construct` вычисляет `endDate` |
| `backend/src/Billing/Service/RowBalanceService.php` | 69-89, 158-178 | расчёт row balance по периоду |
| `backend/src/Billing/Service/SubscriptionPriceService.php` | 15-17 | цена подписки |
| `backend/src/Billing/Service/SubscriptionNotifier.php` | 49-132 | email-нотификации |

Для **самого фикса бага (горячий путь чтения)** эти места **не задействуются** — Enterprise-подписку никто не создаёт через `new Subscription(UNLIMITED)` в backend (вероятно, она вставляется отдельным сервисом/прямым SQL извне), а нотификации/balance/цена для Enterprise не считаются по периоду.

**Рекомендация:** в рамках текущей задачи **не трогать эти `match`**, чтобы не расширять scope. Если появится отдельный тикет на полную поддержку Enterprise — обработать там.

### Шаг 3 (отдельный тикет, не входит в этот фикс) — proto-поле `subscription_type`

В Subscription.proto есть `SubscriptionType subscription_type = 12`, в БД появилась колонка `billing.subscription.subscription_type_id` (миграции 1775733127–1775733129). В Doctrine entity нет соответствующего свойства, и `BillingProtobufTransformer` не выставляет это поле в proto. Сейчас безвредно, но фронт не может отличить Standard от Enterprise через GetActiveSubscription/GetFull. Это **отдельная задача** — выходит за рамки исправляемого бага "subscription не приходит".

## Файлы для изменения

- `backend/src/Billing/Enum/SubscriptionPeriodEnum.php` — добавить case `UNLIMITED = 3` и кейс в `getTitle()`

Это **единственное** изменение для фикса.

## Верификация

1. Перезапустить backend-контейнер чтобы применился изменённый enum (Symfony cache):
   ```bash
   ./compose.sh exec -T backend php bin/console cache:clear
   ```
2. Проверить, что у Enterprise-юзера в БД есть запись с `period_id=3` и `is_active=true`:
   ```sql
   SELECT subscription_id, user_id, period_id, is_active, status_id, subscription_type_id
   FROM billing.subscription
   WHERE is_active = true AND period_id = 3;
   ```
3. Получить токен этого пользователя и вызвать оба эндпоинта (через grpcurl или фронт):
   - `bringo.api.v2.grpc.account.user_profile.UserProfileService/GetFull` — в ответе должен присутствовать `subscription` с `period: 3`
   - `bringo.api.v2.grpc.billing.BillingService/GetActiveSubscription` — то же самое
4. Логи backend не должны содержать `ValueError: 3 is not a valid backing value for enum App\Billing\Enum\SubscriptionPeriodEnum`.
5. Регрессионная проверка для Standard-юзеров (yearly-active@bcu.localhost, monthly-active@bcu.localhost) — оба эндпоинта возвращают subscription как раньше.
