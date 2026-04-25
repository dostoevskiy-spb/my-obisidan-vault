---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-08_10-48_backend-cache-clear-fix.md
session_date: 2026-04-08
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [backend] Фикс cache:clear — autowire Redis
**Дата:** 2026-04-08 10:48
**Субмодуль:** backend
**Цель:** Починить падение бекенда при cache:clear из-за невозможности autowire Redis для ApiWebhookRelayHandler

---

## Лог

### 10:48 — Начало
- Задача: бекенд не стартует, cache:clear падает с ошибкой autowiring Redis для ApiWebhookRelayHandler
- Контекст: ошибка `Cannot autowire service "App\Service\ApiWebhook\ApiWebhookRelayHandler": argument "$redis" of method "__construct()" references class "Redis" but no such service exists`

### 10:49 — Диагностика и фикс
- Что: нашёл ApiWebhookRelayHandler — конструктор принимает `\Redis $redis`, но нет привязки к сервису snc_redis.default. Аналогичная привязка уже есть для RedisCircuitBreaker в services_apollo.yaml
- Результат: добавил explicit binding `$redis: '@snc_redis.default'` в services.yaml
- Файлы: backend/config/services.yaml

---

## Итоги
- **Выполнено:** добавлена привязка Redis для ApiWebhookRelayHandler в services.yaml

## Реализация

### Конфигурация
- `backend/config/services.yaml`: добавлен блок `App\Service\ApiWebhook\ApiWebhookRelayHandler` с аргументом `$redis: '@snc_redis.default'`
