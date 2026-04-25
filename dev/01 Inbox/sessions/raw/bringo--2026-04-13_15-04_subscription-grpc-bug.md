---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-13_15-04_subscription-grpc-bug.md
session_date: 2026-04-13
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [backend] Баг с отсутствующим subscription в gRPC ответах
**Дата:** 2026-04-13 15:04
**Субмодуль:** backend
**Цель:** Найти и исправить причину отсутствия объекта subscription в ответах UserProfileService.GetFull и BillingService.GetActiveSubscription

---

## Лог

### 15:04 — Начало
- Задача: проанализировать почему перестал приходить subscription в gRPC ответах
- Контекст: пользователь сообщил о двух связанных багах на бекенде, нужен анализ + план исправления
- Режим: Plan Mode — только анализ, без правок

### 15:06 — Корректировка подхода
- Первый Explore-агент выдал галлюцинацию про коммит 957b2fab с фейковым diff-ом — пользователь это пресёк
- Решение пользователя: не копаться в git history, искать причину в текущем коде
- Переключаюсь на чтение реальных файлов

### 15:08 — Уточнение от пользователя
- Баг проявляется только когда у пользователя ENTERPRISE подписка
- Это резко сужает зону поиска

### 15:10 — Найдена root cause
- Что: проанализированы Subscription entity, SubscriptionService, transformer, миграции, enum'ы
- Результат: классическая рассинхронизация enum'а с БД
- Детали:
  - Миграция [1775733130_data_add_unlimited_subscription_period.php](../../migration/migrations/db/1775733130_data_add_unlimited_subscription_period.php) добавила в `billing.subscription_period` запись `(3, 'Unlimited')` — этот период используется для Enterprise подписок
  - proto [Subscription.proto:12](../../shared-models/proto/Api/V2/Model/Billing/Subscription.proto#L12) уже имеет `UNLIMITED = 3`
  - Но в [backend/src/Billing/Enum/SubscriptionPeriodEnum.php](../../backend/src/Billing/Enum/SubscriptionPeriodEnum.php) есть только MONTHLY=0, ANNUALLY=1, DAILY=2 — UNLIMITED отсутствует
  - [Subscription entity:42-43](../../backend/src/Billing/Entity/Subscription.php#L42-L43) маппит `period_id` в `enumType: SubscriptionPeriodEnum::class`
  - Когда `SubscriptionService::getActiveSubscription()` ([SubscriptionService.php:150-160](../../backend/src/Billing/Service/SubscriptionService.php#L150-L160)) делает `findOneBy` для Enterprise юзера, Doctrine hydrate'ит Subscription с `period_id=3` и вызывает `SubscriptionPeriodEnum::from(3)` → `\ValueError`
  - Exception всплывает из обоих gRPC-методов — поэтому subscription "не приходит"
- Также есть смежная проблема (не блокер): в Subscription.proto есть `subscription_type = 12`, в БД появилась колонка `subscription_type_id`, но в Doctrine entity нет соответствующего поля, и transformer не выставляет это в proto. Сейчас это безвредно (Doctrine игнорирует неизвестные колонки), но надо доделать отдельно

### 15:11 — План утверждён
- План: [lucky-swimming-mochi.md](plans/2026-04-13_15-11_subscription-unlimited-fix.md)
- Краткое содержание: добавить case `UNLIMITED = 3` в `SubscriptionPeriodEnum`, добавить кейс в `getTitle()`. Один файл — один фикс.

### 15:23 — Имплементация
- Что: добавлен `case UNLIMITED = 3` в `SubscriptionPeriodEnum` + кейс в `getTitle()`
- PHPStan показал, что `Subscription::__construct()` имеет `match($period)` без default — добавил `throw new LogicException` для UNLIMITED (Enterprise подписки создаются не через этот конструктор)
- Файлы: backend/src/Billing/Enum/SubscriptionPeriodEnum.php, backend/src/Billing/Entity/Subscription.php
- csfix + phpstan по затронутым файлам — чисто
- Скопировать утверждённый план в .claude/sessions/plans

---

## Итоги
- **Выполнено:** добавлен case `UNLIMITED = 3` в `SubscriptionPeriodEnum`, обработан match в `Subscription::__construct` через explicit LogicException
- **Не завершено:** не сделана поддержка proto-поля `subscription_type` (отдельная задача — фронт пока не может отличать Standard от Enterprise через GetActiveSubscription/GetFull)
- **Планы:** [lucky-swimming-mochi.md](plans/2026-04-13_15-11_subscription-unlimited-fix.md)
- **В память:** baгy-механизм "новое значение в БД → старый PHP enum → ValueError при Doctrine hydrate" — типичная грабля при добавлении enum значений

## Реализация

### Изменённые файлы
- `backend/src/Billing/Enum/SubscriptionPeriodEnum.php`:
  - Добавлен `case UNLIMITED = 3`
  - Добавлен кейс в `getTitle()`: `'Unlimited Subscription'`
- `backend/src/Billing/Entity/Subscription.php`:
  - В `__construct()` `match($period)` для вычисления `endDate` добавлен кейс `UNLIMITED => throw new LogicException(...)` (защитно, т.к. Enterprise подписки не должны создаваться через этот конструктор)
  - Добавлен `use LogicException` (csfix нормализовал `\LogicException`)

### Не изменено (оставлено для отдельной задачи)
- `RowBalanceService` — match'ы по периоду без UNLIMITED (Enterprise не использует RowBalance логику)
- `SubscriptionPriceService` — таблица цен (Enterprise — кастомные цены вне Stripe)
- `SubscriptionNotifier` — email-нотификации (для Enterprise свои каналы)
- `BillingProtobufTransformer` — не выставляет `subscription_type` в proto (отдельная задача)
