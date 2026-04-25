# Project Memory

## Billing Architecture
- Подробное исследование и план: see [billing-manual-subscriptions.md](billing-manual-subscriptions.md)
- Ключевые файлы биллинга: `src/Billing/` (Entity, Service, Stripe, Console, Enum)
- Проверка премиума: `User::hasActiveSubscription()` → `Subscription::isActive()`
- Voter: `UserSubscriptionVoter` (`has_active_subscription`)
- `PaymentSystemEnum` сейчас только `STRIPE = 1`, планируется `MANUAL = 2`
- `PaymentSystemInterface` + `BillingScheduler` — уже есть абстракция для множества платёжных систем
- Промокоды были (`PromoCodeEnum`), но отключены с throw в `BillingService`

## Key Services
- `MagicLinkService` — одноразовые ссылки для входа (Redis, TTL)
- `SubscriptionNotifier` — email уведомления о подписках
- `RowBalanceService` — лимиты на экспорт строк
- `AccountService::SignUp()` — регистрация пользователей

## Email
- Symfony Mailer + Twig templates (`templates/email/`)
- Base template: `email/base-new.html.twig`
- Отправители: `noreply@bringo.co.uk` (welcome), `bcu@bringo.co.uk` (default)
