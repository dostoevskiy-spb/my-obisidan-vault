---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-08_16-17_redis-autowire-fix.md
session_date: 2026-04-08
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [backend] Фикс autowire Redis в ApiWebhookRelayHandler
**Дата:** 2026-04-08 16:17
**Субмодуль:** backend
**Цель:** Исправить ошибку `Cannot autowire service "App\Service\ApiWebhook\ApiWebhookRelayHandler": argument "$redis" references class "Redis" but no such service exists`

---

## Лог

### 16:17 — Начало
- Задача: исправить ошибку autowire Redis при `composer install` / `cache:clear`
- Контекст: ошибка возникает в post-install скрипте `cache:clear`

### 16:18 — Анализ проблемы
- Что: проверены `ApiWebhookRelayHandler.php` и `config/services.yaml`
- Результат: найден алиас `\Redis: '@snc_redis.default'` в services.yaml:12, но Symfony его не подхватывает
- Детали: обратный слэш `\` в YAML-ключе не распознаётся как валидный алиас класса `Redis`. Symfony ищет сервис `Redis` (без слэша), а в конфиге зарегистрирован `\Redis` (со слэшем). Несмотря на то что в PHP `\Redis` и `Redis` — один класс, в Symfony DI ключи YAML не нормализуются.

### 16:19 — Фикс
- Что: заменил `\Redis: '@snc_redis.default'` → `Redis: '@snc_redis.default'` в services.yaml:12
- Результат: `cache:clear` прошёл успешно
- Файлы: `backend/config/services.yaml`

---

## Итоги
- **Выполнено:** исправлена ошибка autowire Redis
- **В память:** YAML-ключи с обратным слэшем не нормализуются Symfony DI
