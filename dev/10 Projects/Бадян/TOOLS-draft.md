---
type: project
tags: [openclaw, config]
created: 2026-04-06
---

# TOOLS.md — черновик

> Деплоится в `~/.openclaw/workspace/TOOLS.md`

```markdown
# Tools

## Obsidian CLI (primary interface to vault)
- obsidian-cli search <query> — поиск по заголовкам
- obsidian-cli search-content <query> — полнотекстовый поиск
- obsidian-cli create <path> — создать заметку
- obsidian-cli move <from> <to> — переместить (обновит ссылки)
- obsidian-cli delete <path> — удалить заметку
- obsidian-cli daily — открыть/создать daily note

## Vault Structure
- 00 HUB/ — навигация, Dashboard, MOC
- 01 Inbox/ — входящее
- 10 Projects/ — активные проекты (status: active/on-hold/completed/cancelled)
- 20 Areas/ — зоны ответственности (Программирование, DevOps, Карьера, Здоровье, Финансы, Обучение)
- 30 Resources/ — справочник (Книги, Статьи, Курсы, Сниппеты, Инструменты)
- 40 Archive/ — завершённое
- 50 Zettelkasten/ — атомарные идеи
- 60 Kill-List/ — фокус (today/this-week/someday)
- 70 Alerts/ — дедлайны и предупреждения
- Daily/ — ежедневные заметки (YYYY-MM-DD.md)
- Weekly/ — еженедельные обзоры
- Templates/ — шаблоны Templater
- Files/ — вложения

## Frontmatter Types
project, area, resource, zettel, literature, daily, weekly, moc, kill-list, triggers

## Notes
- Vault path: configured via obsidian-cli set-default
- All notes are markdown with YAML frontmatter
- Links format: wiki-links [[]]
```
