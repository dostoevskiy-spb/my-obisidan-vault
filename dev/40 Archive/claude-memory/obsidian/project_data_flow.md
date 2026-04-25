---
name: Data flow pipeline for session logs
description: Architecture of automated session log collection from dev projects into Obsidian vault
type: project
---

Настроен поток данных из проектов в Obsidian vault (2026-04-07).

**Архитектура:**
- **Локально (02:00, systemd timer):** `/collect-sessions` — Claude Code сканирует ~/dev/www/, находит .claude/sessions/, копирует raw-логи в `01 Inbox/sessions/raw/`, помечает SESSION_INDEX.md
- **На сервере:** `/digest` — Claude Code обрабатывает raw → создаёт саммари с wiki-links в `01 Inbox/`, архивирует raw в `40 Archive/sessions/`
- **Синхронизация:** git auto-push/pull каждую минуту (obsidian-git)

**Трекинг:** Пометки `[imported:YYYY-MM-DD last-log:HH:MM]` в SESSION_INDEX.md каждого проекта. Повторный запуск проверяет обновления.

**Ключевые файлы:**
- `.claude/commands/collect-sessions.md` — команда сбора (локально)
- `.claude/commands/digest.md` — команда обработки (сервер)
- `.claude/skills/vault-digest/SKILL.md` — skill обработки
- `scripts/collect-sessions.sh` — bash fallback
- `~/.config/systemd/user/vault-collect-sessions.timer` — cron в 02:00

**Why:** Информация из проектных сессий терялась в .claude/sessions/ — нужно централизовать в Second Brain.

**How to apply:** При работе с проектами помнить что логи автоматически собираются ночью. Команда /collect-sessions для ручного запуска.
