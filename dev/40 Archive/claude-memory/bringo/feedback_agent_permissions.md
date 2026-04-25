---
name: Agent Permissions Issue
description: Background agents cannot write files even with bypassPermissions mode — use foreground agents or write files manually after agent completes
type: feedback
---

Background agents (run_in_background: true) не могут писать файлы даже с mode: bypassPermissions. Write и Bash блокируются.

**Why:** Ограничение текущей версии Claude Code — фоновые агенты наследуют permissions родителя, но bypassPermissions не пробрасывается.

**How to apply:** Для задач, требующих записи файлов, использовать foreground agents или запускать агента для генерации контента, а записывать файл в основном потоке после получения результата.
