Собери метаданные Claude Code из всех проектов и обнови аналитику в vault.

## Что делать

### 1. Сканировать проекты
Найди все директории `.claude/` в `~/dev/www/` (maxdepth 6).

### 2. Для каждого проекта собрать

- **Skills:** имена и описания из `.claude/skills/*/SKILL.md` (первая строка description)
- **Commands:** имена и первая строка из `.claude/commands/*.md`
- **Agents:** имена из `.claude/agents/`
- **MCP серверы:** из `settings.json`, `settings.local.json`, `config.json`
- **Плагины:** из `settings.json` (enabledPlugins)
- **MEMORY.md:** ключевые выводы (если файл существует)
- **Разрешения:** из settings.json (allowedTools)

### 3. Создать/обновить claude-config.md

Для каждого проекта создай или обнови `10 Projects/{Project}/claude-config.md`:

```yaml
---
type: claude-config
project: {project}
tags: [claude-config, {project}]
updated: YYYY-MM-DD
---
```

Содержимое: Skills, Commands, Agents, MCP серверы, Плагины, MEMORY выводы, Субмодули с их конфигами.

### 4. Обновить Claude Code Analytics

Обнови `00 HUB/Claude Code Analytics.md`:
- Сводная таблица: проект → skills → commands → MCP серверы
- Пересекающиеся skills между проектами
- Общие MCP серверы
- Дата последнего обновления

### 5. Итог
Покажи что обновлено и какие изменения обнаружены с прошлого запуска.
