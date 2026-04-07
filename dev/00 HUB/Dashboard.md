---
type: moc
tags: [hub]
---

# Второй Мозг

## Активные проекты

```dataview
TABLE status, priority, deadline
FROM "10 Projects"
WHERE type = "project" AND status = "active"
SORT priority ASC
```

## Задачи на сегодня

```tasks
not done
(due today) OR (scheduled today)
sort by priority
```

## Inbox (не разобрано)

```dataview
LIST
FROM "01 Inbox"
SORT file.ctime DESC
```

## Недавние заметки

```dataview
TABLE type, tags
SORT file.mtime DESC
LIMIT 10
```

## Недавние сессии разработки

```dataview
TABLE project, session_date
FROM "01 Inbox"
WHERE type = "session-log"
SORT session_date DESC
LIMIT 10
```

## Необработанные логи

```dataview
LIST
FROM "01 Inbox/sessions/raw"
WHERE status = "unprocessed"
```

## Сейчас читаю

```dataview
TABLE author, rating
FROM "30 Resources"
WHERE type = "literature" AND status = "reading"
```
