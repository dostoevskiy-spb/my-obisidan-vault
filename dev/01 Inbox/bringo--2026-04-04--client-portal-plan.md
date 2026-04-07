---
type: session-plan
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/plans/2026-04-04_01-24_client-portal-plan.md
session_date: 2026-04-04
tags: [session-plan, bringo]
created: 2026-04-07
---

# План: Клиентский портал API

**Проект:** [[Bringo]]
**Дата:** 2026-04-04

## Цель
Спроектировать клиентский портал для REST API: роли, invite-система, личный кабинет, логи запросов, финансовые данные.

## Содержание плана
- **Фаза 1:** Модель ClientUser + аутентификация — миграция таблицы `client_users`, Laravel guard для клиентского портала
- **Фаза 2:** Клиентский портал (Filament) — dashboard, управление API-токенами, отдельная панель `/client`
- **Фаза 3:** Invite-система — создание клиентов админом с invite-email, принятие приглашения, установка пароля
- **Фаза 4:** Импорт пользователей из legacy-таблицы `public.user` (Symfony backend) с autocomplete
- **Фаза 5:** Логи API-запросов из ClickHouse — просмотр и фильтрация для клиентов и админов
- **Фаза 6:** Новый эндпоинт финансовых данных с иерархической структурой (tabs → rows → children → values)
- Архитектура: Laravel 13 + Filament 5, multi-user на один ApiClient, SMTP email (Mailcatcher на локалке)
- Тесты пишутся после каждой фазы, не откладываются до конца

## Связи
- [[Bringo]]
