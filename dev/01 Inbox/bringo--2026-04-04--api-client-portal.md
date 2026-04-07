---
type: session-log
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-04_00-56_api-client-portal.md
session_date: 2026-04-04
tags: [session-log, bringo]
created: 2026-04-07
---

# Клиентский портал API — роли, invite, ЛК, логи, финансы

**Проект:** [[Bringo]]
**Дата:** 2026-04-04

## Цель
Спроектировать и реализовать систему ролей, клиентский ЛК, логирование запросов и финансовый эндпоинт для api/ субмодуля (Laravel 13 + Filament 5).

## Результаты
- Полностью реализован клиентский портал (`/client`) с dashboard и виджетами — отдельная Filament-панель для API-клиентов
- Создан invite flow: InviteService отправляет email-приглашение, клиент принимает и устанавливает пароль (один ClientUser на одного ApiClient)
- Импорт legacy-пользователей из основного backend с autocomplete — пароли не копируются, всегда через invite
- Логирование API-запросов через ClickHouse: RequestLogResource доступен в обеих панелях (admin и client)
- Новый эндпоинт финансовых данных с иерархической структурой (180+ показателей), аналогичной backend
- Исправлены несовместимости с Filament 5: `$view`, `$layout`, `$navigationIcon` стали non-static
- Итого: 35 файлов создано, 8 изменено, 148 тестов (679 assertions) проходят

## Связи
- [[Bringo]]
