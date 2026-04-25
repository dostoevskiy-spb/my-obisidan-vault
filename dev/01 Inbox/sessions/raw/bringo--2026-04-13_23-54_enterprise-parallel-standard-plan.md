---
type: session-plan-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-13_23-54_enterprise-parallel-standard.md
session_date: 2026-04-13
tags:
  - session-plan
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# План: `billing:enterprise-subscription:create` — гарантированная работа + полноценный UI-доступ Enterprise

## Context

Пользователь хочет чтобы команда `billing:enterprise-subscription:create`:
1. Работала для юзеров с активной Monthly/Yearly (Stripe) подпиской — **параллельное сосуществование STANDARD + ENTERPRISE**.
2. Оставляла БД в состоянии, при котором gRPC `ApiTokenService.GetClientInfo` возвращает валидные данные.
3. Давала Enterprise-юзеру работающие **платные UI-функции** (Export строк + Apollo — списки/email/телефоны) через правильно проинициализированный RowBalance.

**Главное ограничение: вся текущая Stripe-логика должна работать как сейчас.** Enterprise живёт рядом, никак Stripe не трогает.

## Решения пользователя

| Вопрос | Решение |
|---|---|
| RowBalance для Enterprise | Опции команды (`--rows` и опции по счётчикам Apollo). Заполнять все соответствующие счётчики. |
| `GetActiveSubscription` gRPC для Enterprise-only | Fallback на ENTERPRISE, если STANDARD нет |
| Stripe-вебхук / блокировки | **Не трогаем** — параллельная работа. Варианты защиты сохранить в память для будущего. |

## Счётчики RowBalance — что заполняем

Изучил [RowBalance.php](backend/src/Billing/Entity/RowBalance.php). Entity содержит:

**Текущие балансы (списываются при операциях):**
- `amount_companies` — строки компаний в экспорте
- `amount_pcs` — строки PSC в экспорте
- `amount_officers` — строки officers в экспорте
- `amount_employee_list_action` — Apollo list requests
- `amount_employee_email_action` — Apollo email requests
- `amount_employee_phone_action` — Apollo phone requests

**Hold-поля (резерв при hold/release во время операции):**
- `hold_companies`, `hold_pcs`, `hold_officers` — инициализируются 0, не трогаем

**Init-значения (база для `resetAmounts` при renewal):**
- `init_rows_amount` — для companies/pcs/officers
- `init_employees_amount` (JSON `InitEmployeesAmount`) — для list/email/phone

**Служебное:**
- `fill_date` — дата заполнения

**Для Enterprise (period=UNLIMITED) сейчас все эти счётчики = 0** ([RowBalanceService.php:68-94](backend/src/Billing/Service/RowBalanceService.php#L68-L94)) — это и есть причина почему UI-функции не работают. Надо их выставить в корректные положительные значения.

## Производственные правки

### 1. Команда: опции `--rows` + Apollo-счётчики

Файл: [backend/src/Billing/Console/EnterpriseSubscriptionCreateCommand.php](backend/src/Billing/Console/EnterpriseSubscriptionCreateCommand.php)

Добавить опции (все опциональны, default=null → не трогать):
- `--rows=N` → `amount_companies`, `amount_pcs`, `amount_officers`, `init_rows_amount` = N
- `--employee-list=N` → `amount_employee_list_action` + компонент init list
- `--employee-email=N` → `amount_employee_email_action` + компонент init email
- `--employee-phone=N` → `amount_employee_phone_action` + компонент init phone

После `findOrCreateApiClient`:
```php
if (null !== $rowsInt || null !== $empListInt || null !== $empEmailInt || null !== $empPhoneInt) {
    $this->rowBalanceService->setSubscriptionAmounts(
        $subscription,
        $rowsInt,      // nullable — только те, что переданы
        $empListInt,
        $empEmailInt,
        $empPhoneInt,
    );
}
```

Новый метод `setSubscriptionAmounts` в core `RowBalanceService` — ниже.

Команда идемпотентна: повторный запуск с новыми `--rows`/`--employee-*` топ-апит значения.

Обновить success-output: `"... API client ID: %d. Row balance: {rows=X, list=Y, email=Z, phone=W}."`

### 2. Новый метод в [RowBalanceService.php](backend/src/Billing/Service/RowBalanceService.php)

```php
public function setSubscriptionAmounts(
    Subscription $subscription,
    ?int $rowsAmount,
    ?int $employeeListAmount,
    ?int $employeeEmailAmount,
    ?int $employeePhoneAmount,
): RowBalance {
    $rowBalance = $this->rowBalanceRepository->findOneBy(['subscription' => $subscription])
        ?? throw new RuntimeException("RowBalance not found for subscription {$subscription->getId()}");

    if (null !== $rowsAmount) {
        $rowBalance->setAmountCompanies($rowsAmount);
        $rowBalance->setAmountPcs($rowsAmount);
        $rowBalance->setAmountOfficers($rowsAmount);
        $rowBalance->setInitRowsAmount($rowsAmount);
    }

    $currentInit = $rowBalance->getInitEmployeesAmount();
    $list  = $employeeListAmount  ?? $currentInit->getList();
    $email = $employeeEmailAmount ?? $currentInit->getEmail();
    $phone = $employeePhoneAmount ?? $currentInit->getPhone();

    if (null !== $employeeListAmount)  { $rowBalance->setAmountEmployeeListAction($employeeListAmount); }
    if (null !== $employeeEmailAmount) { $rowBalance->setAmountEmployeeEmailAction($employeeEmailAmount); }
    if (null !== $employeePhoneAmount) { $rowBalance->setAmountEmployeePhoneAction($employeePhoneAmount); }

    if (null !== $employeeListAmount || null !== $employeeEmailAmount || null !== $employeePhoneAmount) {
        $rowBalance->setInitEmployeesAmount(new InitEmployeesAmount($list, $email, $phone));
    }

    return $rowBalance;
}
```

**Не трогаем `createForSubscription`** — он продолжает создавать RowBalance с нулями для UNLIMITED (как сейчас). Это важно: Stripe-потоки не задействуют этот метод для Enterprise (они вызывают для DAILY/MONTHLY/ANNUALLY), так что их поведение не меняется. Enterprise получает нули → команда топит вверх через новый метод.

### 3. `SubscriptionRepository::getForUserId` — детерминированный приоритет

Файл: [backend/src/Billing/Common/Repository/SubscriptionRepository.php:23-33](backend/src/Billing/Common/Repository/SubscriptionRepository.php#L23-L33)

Сейчас: `setMaxResults(1)` без ORDER BY — недетерминированно при двух активных подписках.

Правка:
```php
->orderBy('i.subscriptionType', 'ASC')   // STANDARD (=0) раньше ENTERPRISE (=1)
->addOrderBy('i.startDate', 'DESC')
```

**Влияние на Stripe-поток:** нулевое. Stripe всегда оперирует со STANDARD. Для STANDARD-only юзеров возвращается STANDARD (как раньше). Для Enterprise-only — Enterprise (как раньше). Для STANDARD+ENTERPRISE теперь гарантированно возвращается STANDARD → export/Apollo списывают из STANDARD.rowBalance (деньги идут из Stripe, что правильно).

### 4. `BillingService::GetActiveSubscription` — fallback на ENTERPRISE

Файл: [backend/src/Controller/V2/Grpc/Billing/BillingService.php:115-133](backend/src/Controller/V2/Grpc/Billing/BillingService.php#L115-L133)

```php
$subscription = $this->subscriptionService->getActiveSubscription($user->getId());
if (null === $subscription) {
    $subscription = $this->subscriptionService->getActiveEnterpriseSubscription($user->getId());
}
if (null !== $subscription) {
    $response->setSubscription($this->billingProtobufTransformer->transformSubscriptionToProtobuf($subscription));
}
```

То же применить в:
- [UserProfileService::GetProfile](backend/src/Controller/V2/Grpc/Account/UserProfileService.php) (строка 198)
- [AccountMeController::GET /me](backend/src/Controller/V2/Rest/AccountMeController.php) (строка 31)

**Влияние на Stripe-юзеров:** нулевое — у них есть STANDARD, fallback не срабатывает, поведение идентично текущему.

### Что НЕ правим (решено выше)

- **`createFree`** — оставляем как есть. Текущий путь: Stripe webhook → создаёт STANDARD/TRIAL, не вызывает `createFree`. Промокоды используют `createFree` — трогать без подтверждения бизнеса опасно.
- **`createEnterprise`** — уже корректно выкидывает `FailedPreconditionException` при активной Enterprise. Не добавляем проверку на STANDARD: команда в обёртке пропускает `createEnterprise` если Enterprise уже есть, и разрешает создать Enterprise параллельно STANDARD.
- **Stripe webhook handlers, CheckoutSession, SubscriptionUpdated** — вообще не трогаем. Все варианты блокировок — в "Future Extensions".

## Тесты

### Unit-тесты

**[EnterpriseSubscriptionCreateCommandTest.php](backend/tests/Billing/Console/EnterpriseSubscriptionCreateCommandTest.php)** — +6 тестов

| Тест | Проверяет |
|---|---|
| `testCommandWithExistingActiveEnterpriseReusesIt` | Reuse existing subscription, `createEnterprise` не вызывается, `findOrCreateApiClient` вызывается |
| `testCommandSucceedsForUserWithActiveStandardSubscription` | User с active STANDARD → команда создаёт Enterprise параллельно, успех |
| `testCommandWithoutCreditsSkipsBalanceUpdate` | `setClientCreditBalance` не вызывается |
| `testCommandWithRowsOptionCallsSetSubscriptionAmounts` | `--rows=1000` → `rowBalanceService->setSubscriptionAmounts($sub, 1000, null, null, null)` |
| `testCommandWithAllEmployeeOptionsCallsSetSubscriptionAmounts` | `--employee-list=100 --employee-email=50 --employee-phone=30` → вызов с null rows + 100/50/30 |
| `testCommandFailsGracefullyWhenApiClientCreationThrows` | error output, exit=FAILURE |

**[EnterpriseApiClientServiceTest.php](backend/tests/Service/Billing/EnterpriseApiClientServiceTest.php)** — +7 тестов (как описано ранее: sync by userId, createToken production/sandbox, revokeToken success/fail, listTokens, setClientCreditBalance, activate/deactivate).

**Новый `backend/tests/Service/Billing/RowBalanceServiceTest.php`** — 4 теста

| Тест | Проверяет |
|---|---|
| `testSetSubscriptionAmountsUpdatesAllRowFields` | `--rows=N`: amount_companies/pcs/officers/init_rows_amount = N |
| `testSetSubscriptionAmountsPreservesFieldsWhenNull` | `--rows=null`: row-счётчики не трогаются, можно обновлять только employees |
| `testSetSubscriptionAmountsUpdatesEmployeeFieldsIndependently` | list/email/phone устанавливаются независимо, init_employees_amount пересчитывается корректно |
| `testSetSubscriptionAmountsThrowsWhenRowBalanceMissing` | RowBalance не найден → RuntimeException |

**Новый `backend/tests/Service/Billing/SubscriptionRepositoryTest.php`** — 2 теста

| Тест | Проверяет |
|---|---|
| `testGetForUserIdReturnsStandardWhenBothActive` | STANDARD приоритет при конфликте |
| `testGetForUserIdReturnsEnterpriseWhenOnlyEnterpriseActive` | Enterprise-only → возвращает Enterprise |

Эти тесты должны быть integration-уровня (с реальной БД) или использовать `InMemoryRepository` — уточнить паттерн по существующим в проекте.

### Functional-тест

**Новый `backend/tests/Api/EnterpriseApiToken1Test.php`** — 8 сценариев

| Тест | Сценарий |
|---|---|
| `testCommandCreatesValidStateForFreshUser` | Свежий user + все опции (`--credits=100000 --rows=50000 --employee-list=1000 --employee-email=500 --employee-phone=300`) → `GetClientInfo` валидный, `GetRowsBalance` возвращает 50000/1000/500/300 |
| `testCommandSucceedsForUserWithStripeSubscription` | STANDARD через SubscriptionHelper → запуск команды → обе подписки активны, `GetClientInfo` валиден, `GetActiveSubscription` возвращает STANDARD (приоритет), `GetRowsBalance` читает из STANDARD.rowBalance (не из Enterprise) |
| `testCommandTopsUpRowBalanceOnReRun` | Запуск команды 1: `--rows=1000`. Запуск 2: `--rows=5000`. → RowBalance = 5000. Повторный запуск без `--rows` не обнуляет |
| `testGetActiveSubscriptionFallsBackToEnterpriseForEnterpriseOnly` | Только Enterprise → `GetActiveSubscription` возвращает Enterprise |
| `testGetRowsBalanceWorksForEnterpriseOnlyWithRowsOption` | Enterprise + `--rows=5000` + `--employee-email=100` → `GetRowsBalance` возвращает 5000/X/100/X |
| `testGetClientInfoReturnsPermissionDeniedWithoutEnterprise` | `PERMISSION_DENIED` |
| `testGetClientInfoReturnsUnauthenticatedWithoutAuth` | `UNAUTHENTICATED` |
| `testCreateTokenThenListThenRevoke` | Полный цикл токенов |

## Файлы к изменению

| Файл | Операция |
|---|---|
| [backend/src/Billing/Console/EnterpriseSubscriptionCreateCommand.php](backend/src/Billing/Console/EnterpriseSubscriptionCreateCommand.php) | Изменить: +4 опции, вызов `setSubscriptionAmounts` |
| [backend/src/Billing/Service/RowBalanceService.php](backend/src/Billing/Service/RowBalanceService.php) | Изменить: +метод `setSubscriptionAmounts` |
| [backend/src/Billing/Common/Repository/SubscriptionRepository.php](backend/src/Billing/Common/Repository/SubscriptionRepository.php) | Изменить: ORDER BY subscriptionType ASC, startDate DESC |
| [backend/src/Controller/V2/Grpc/Billing/BillingService.php](backend/src/Controller/V2/Grpc/Billing/BillingService.php) | Изменить: fallback в `GetActiveSubscription` |
| [backend/src/Controller/V2/Grpc/Account/UserProfileService.php](backend/src/Controller/V2/Grpc/Account/UserProfileService.php) | Изменить: fallback на Enterprise в профиле |
| [backend/src/Controller/V2/Rest/AccountMeController.php](backend/src/Controller/V2/Rest/AccountMeController.php) | Изменить: fallback на Enterprise в /me |
| [backend/tests/Billing/Console/EnterpriseSubscriptionCreateCommandTest.php](backend/tests/Billing/Console/EnterpriseSubscriptionCreateCommandTest.php) | Изменить: +6 тестов |
| [backend/tests/Service/Billing/EnterpriseApiClientServiceTest.php](backend/tests/Service/Billing/EnterpriseApiClientServiceTest.php) | Изменить: +7 тестов |
| `backend/tests/Service/Billing/RowBalanceServiceTest.php` | Создать: 4 теста |
| `backend/tests/Service/Billing/SubscriptionRepositoryTest.php` | Создать: 2 теста |
| `backend/tests/Api/EnterpriseApiToken1Test.php` | Создать: 8 сценариев |

## Stripe-безопасность (явно)

Правки №3 (ORDER BY), №4 (GetActiveSubscription fallback), +fallback в профиле:

- **Для STANDARD-only юзера**: поведение **100% идентично** текущему. Все пути возвращают STANDARD-подписку. Stripe webhooks продолжают создавать STANDARD, ничего не ломается.
- **Для Enterprise-only**: ранее был UI-облом (профиль показывал "нет подписки", export/Apollo падали). Теперь UI/export/Apollo работают через Enterprise.RowBalance (если его проинициализировать `--rows`/`--employee-*`).
- **Для STANDARD+ENTERPRISE**: UI-операции детерминированно списывают из STANDARD.rowBalance (приоритет в ORDER BY). API-операции через ENTERPRISE.api.clients (работают независимо через ApiTokenService). Stripe webhooks продолжают обновлять STANDARD, Enterprise ими не затрагивается.

Ни одна правка не требует изменений в Stripe EventHandlers, checkout session, StripeSubscriptionService, StripeInvoiceService. Все Stripe-потоки работают по-старому.

## Верификация

```bash
docker compose exec -it backend bash

# 1. Тесты (только затрагиваемые)
./vendor/bin/phpunit tests/Billing/Console/ --testdox
./vendor/bin/phpunit tests/Service/Billing/ --testdox
./vendor/bin/phpunit tests/Api/EnterpriseApiToken1Test.php --testdox

# 2. Smoke-проверка что Stripe-тесты не сломались
./vendor/bin/phpunit tests/Api/Billing1Test.php --testdox
./vendor/bin/phpunit tests/Api/Billing2Test.php --testdox
./vendor/bin/phpunit tests/Api/Billing3Test.php --testdox
./vendor/bin/phpunit tests/Api/Billing4Test.php --testdox
./vendor/bin/phpunit tests/Api/Billing5Test.php --testdox
./vendor/bin/phpunit tests/Api/Billing6Test.php --testdox

# 3. Style + PHPStan
PHP_CS_FIXER_IGNORE_ENV=1 ./vendor/bin/php-cs-fixer fix --diff \
  --config=.php-cs-fixer.php --using-cache=no \
  src/Billing/ src/Controller/V2/Grpc/Billing/BillingService.php \
  src/Controller/V2/Grpc/Account/UserProfileService.php \
  src/Controller/V2/Rest/AccountMeController.php tests/

vendor/bin/phpstan analyze src --memory-limit=512M

# 4. Smoke вручную по сценариям
# #2 (свежий user):
php bin/console billing:enterprise-subscription:create trial-expired@bcu.localhost \
  --credits=100000 --rows=50000 --employee-list=1000 --employee-email=500 --employee-phone=300

# #1 (с active STANDARD):
php bin/console billing:enterprise-subscription:create monthly-active@bcu.localhost \
  --credits=100000 --rows=50000

# #4 (повторный с обновлением):
php bin/console billing:enterprise-subscription:create trial-expired@bcu.localhost --rows=75000

# БД-аудит
docker compose exec -it postgres psql -U bringo -d bringo -c \
  "SELECT u.email,
          s.subscription_type_id,
          s.is_active,
          rb.amount_companies, rb.amount_pcs, rb.amount_officers, rb.init_rows_amount,
          rb.amount_employee_list_action, rb.amount_employee_email_action, rb.amount_employee_phone_action,
          c.credit_balance
   FROM billing.subscription s
   JOIN public.\"user\" u ON u.user_id = s.user_id
   LEFT JOIN billing.row_balance rb ON rb.subscription_id = s.subscription_id
   LEFT JOIN api.clients c ON c.website_user_id = u.user_id
   WHERE u.email IN ('trial-expired@bcu.localhost', 'monthly-active@bcu.localhost')
   ORDER BY u.email, s.subscription_type_id;"

# 5. Manual gRPC для обоих пользователей:
# https://nginx → войти → DevTools → проверить ApiTokenService/GetClientInfo,
# BillingService/GetActiveSubscription, GetRowsBalance
```

## Future Extensions — сохранить в память после аппрува

После выхода из plan mode создать файл `~/.claude/projects/-home-pavel-dev-www-bringo-bringo-co-uk-main/memory/project_enterprise_stripe_coexistence.md` и добавить ссылку в `MEMORY.md`. Содержание — ниже.

**Тема: Защита Stripe-потока от конфликта с Enterprise (отложено)**

Сейчас разрешена параллельная работа STANDARD (Stripe) + ENTERPRISE (админ-команда). Бизнес явно захотел это.

Если в будущем потребуется более жёсткая защита, варианты:

1. **Мягкая блокировка на gRPC** — в [BillingService::CreateSubscriptionCheckoutSession](backend/src/Controller/V2/Grpc/Billing/BillingService.php#L331-L334) + `GetOrCreateLastSubscriptionCheckoutSession` (строки 411-417): `if ($user->hasActiveEnterpriseSubscription()) throw ...`. Блокирует инициацию Stripe checkout из UI. Не защищает от прямых API Stripe вызовов.

2. **Жёсткая блокировка на webhook** — в [CheckoutSessionCompletedHandler.php:92](backend/src/Billing/Stripe/EventHandler/CheckoutSessionCompletedHandler.php#L92): `if ($user->hasActiveEnterpriseSubscription()) throw RuntimeException(...)`. Webhook failed → deadletter. Финансово рискованно: пользователь заплатил, а подписка не создалась.

3. **Полный фикс для prod** — 1 + 2 + при активации Enterprise автоматически отменять Stripe-подписку через Stripe SDK (refund / proration / cancel-at-period-end — зависит от бизнес-решения).

Также отложено:
- Новый gRPC-метод `GetAllActiveSubscriptions` для фронта (если UI захочет показывать обе подписки одновременно).
- Partial unique index `billing.subscription (user_id) WHERE is_active=true AND subscription_type_id=X` — требует аудита исторических дубликатов.

План реализации: `/home/pavel/.claude/plans/playful-giggling-map.md` (после старта работ перенести в `.claude/sessions/plans/` по правилам session-log).

## Итог

- Команда работает для всех 4 сценариев подписок (STANDARD-only, Enterprise-only, оба, повторный запуск).
- Enterprise-юзер получает полноценный UI-доступ (Export rows, Apollo list/email/phone) через 4 опции команды.
- Все 9 счётчиков RowBalance + init-значения заполняются корректно.
- STANDARD + ENTERPRISE сосуществуют: UI-списания идут из STANDARD, API-списания из Enterprise.api.clients.
- Enterprise-only юзер в UI видит свою подписку как активную (fallback в `GetActiveSubscription` и профиле).
- Вся Stripe-логика работает идентично текущей — ни один handler/checkout/transition не меняется.
- Покрытие тестами: 6+7+4+2+8 = 27 новых тестов на все ветки.
- Future Extensions (Stripe защита, GetAllActiveSubscriptions, DB-constraint) сохраняются в memory на будущее.
