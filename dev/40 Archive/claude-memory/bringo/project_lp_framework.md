---
name: LP Pipeline Framework
description: White-label LP Pipeline переехал из lp/ субмодуля в ai-tools/ как два отдельных компонента для дистрибуции
type: project
---

LP Pipeline выносится из lp/.claude/ в распространяемый фреймворк с двумя компонентами:

1. **ai-tools/lp-pipeline/** — Claude Code Plugin (GitLab-репо)
   - 17 skills (generic, без Bringo хардкода)
   - 11 agents (generic)
   - 9 generic references + image-prompt-templates.md
   - 5 шаблонов для brand-specific файлов
   - scrape-brand.mjs — скрейпинг URL → brand config
   - /lp-init визард для инициализации под любой бренд

2. **ai-tools/mcp-image-gen/** — npm-пакет @bringo/mcp-image-gen
   - 5 MCP tools: generate_image, generate_icon, optimize_image, generate_favicon_set, batch_generate
   - Модель: google/gemini-3.1-flash-image-preview через OpenRouter
   - CI: npm publish в GitLab Packages (по образцу shared-models)
   - Подключение через npx в .mcp.json

**Why:** Коллеги из разных проектов/брендов должны создавать LP с LP pipeline. Bringo — одна из конфигураций.

**How to apply:** При работе с LP pipeline смотреть в ai-tools/, а не в lp/.claude/. SSI полностью убран — header/footer инлайнятся в index.html.
