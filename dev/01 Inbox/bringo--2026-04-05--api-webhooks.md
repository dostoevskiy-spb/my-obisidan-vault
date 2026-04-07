---
type: session-log
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-05_00-52_api-webhooks.md
session_date: 2026-04-05
tags: [session-log, bringo]
created: 2026-04-07
---

# API Webhooks реализация

**Проект:** [[Bringo]]
**Дата:** 2026-04-05

## Цель
Реализовать полную webhook-систему для Public API — от приема событий до доставки и мониторинга.

## Результаты
- Реализована полная webhook-система: backend отправляет EntityUpdatedEvent (Protobuf), relay через Redis в API, доставка подписчикам с HMAC-подписью
- 9 API-эндпоинтов для управления подписками (CRUD + тестирование), full payload при доставке
- Биллинг: каждый webhook delivery списывает кредиты, кеш подписок в Redis для производительности
- DispatchWebhookJob с автоматическим retry и логированием request/response body в ClickHouse
- Laravel Horizon подключен вместо ручного queue:work для управления воркерами
- Filament UI: управление подписками на странице клиента, просмотр delivery logs с возможностью retry из админки
- Backend: новый Symfony MessageHandler + consumer для relay событий в API
- 16 feature-тестов, общий suite: 176 тестов, 763 assertions — все зеленые

## Связи
- [[Bringo]]
