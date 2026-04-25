---
type: session-log-raw
project: yandex-business
source: /home/pavel/dev/www/mcp/yandex-business/.claude/sessions/2026-04-16_18-21_yandex-business-mcp.md
session_date: 2026-04-16
tags:
  - session-log
  - raw
  - yandex-business
created: 2026-04-26
status: unprocessed
---

# Сессия: Yandex Business MCP сервер
**Дата:** 2026-04-16 18:21
**Цель:** Найти документацию по API Яндекс Бизнеса и написать MCP сервер для работы с этим API

---

## Лог

### 18:21 — Начало
- Задача: исследовать API Яндекс Бизнеса, найти документацию, спроектировать и реализовать MCP сервер
- Контекст: проект пустой, начинаем с нуля

### 18:33 — Исследование API завершено
- Что: проведён полный обзор всех доступных API Яндекс Бизнеса
- Результат: найдено несколько API, но публичного REST API для статистики карточек нет
- Детали:
  - **GeoAdv API** (`geoadv-api.yandex.ru`) — API рекламного продвижения (Яндекс Бизнес Приоритет). Эндпоинты: управление рекламными кампаниями, поиск организаций, баланс/биллинг, промокоды, КП. Библиотека: promopult/yandex-business-api (PHP)
  - **Yandex Direct API v5** (`api.direct.yandex.com/json/v5/businesses`) — метод Businesses.get возвращает базовые профили организаций (Id, Name, Address, Phone, ProfileUrl, IsPublished, Rubric). Без статистики
  - **Organization Search API** (GeoSearch) — HTTP API для поиска организаций на Яндекс Картах. До 500 запросов/день бесплатно. Только чтение
  - **Публичного API для статистики конверсий (звонки, маршруты, клики) по карточкам НЕТ** — данные доступны только через веб-дашборд business.yandex.ru
  - Пользователь уточнил: ему нужны именно конверсии по карточкам (отдельно поиск/карты), которых нет в Метрике
  - Образцы MCP: yandex-metrika-mcp и yandex-wordstat-mcp (Node.js/ESM, @modelcontextprotocol/sdk + zod, OAuth авторизация)

### 18:38 — Реверс внутреннего API дашборда
- Что: через Chrome DevTools MCP перехватили сетевые запросы на страницах статистики Яндекс Бизнеса
- Результат: успех — обнаружены все ключевые API-эндпоинты
- Детали:
  - Базовый URL: `https://yandex.ru`
  - **GET /business/statistic/api/metrika/get-vacuum-statistic** — конверсии с разбивкой по webmaps/websearch/navi/business.site, параметры from/to/group/permalink
  - **GET /business/statistic/api/geovisor-session/get** — сессии посетителей с поисковыми запросами, действиями, источниками
  - **GET /business/statistic/api/campaign-list/get-lite** — список рекламных кампаний
  - **GET /business/statistic/api/company/get-company-role-safe** — роль пользователя
  - **POST /sprav/api/companies/get-companies-adv** — список организаций
  - Авторизация: cookie Session_id + CSRF-токен

### 18:42 — План написан
- План: [MCP сервер для Яндекс Бизнеса](../../.claude/plans/idempotent-mapping-nest.md)
- 4 MCP tools: get-companies, get-statistics, get-geovisor, get-campaigns
- Стек: Node.js ESM, @modelcontextprotocol/sdk, zod
