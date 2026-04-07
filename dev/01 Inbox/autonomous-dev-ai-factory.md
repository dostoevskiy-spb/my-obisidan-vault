---
type: literature
tags: [research, ai-factory, autonomous-dev, kanban, ci-cd, ai-agents]
status: reading
created: 2026-04-07
---

# Исследование: Автономная разработка — AI Factory + Handoff

Инструменты от lee-to для полной автоматизации цикла разработки. Изучить и внедрить в рабочие процессы [[Bringo]] и [[OmniCom CRM|OmniCom-CRM]].

## AI Factory

**Репо:** [lee-to/ai-factory](https://github.com/lee-to/ai-factory) (455 stars, TypeScript)
**Суть:** CLI для настройки AI-driven development environment. «Stop configuring. Start building.»

### Ключевые фичи
- **Zero-config**: автоматическая установка skills по типу проекта
- **Spec-driven development**: план → approve → implement → review (не хаотичный AI-кодинг)
- **Checkpoint commits**: автоматические коммиты после каждого этапа
- **Skill evolution**: `/aif-fix` создаёт патчи → `/aif-evolve` генерирует всё более умные правила
- **Multi-agent**: Claude Code, Cursor, Windsurf, Codex, Gemini CLI, Copilot и ещё 8+

### Workflow (slash-команды)
| Команда | Что делает |
|---------|-----------|
| `/aif-explore` | Исследование перед планированием |
| `/aif-grounded` | Проверенные ответы без изменения кода |
| `/aif-plan` | Пошаговый план с анализом кодовой базы |
| `/aif-improve` | Итеративное улучшение плана |
| `/aif-implement` | Выполнение с checkpoint-коммитами |
| `/aif-fix` | Багфикс + запись в institutional knowledge |
| `/aif-ci` | Настройка GitHub Actions / GitLab CI |
| `/aif-docs` | Автогенерация README + docs/ |

### Архитектура подагентов
- **Planning subagent** — анализ кодовой базы, пошаговые планы
- **Implementation subagent** — выполнение с узким контрактом роли
- **Loop subagent** — цикл generate → evaluate → critique → refine

---

## AIF Handoff

**Репо:** [lee-to/aif-handoff](https://github.com/lee-to/aif-handoff) (TypeScript, Turborepo)
**Суть:** Автономная Kanban-доска — AI-агенты сами планируют, реализуют и ревьюят задачи.

### Конвейер
```
Backlog → Planning → Plan Ready → Implementing → Review → Done
                                      ↑                |
                                      └── request_changes ←┘
```

### Ключевые фичи
- **Полная автоматизация**: создал задачу → агенты всё делают сами
- **UI**: drag-and-drop Kanban с WebSocket real-time обновлениями
- **Подагенты**: plan-coordinator, implement-coordinator, review-sidecar, security-sidecar
- **Self-healing**: heartbeat + watchdog для зависших задач
- **Human-in-the-loop**: можно одобрить/отклонить план вручную
- **Параллельное выполнение**: слой-ориентированное распределение по зависимостям

### Провайдеры
Claude (SDK/CLI/API), Codex (SDK/CLI/API), OpenRouter, OpenCode + кастомные адаптеры

### Стек
React + Vite + TailwindCSS (UI), Hono + WebSocket (API), SQLite + drizzle-orm (DB), node-cron (scheduler)

---

## AIF Handoff JetBrains Plugin

**Репо:** [lee-to/aif-handoff-jb-plugin](https://github.com/lee-to/aif-handoff-jb-plugin) (Kotlin)
**Суть:** Интеграция Handoff Kanban в JetBrains IDE (IntelliJ, PhpStorm, WebStorm).

---

## Что внедрить в наши процессы

- [ ] AI Factory skills (`/aif-plan`, `/aif-implement`) — spec-driven подход вместо хаотичной разработки
- [ ] Skill evolution — автоматическое накопление знаний из багфиксов
- [ ] Checkpoint commits — автоматические коммиты после каждого шага плана
- [ ] Handoff Kanban — попробовать для автономной разработки фич [[Bringo]]
- [ ] Security sidecar — автоматическое ревью безопасности при каждом PR

## Связи
- [[Bringo]]
- [[second-brain-research]]
- [[ai-workspace|AI Workspace (lee-to)]]
