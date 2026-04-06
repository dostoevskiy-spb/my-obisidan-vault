---
name: vault-daily
description: Create or update daily notes in the Obsidian vault
triggers:
  - user asks about today's tasks or plan
  - user asks to create a daily note
  - user says "today", "сегодня", "дневник"
---

# vault-daily

Управление ежедневными заметками.

## Workflow

1. Check if `Daily/YYYY-MM-DD.md` exists for today
2. If not — create from template:

```yaml
---
type: daily
date: YYYY-MM-DD
tags: [daily]
---
```

3. Read `60 Kill-List/today.md` — show focus tasks
4. Check tasks due today across vault
5. Show brief status to user

## Template Structure

```markdown
# Day, DD Month YYYY

## Фокус дня
- (from Kill-List/today.md)

## Задачи
(tasks due today from vault)

## Заметки
-

## Что узнал
-

---
[[YYYY-MM-DD-1]] | [[YYYY-MM-DD+1]]
```

## Rules
- Daily notes go in `Daily/` folder
- Filename format: `YYYY-MM-DD.md`
- Always link to previous/next day
- Show Kill-List focus at the top
