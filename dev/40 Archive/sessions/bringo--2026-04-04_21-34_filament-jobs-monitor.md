---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-04_21-34_filament-jobs-monitor.md
session_date: 2026-04-04
tags: [session-log, raw, bringo]
created: 2026-04-07
status: processed
---

# Сессия: Подключение filament-jobs-monitor

**Дата:** 2026-04-04 21:34
**Цель:** Подключить пакет ultraviolettes/filament-jobs-monitor в субмодуле api и добавить в боковое меню

---

## Лог

### 21:34 — Начало: анализ текущего состояния
- Задача: подключить filament-jobs-monitor в api субмодуле
- Контекст: пакет `croustibat/filament-jobs-monitor` v4.3 уже в composer.json, в composer.lock тянется из ultraviolettes fork. Плагин закомментирован в AdminPanelProvider с пометкой "incompatible with Filament 5 (resolve() returns object, not class string)"
- Детали: конфиг ссылается на несуществующий `App\Filament\Resources\QueueMonitorResource`, миграция уже опубликована но создаёт таблицу в `public` схеме

### 21:37 — Исправление миграции
- Что: переписал миграцию `2026_04_03_124255_create_filament-jobs-monitor_table.php` — заменил `Schema::create('queue_monitors')` на `DB::unprepared('CREATE TABLE api.queue_monitors ...')` по паттерну остальных миграций проекта
- Результат: успех
- Файлы: `api/database/migrations/2026_04_03_124255_create_filament-jobs-monitor_table.php`

### 21:38 — Создание кастомного QueueMonitorResource
- Что: создал `App\Filament\Resources\QueueMonitorResource`, наследует вендорный ресурс, переопределяет `getModel()` — возвращает `QueueMonitor::class` (строку) вместо `resolve(QueueMonitor::class)` (объект)
- Результат: успех
- Файлы: `api/app/Filament/Resources/QueueMonitorResource.php`

### 21:39 — Обновление конфига и AdminPanelProvider
- Что: в `config/filament-jobs-monitor.php` установил `connection => 'api'`, `navigation_sort => 90`, указал кастомный ресурс. В `AdminPanelProvider` раскомментировал `FilamentJobsMonitorPlugin::make()`
- Результат: успех
- Файлы: `api/config/filament-jobs-monitor.php`, `api/app/Providers/Filament/AdminPanelProvider.php`

### 21:40 — Перенос таблицы и проверка
- Что: таблица `queue_monitors` уже была в `public` схеме от предыдущей миграции. Перенёс через `ALTER TABLE public.queue_monitors SET SCHEMA api`. Проверил через tinker: model, connection, navigation — всё корректно
- Результат: успех
- Детали: `getModel()` возвращает строку, connection = api, маршрут `admin/queue-monitors` зарегистрирован, count = 0 (пустая таблица)

---

## Итоги
- **Выполнено:** filament-jobs-monitor подключён и работает в Filament 5 админке
- **Изменённые файлы:**
  - `api/app/Filament/Resources/QueueMonitorResource.php` (создан)
  - `api/app/Providers/Filament/AdminPanelProvider.php` (раскомментирован плагин)
  - `api/config/filament-jobs-monitor.php` (connection=api, navigation_sort=90)
  - `api/database/migrations/2026_04_03_124255_create_filament-jobs-monitor_table.php` (api схема)
