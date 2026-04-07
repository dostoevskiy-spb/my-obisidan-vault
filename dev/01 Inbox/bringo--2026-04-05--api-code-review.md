---
type: session-log
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-05_13-03_api-code-review.md
session_date: 2026-04-05
tags: [session-log, bringo]
created: 2026-04-07
---

# Code Review модуля API

**Проект:** [[Bringo]]
**Дата:** 2026-04-05

## Цель
Глубокое ревью модуля api/ (Laravel 13, 192 PHP файла) — security, performance, DB safety, code quality.

## Результаты
- Проведено параллельное ревью 6 агентами (security, performance, db-safety, code-quality, infra, billing) с кросс-ревью между ними
- Найдена **21 уязвимость/проблема**: 4 CRITICAL, 6 HIGH, 7 MEDIUM, 4 LOW
- CRITICAL: Contact Reveal IDOR — любой клиент может читать контакты других клиентов
- CRITICAL: ClickHouse SQL injection через `addslashes` (недостаточная защита)
- CRITICAL: ConcurrencyLimiter state leak в Octane (утечка состояния между запросами)
- CRITICAL: Sandbox bypass для contacts endpoint
- Оба PG-соединения используют один DB user — защита read-only реализована только на уровне приложения, а не базы данных

## Связи
- [[Bringo]]
