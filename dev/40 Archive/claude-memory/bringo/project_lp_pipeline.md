---
name: LP Pipeline V2 — Ревью и рефакторинг
description: Масштабное обновление LP Pipeline: TeamCreate + 12 Gates, динамические дизайнеры, перевод до показа, оптимизация изображений
type: project
---

## LP Pipeline V2 — Утверждённый план (2026-03-18)

**План:** `/home/pavel/.claude/plans/streamed-questing-karp.md`

### Ключевые решения:
- **TeamCreate + Gates** вместо волн: 8 базовых агентов spawn upfront + N designer-агентов динамически на Gate 5
- **Дизайнеры параллельно**: спавнятся 1-5 (default 3), каждый в своём .pen файле, параллельно с fact-check
- **Перевод — железное правило**: translate BEFORE present, re-translate after modify, никогда не показывать без _ru.md
- **Изображения**: хранятся в `lp/{slug}/images/`, webp оптимизация, OG-image генерация
- **UX "Авто/Ввод"** перед каждым gate
- **CTA 5 states**: guest, trial-available, no-subscription, subscriber, cancelled
- **zoom:1.1 → font-size:110%**
- **Tablet breakpoints**: +1024px, +768px в QA
- **Общая папка references**: `lp/.claude/references/` — без дублей

### Прогресс:
- Шаг 1 ✅ — дубликаты из `.claude/` (корень main) удалены (15 skill-директорий + 10 agent-файлов)
- Шаги 2-14 — ожидают выполнения

**Why:** E2E тест пайплайна выявил дублирование файлов, устаревшие CTA states (3 вместо 5), отсутствие TeamCreate, перевод после показа, zoom:1.1 вместо font-size.

**How to apply:** Продолжить выполнение плана с шага 2. Все правки в `lp/.claude/` (субмодуль). План содержит точные файлы/строки для каждого шага.
