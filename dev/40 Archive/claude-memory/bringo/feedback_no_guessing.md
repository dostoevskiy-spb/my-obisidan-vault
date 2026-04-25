---
name: No guessing — always research first
description: Never guess commands, paths, or solutions — always read files and provide evidence with the answer
type: feedback
---

Никогда не угадывай команды, пути, имена сервисов или решения. Если есть теория — она должна быть подтверждена исследованием (чтение файлов, grep, документация).

**Why:** Пользователь дал угаданную команду с неправильным именем сервиса (client-api вместо api), хотя ответ был в CLAUDE.md субмодуля. Угадывание тратит время и подрывает доверие.

**How to apply:** Перед любым ответом — прочитай CLAUDE.md, compose-файлы, package.json/composer.json или другие релевантные файлы. Приводи в ответе ссылку на источник (файл:строка), откуда взято решение.
