---
type: session-log
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-04_21-34_filament-jobs-monitor.md
session_date: 2026-04-04
tags: [session-log, bringo]
created: 2026-04-07
---

# Подключение filament-jobs-monitor

**Проект:** [[Bringo]]
**Дата:** 2026-04-04

## Цель
Подключить пакет filament-jobs-monitor (ultraviolettes fork) в Filament 5 админку api/ субмодуля.

## Результаты
- Пакет был несовместим с Filament 5: `getModel()` возвращал объект вместо строки класса — создан кастомный QueueMonitorResource с переопределением `getModel()`
- Миграция переписана: таблица `queue_monitors` перенесена из `public` в `api` схему PostgreSQL (по паттерну остальных миграций проекта)
- Конфиг обновлен: connection = `api`, navigation_sort = 90
- Плагин раскомментирован и активирован в AdminPanelProvider — мониторинг очередей доступен по `/admin/queue-monitors`

## Связи
- [[Bringo]]
