---
type: project
status: active
priority: 1
tags: [project, bringo]
created: 2026-04-07
---

# Bringo

Платформа для работы с UK Companies House — поиск компаний, директоров, PSC, финансовых данных.

## Стек

- **Backend:** Symfony 6.4, PHP 8.4, Doctrine, RabbitMQ
- **API:** Laravel 13, PHP 8.5, Filament 5, Scramble (OpenAPI 3.1)
- **Frontend:** Next.js 16, React 19, TypeScript
- **AI:** Express 5, TypeScript, OpenRouter/Gemini
- **Инфраструктура:** Docker Compose, PostgreSQL 16, ClickHouse, Redis, OpenSearch, MinIO, Nginx, Horizon

## Субмодули

- [[Bringo API]] — REST API (api/)
- Backend — основной сервер (backend/)
- Frontend — веб-клиент (front/)
- AI — AI-чат (ai/)
- LP — Landing page (lp/)
- Parser — async парсер Companies House (parser/)
- Shared Models — Protobuf определения (shared-models/)

## Ссылки

- Репозиторий: bringo-co-uk (git субмодули)
- [[Claude Code Bringo]] — конфигурация Claude Code
