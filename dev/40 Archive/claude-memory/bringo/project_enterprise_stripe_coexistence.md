---
name: Enterprise + STANDARD coexistence — отложенные защиты Stripe
description: Бизнес разрешил параллельное существование ENTERPRISE (админ-команда) и STANDARD (Stripe). Варианты блокировок сохранены на будущее.
type: project
originSessionId: e1815658-4bb4-4080-86fe-5e98e11aec11
---
**Контекст:** команда `billing:enterprise-subscription:create` допускает создание Enterprise-подписки для юзера с уже активной Stripe STANDARD-подпиской. Обе живут параллельно: UI (Export/Apollo) берёт лимиты из STANDARD.RowBalance, API через токены — из Enterprise.api.clients. См. сессию `.claude/sessions/2026-04-13_23-54_enterprise-parallel-standard.md` и план `.claude/sessions/plans/2026-04-13_23-54_enterprise-parallel-standard.md`.

**Why:** бизнес явно потребовал параллельную работу. Stripe-поток не должен ломаться. Ужесточать блокировки — когда появится бизнес-правило.

**How to apply:** если пользователь спросит про защиту от конфликта Stripe×Enterprise, блокировку Stripe checkout для Enterprise-юзера, или автоматический refund при активации Enterprise — использовать один из вариантов ниже.

### Отложенные варианты защиты

1. **Мягкая блокировка на gRPC** — `backend/src/Controller/V2/Grpc/Billing/BillingService.php` методы `CreateSubscriptionCheckoutSession` (строки 331-334) и `GetOrCreateLastSubscriptionCheckoutSession` (строки 411-417): добавить `if ($user->hasActiveEnterpriseSubscription()) throw ...`. Блокирует инициацию Stripe checkout из UI. Не защищает от прямых API Stripe вызовов.

2. **Жёсткая блокировка на webhook** — `backend/src/Billing/Stripe/EventHandler/CheckoutSessionCompletedHandler.php` строка 92: `if ($user->hasActiveEnterpriseSubscription()) throw new RuntimeException(...)`. Webhook падает → deadletter. Финансово рискованно: пользователь оплатил, подписка в БД не создалась.

3. **Полный prod-фикс** — 1 + 2 + при активации Enterprise автоматически отменять Stripe-подписку (`billing:enterprise-subscription:create` → Stripe SDK cancel/proration/refund по бизнес-решению).

### Также отложено

- Новый gRPC-метод `GetAllActiveSubscriptions` — если фронт захочет показывать обе подписки одновременно. Сейчас `BillingService::GetActiveSubscription` возвращает STANDARD с fallback на ENTERPRISE.
- Partial unique index `billing.subscription (user_id) WHERE is_active=true AND subscription_type_id=X` — требует предварительного аудита исторических дубликатов.

### Что уже в коде (апрель 2026)

- `SubscriptionRepository::getForUserId` возвращает STANDARD при конфликте STANDARD+ENTERPRISE (ORDER BY subscriptionType ASC). Import/Apollo спишут из STANDARD.
- `GetActiveSubscription`, `UserProfileService::GetProfile`, `AccountMeController` → fallback на Enterprise когда нет STANDARD (Enterprise-only юзер видит подписку активной).
- Команда `billing:enterprise-subscription:create` принимает `--credits` (API), `--rows` (companies/pcs/officers), `--employee-list`/`--employee-email`/`--employee-phone` (Apollo).
