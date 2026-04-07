---
type: moc
tags: [hub, claude-code, analytics]
updated: 2026-04-07
---

# Claude Code Analytics

Аналитика использования Claude Code по проектам. Обновляется через `/collect-metadata`.

## Проекты

```dataview
TABLE
  length(file.inlinks) AS "Ссылки"
FROM "10 Projects"
WHERE type = "claude-config"
SORT project ASC
```

## Сессии по проектам

```dataview
TABLE length(rows) AS "Сессий", min(rows.session_date) AS "С", max(rows.session_date) AS "По"
FROM "10 Projects"
WHERE type = "session-log"
GROUP BY project
```

## ADR по проектам

```dataview
LIST
FROM "10 Projects"
WHERE type = "adr"
SORT file.mtime DESC
```
