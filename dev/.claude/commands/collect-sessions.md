Сбор сырых логов сессий Claude Code из проектов в Obsidian vault.
Эта команда выполняется ЛОКАЛЬНО — на машине где лежат проекты.
Обработка (digest) выполняется отдельно на сервере через /digest.

## Что делать

### 1. Найти проекты с сессиями
Рекурсивно просканируй `/home/pavel/dev/www/` (maxdepth 6) — найди все директории `.claude/sessions/` содержащие `.md` файлы.

### 2. Для каждого проекта

**Определи имя проекта** из пути (например `bringo`, `omnicom-crm-v2`).

**Прочитай SESSION_INDEX.md** (если есть) и обработай каждую строку:

#### Новые записи (нет `[imported:...]`)
1. Прочитай файл сессии
2. Найди последний `### HH:MM` в `## Лог` — это last-log
3. Создай заметку в `01 Inbox/sessions/raw/` с именем `{project}--{filename}`:
   - Добавь YAML frontmatter: type: session-log-raw, project, source (полный путь), session_date, tags, created, status: unprocessed
   - Скопируй полное содержимое файла после frontmatter
4. Пометь строку в SESSION_INDEX.md: добавь ` [imported:YYYY-MM-DD last-log:HH:MM]`

#### Обновлённые записи (есть `[imported:...]`)
1. Извлеки `last-log:HH:MM` из метки
2. Прочитай файл, найди последний `### HH:MM`
3. Если last-log в файле отличается от метки — ре-импортируй:
   - Перезапиши raw-файл (то же имя → нет дубля)
   - Установи status: unprocessed
   - Обнови метку в SESSION_INDEX.md

#### Осиротевшие файлы
Проверь `.md` файлы в директории, которых НЕТ в SESSION_INDEX.md (кроме самого SESSION_INDEX.md). Импортируй их и добавь в индекс.

### 3. Планы
Аналогично проверь `.claude/sessions/plans/` и `.claude/plans/` — файлы без соответствующего raw-файла в vault импортируй как type: session-plan-raw.

### 4. Сохрани изменения SESSION_INDEX.md
Закоммить изменённый SESSION_INDEX.md в git-репозиторий проекта.

### 5. Git push vault
Выполни в директории vault:
```
git add "01 Inbox/sessions/raw/"
git commit -m "collect-sessions: N imported, M updated"
git push origin main
```

### 6. Итоговый отчёт
Покажи:
- Сколько сессий найдено / импортировано / обновлено / пропущено
- Какие проекты затронуты

## Правила
- НЕ создавать саммари — это делает /digest на сервере
- НЕ перемещать файлы в Archive — это делает /digest
- Язык заметок — русский
- Никогда не создавать дубли (детерминистические имена файлов)
- Не трогать файлы в проектах кроме SESSION_INDEX.md
