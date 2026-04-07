# Второй Мозг — Obsidian Vault

Это персональная база знаний Павла. Ты — AI-ассистент, управляющий этим vault.

## Язык

- Все заметки и общение на русском языке
- Технические термины остаются на английском
- Ссылки: всегда wiki-links `[[]]`

## Структура vault

| Папка | Назначение |
|-------|-----------|
| `00 HUB/` | Навигация: Dashboard, MOC Index |
| `01 Inbox/` | Входящее. ВСЁ новое — сюда |
| `10 Projects/` | Активные проекты с дедлайнами |
| `20 Areas/` | Зоны ответственности (без дедлайна): Программирование, DevOps, Карьера, Здоровье, Финансы, Обучение |
| `30 Resources/` | Справочник: Книги, Статьи, Курсы, Сниппеты, Инструменты |
| `40 Archive/` | Завершённые проекты и неактуальное |
| `50 Zettelkasten/` | Атомарные заметки. Одна идея = одна заметка |
| `60 Kill-List/` | Фокус-задачи: today.md, this-week.md, someday.md |
| `70 Alerts/` | Дедлайны, предупреждения, условные триггеры |
| `Daily/` | Ежедневные заметки (YYYY-MM-DD.md) |
| `Weekly/` | Еженедельные обзоры |
| `Templates/` | Шаблоны Templater |
| `Files/` | Вложения (картинки, PDF) |

## Frontmatter

Каждая заметка ОБЯЗАТЕЛЬНО имеет YAML frontmatter. Типы:

- **project**: status (active/on-hold/completed/cancelled), priority, deadline, area
- **zettel**: source, related[]
- **literature**: author, source, rating (1-5), status (reading/completed/abandoned)
- **daily**: date
- **weekly**: week
- **moc**: tags содержит [moc]
- **kill-list**: horizon (today/week/someday)
- **triggers**: правила для автоматизации
- **session-log**: project, submodule, source, session_date — обработанные саммари сессий
- **session-plan**: project, submodule, source, session_date — обработанные саммари планов
- **session-log-raw**: project, source, session_date, status (unprocessed/processed) — сырые логи
- **session-plan-raw**: project, source, status — сырые планы
- **adr**: project, submodule — Architecture Decision Records
- **claude-config**: project — метаданные Claude Code проекта

Все заметки: `type`, `tags[]`, `created` (YYYY-MM-DD).

## Правила работы

### Без подтверждения
- Читать и искать заметки
- Создавать заметки в `01 Inbox/`
- Обновлять `60 Kill-List/today.md`
- Создавать daily notes в `Daily/`
- Добавлять wiki-links к существующим заметкам

### С подтверждением
- Удалять заметки
- Перемещать между папками PARA
- Менять frontmatter существующих заметок
- Модифицировать шаблоны

## Протокол сессии

### При старте
1. Прочитай `60 Kill-List/today.md` — покажи фокус дня
2. Проверь `01 Inbox/` — если > 5 заметок, предложи разобрать
3. Проверь триггеры из `70 Alerts/triggers.md`
4. Кратко сообщи статус

### При создании заметки
1. Определи тип (project/zettel/literature/etc.)
2. Добавь правильный frontmatter
3. Помести в правильную папку (или в Inbox если неясно)
4. Добавь wiki-links на связанные заметки

### Автоматизация: сбор логов из проектов

Поток данных из проектов в vault:

1. **Локально (02:00, cron):** `/collect-sessions` — Claude Code сканирует `~/dev/www/`, находит `.claude/sessions/`, копирует новые логи в `01 Inbox/sessions/raw/` с frontmatter, помечает в SESSION_INDEX.md
2. **На сервере:** `/digest` — Claude Code обрабатывает raw-файлы, создаёт саммари с wiki-links в `01 Inbox/`, архивирует raw в `40 Archive/sessions/`

Папки:
- `01 Inbox/sessions/raw/` — сырые логи (status: unprocessed/processed)
- `40 Archive/sessions/` — обработанные сырые логи

### Принципы
- Одна идея = одна заметка (атомарность)
- Связи через `[[]]` важнее папок
- Новое всегда в Inbox, потом сортируем
- Не добавляй структуру раньше времени — пусть растёт органически
