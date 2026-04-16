---
type: literature
tags: [tool, mcp, yandex, seo, api, claude-code]
source: https://github.com/altrr2/yandex-tools-mcp/
created: 2026-04-16
status: reading
rating: 4
---

# Yandex Tools MCP

MCP-серверы для Yandex API — поиск, подбор ключевых слов, вебмастер и веб-аналитика для русскоязычного рынка.

## Что это

Набор MCP-серверов, которые дают Claude доступ к инструментам Яндекса через стандартный протокол Model Context Protocol.

## Пакеты

| Пакет | Назначение | Токен |
|---|---|---|
| `yandex-wordstat-mcp` | Подбор ключевых слов через Wordstat API | `YANDEX_WORDSTAT_TOKEN` |
| `yandex-search-mcp` | Поиск через Yandex Search API | `YANDEX_SEARCH_API_KEY` + `YANDEX_FOLDER_ID` |
| `yandex-webmaster-mcp` | SEO-аналитика через Webmaster API | `YANDEX_WEBMASTER_TOKEN` |
| `yandex-metrika-mcp` | Трафик и аналитика через Metrika API | `YANDEX_METRIKA_TOKEN` |

## Установка

Каждый пакет ставится отдельно через npx в `.mcp.json`:

```json
{
  "mcpServers": {
    "yandex-webmaster": {
      "command": "npx",
      "args": ["-y", "yandex-webmaster-mcp-server"],
      "env": {
        "YANDEX_WEBMASTER_OAUTH_TOKEN": "your_token"
      }
    }
  }
}
```

Или как Claude Code плагин целиком:

```bash
claude --plugin-dir /path/to/yandex-tools-mcp
```

## Встроенные навыки

- `yandex-keyword-research` — подбор ключевых слов
- `yandex-competitive-analysis` — конкурентный анализ

## Связи

- [[AZT — Baseline Яндекс Вебмастер 2026-04-15]] — используем `yandex-webmaster-mcp` для проекта AZT
- [[AZT — P0 задачи с обоснованием из Вебмастера 2026-04-16]] — данные собраны через этот MCP

Лицензия: MIT, автор Alternex.
