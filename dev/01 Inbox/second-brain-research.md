---
type: literature
tags: [research, second-brain, openclaw, obsidian, ai-agents]
status: reading
created: 2026-04-07
---

# Исследование: Second Brain + OpenClaw + Claude Code

Коллекция ссылок и аналогов для построения комплексного решения. Цель — изучить подходы, взять лучшее, собрать свою систему.

## Новые ссылки

### Obsidian + Claude Code
- [Obsidian CLI + Claude Code: эволюция PKM](https://constructbydee.substack.com/p/my-obsidian-evolved-again-obsidian) — Construct By Dee, 2026-02. Три уровня: структура → обработка → контроль интерфейса. Голосовое управление как Jarvis.
- [Claude Code + Obsidian: short guide](https://www.reddit.com/r/ClaudeAI/comments/1qr19df/claude_code_obsidian_how_i_use_it_short_guide/) — Reddit гайд по интеграции

### OpenClaw
- [awesome-openclaw-usecases](https://github.com/hesamsheikh/awesome-openclaw-usecases) — 42+ реальных use cases: social media, creative, DevOps, productivity, research, finance
- [Мультиагентность в OpenClaw](https://habr.com/ru/articles/1013150/) — OpenClaw_Lab, Habr. Отдельные агенты, субагенты, ACP. Диспетчер + специализированные агенты по Telegram-топикам
- [Тонкая настройка OpenClaw](https://habr.com/ru/articles/1009862/) — OpenClaw_Lab, Habr. Туториал: openclaw.json секция за секцией, heartbeat, multi-agent, Telegram
- [OpenClaw в VirtualBox](https://habr.com/ru/articles/1001992/) — OpenClaw_Lab, Habr. Установка, архитектура, SOUL/USER/MEMORY — «душа = текстовые файлы»

### Second Brain фреймворки
- [agent-second-brain](https://github.com/smixs/agent-second-brain) — Сергей Шима. Три фазы Capture→Execute→Reflect, память Эббингауза, Todoist, ежедневные отчёты
- [COG Second Brain](https://github.com/huytieu/COG-second-brain) — 17 skills, evolution cycle (daily→weekly→monthly→framework), self-healing cross-references, role packs
- [second-brain-skills](https://github.com/coleam00/second-brain-skills) — 6 skills для Claude Code, progressive context disclosure, SOP Creator, MCP Client
- [llm-second-brain](https://github.com/obuzek/llm-second-brain) — Ollama + Granite 8B + OpenWebUI, полностью локальный, RAG pipeline

### Claude Code Marketplace
- [claude-marketplace](https://github.com/dashed/claude-marketplace) — Пример personal marketplace, структура для своих skills
- [Obsidian Skills plugin](https://github.com/kepano/obsidian-skills) — Steph Ango, official. obsidian-cli, markdown, bases, canvas, defuddle
- [Документация: Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) — Официальная дока Claude Code

### Obsidian + OpenClaw
- [ObsidianClaw plugin](https://github.com/oscarhenrycollins/obsidianclaw) — Чат с OpenClaw из Obsidian, streaming, tool calls visibility

### Инструменты для сравнения
- [Todoist](https://www.todoist.com/ru) — Менеджер задач, аналог для сравнения с Kill-List. Используется в agent-second-brain.

## Уже изучено в сессии 2026-04-07

Подробный анализ проведён по: COG, second-brain-skills, agent-second-brain, OpenClaw docs (workspace, heartbeat, multi-agent, skills, cron). Ключевые выводы встроены в наши skills и AGENTS.md.

## Что взять

- [ ] COG: monthly knowledge consolidation → уже в нашем knowledge-consolidation skill
- [ ] agent-second-brain: Capture→Execute→Reflect → уже в AGENTS.md Бадяна
- [ ] Мультиагентность: топики Telegram → в roadmap (Часть 6 плана)
- [ ] Habr туториалы: тонкая настройка heartbeat и субагентов → применить при настройке сервера
- [ ] awesome-openclaw-usecases: найти идеи для автоматизации

## Связи
- [[Bringo]]
- [[bringo|10 Projects/Bringo/bringo]]


### Кросс-проектный контекст
- [ai-workspace](https://github.com/lee-to/ai-workspace) — Rust CLI + MCP-сервер. Группировка проектов → общий пул файлов/заметок → AI-агент видит всё через MCP. Решает проблему «слепоты» агента при работе с микросервисами/монорепо. SQLite, .ai-workspace.json в git. Полезно для Bringo (api+backend+front в одной группе).