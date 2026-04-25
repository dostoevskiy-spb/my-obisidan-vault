---
name: Use Obsidian CLI instead of manual edits
description: Prefer obsidian CLI commands over direct file edits when working with the vault
type: feedback
---

При работе с Obsidian vault использовать CLI (`obsidian` команды) вместо ручного редактирования .md файлов через Read/Edit/Write.

**Why:** CLI корректно обновляет индексы Obsidian, работает с метаданными, задачами, свойствами и ссылками нативно. Ручное редактирование может рассинхронизировать состояние vault.

**How to apply:**
- Создание заметок: `obsidian create name="..." content="..."`
- Добавление контента: `obsidian append`/`obsidian prepend`
- Задачи: `obsidian task ... done/todo/toggle`
- Свойства: `obsidian property:set`/`property:read`
- Поиск: `obsidian search query="..."`
- Чтение: `obsidian read file="..."`
- Daily notes: `obsidian daily:read`/`daily:append`
- Теги, бэклинки, outline — всё через CLI
- Загружать скилл `obsidian:obsidian-cli` при работе с vault
- Ручное редактирование через Edit/Write допустимо только для сложных структурных правок, где CLI недостаточен
