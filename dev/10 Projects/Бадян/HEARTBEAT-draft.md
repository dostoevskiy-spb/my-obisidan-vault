---
type: project
tags: [openclaw, config]
created: 2026-04-06
---

# HEARTBEAT.md — черновик

> Деплоится в `~/.openclaw/workspace/HEARTBEAT.md`

```markdown
# Heartbeat

## Every 30 minutes
- [ ] Check for overdue tasks (due < today) via obsidian-cli search-content → if found, note in memory
- [ ] Check Kill-List/today.md count → if > 5 tasks, flag

## Daily (08:00)
- [ ] Create daily note if missing
- [ ] Scan 01 Inbox/ → if > 10 notes, send reminder

## Weekly (Monday 09:00)
- [ ] Create weekly review note
- [ ] Summarize completed tasks from past week
- [ ] Check project deadlines approaching this week

## If nothing needs attention
Reply: HEARTBEAT_OK
```
