---
type: moc
tags: [hub, moc]
---

# Карты контента (MOC)

Индекс всех Maps of Content в vault. MOC — это навигационные заметки, которые собирают ссылки по теме.

## Как использовать

1. Когда накопится 5+ заметок по одной теме — создай MOC
2. MOC содержит ссылки на все связанные заметки с кратким описанием
3. Добавляй новые MOC сюда по мере роста vault

## Все MOC

```dataview
LIST
FROM "00 HUB"
WHERE type = "moc" AND file.name != "MOC Index" AND file.name != "Dashboard"
SORT file.name ASC
```

## MOC по областям

```dataview
LIST
WHERE contains(tags, "moc")
SORT file.name ASC
```
