# Задача: Бесплатные подписки и промокоды (без Stripe)

## Статус: ПЛАНИРОВАНИЕ (план обновлён по итогам встречи с заказчиком)

## Файлы
- План: `/home/pavel/.claude/plans/atomic-whistling-hoare.md`
- Диаграмма: `docs/manual-subscriptions.mmd`

## Ключевые решения заказчика
- Подписка = эквивалент monthly (лимиты, строки, контакты)
- Пользователь регистрируется САМ (GDPR, пароль, согласие)
- Stripe НЕ участвует в промокодах
- Нет авто-продления (карту не берём)
- Экспорт сверх лимитов — платно (стандартный Stripe flow)
- После окончания → isTrialUsed = true (стандартный trial закрыт)
- Можно выдать повторно одному пользователю
- 2 письма: активация + окончание/отмена
- Пользователь может отменить досрочно

## Архитектура
- PaymentSystemEnum::MANUAL = 2 (миграция НЕ нужна)
- ManualPaymentSystemService implements PaymentSystemInterface
- PromoCode entity в billing.promo_code (code, duration, max_uses, valid_until)
- PromoCodeService: validate() + activate()
- gRPC: ActivatePromoCode в BillingService
- Console: grant/revoke-subscription, create/list/deactivate-promo-code

## Что УБРАЛИ из первоначального плана
- Создание пользователей через CLI (пользователь регается сам)
- Magic link / invite email для новых пользователей
- STRIPE_DISCOUNT промокоды (минуем Stripe полностью)
- PromoCodeTypeEnum (один тип — FREE)
- Авто-продление
- Сложную логику уведомлений
