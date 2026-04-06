---
type: alerts
---

# Алерты

## Просроченные задачи

```tasks
not done
due before today
sort by due
```

## Дедлайны на этой неделе

```tasks
not done
due after yesterday
due before in 7 days
sort by due
```

## Проекты без обновлений > 7 дней

```dataview
TABLE file.mtime AS "Обновлено", status, deadline
FROM "10 Projects"
WHERE type = "project" AND status = "active"
WHERE file.mtime < date(today) - dur(7 days)
SORT file.mtime ASC
```

## Задачи без дедлайна

```tasks
not done
no due date
no scheduled date
sort by priority
limit 20
```

## Приближающиеся дедлайны проектов

```dataview
TABLE deadline, status, priority
FROM "10 Projects"
WHERE type = "project" AND status = "active" AND deadline
WHERE deadline <= date(today) + dur(14 days)
SORT deadline ASC
```
