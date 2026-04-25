---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-24_12-34_front-next-seo-build-error.md
session_date: 2026-04-24
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [front] Build error — Can't resolve 'next-seo/pages'
**Дата:** 2026-04-24 12:34
**Субмодуль:** front
**Цель:** починить локальную сборку после `git pull`

---

## Лог

### 12:34 — Начало
- Задача: пользователь показал скриншот Build Error из Next.js — `Module not found: Can't resolve 'next-seo/pages'` в `./src/pages/_App/View/index.tsx (21:1)`
- Контекст: пользователь назвал это «бекофисом», но по URL `/admin/login/` и пути файла очевидно — это front (Next.js), а не backoffice (Laravel/PHP)

### 12:36 — Диагностика
- Что: проверил package.json, yarn.lock, node_modules и историю коммитов
- Результат: root cause найден
- Детали:
  - [front/package.json:68](front/package.json#L68) — `"next-seo": "^7.2.0"`
  - yarn.lock содержит resolution на 7.2.0
  - node_modules/next-seo/package.json — версия **6.8.0** (старая, до миграции)
  - Коммит `348d7cca7 Migrate next-seo v6 to v7` — в v7 появился subpath `./pages` (в v6 его не было — отсюда ошибка резолвинга)
  - В контейнере `bcu-front-1` тот же устаревший node_modules (volume с хоста)
- Причина: после `git pull` на master не запущен `yarn install`, node_modules не пересобраны

### 12:37 — Решение
- Выполнить `docker compose exec -it front yarn install` и перезапустить dev-сервер
