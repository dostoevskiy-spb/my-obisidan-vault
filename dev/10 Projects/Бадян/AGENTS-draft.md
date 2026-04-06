---
type: project
tags: [openclaw, config]
created: 2026-04-06
---

# AGENTS.md — черновик

> Деплоится в `~/.openclaw/workspace/AGENTS.md`

```markdown
# Agents

## Every Session Start
1. Read Kill-List/today.md via obsidian-cli
2. Check 01 Inbox/ — if > 5 notes, suggest sorting
3. Check 70 Alerts/triggers.md — run condition checks
4. Brief user on status

## Task Workflows

### New Note
1. Determine type (project/zettel/literature/etc.)
2. Add correct YAML frontmatter
3. Create in correct folder (or Inbox if unclear)
4. Add wiki-links to related notes

### Sort Note (from Inbox)
1. Read note content
2. Determine correct PARA folder
3. Move via obsidian-cli (updates links)
4. Add wiki-links to related notes

### Daily Review
1. Update Kill-List/today.md
2. Check deadlines approaching
3. Create daily note if missing

### Weekly Review
1. Create Weekly/ note
2. Summarize completed/pending tasks
3. Update Kill-List/this-week.md

## Memory Rules
- Log key decisions to MEMORY.md
- Daily observations to memory/YYYY-MM-DD.md
- Never produce "mental notes" — only files persist between sessions

## Permissions
- WITHOUT asking: read, search, organize, create in Inbox, update Kill-List
- WITH confirmation: delete, move between PARA folders, modify frontmatter
- PROACTIVE: update MEMORY.md, suggest connections, flag overdue items

## Red Lines
- Never export vault data outside the system
- Never run destructive commands
- Never modify .obsidian/ configuration
```
