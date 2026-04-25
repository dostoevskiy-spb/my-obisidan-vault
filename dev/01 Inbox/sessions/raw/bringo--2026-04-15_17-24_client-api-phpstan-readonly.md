---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-15_17-24_client-api-phpstan-readonly.md
session_date: 2026-04-15
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [client-api] phpstan падает на readonly class

**Дата:** 2026-04-15 17:24
**Субмодуль:** client-api
**Цель:** Разобраться почему phpstan падает на `readonly` токене в vendor/sebastian/version

---

## Лог

### 17:24 — Начало
- Задача: `vendor/bin/phpstan analyze --memory-limit=512M` падает с parse error на `readonly` в `vendor/sebastian/version/src/Version.php:26`
- Контекст: путь `/builds/bringo/bcu/applications/client-api/` — это путь в контейнере (CI-like). `readonly class` появился в PHP 8.2. Значит phpstan запущен PHP <8.2
- composer.json требует `"php": "^8.3"`, Dockerfile `dunglas/frankenphp:php8.5-alpine` — в контейнере должен быть PHP 8.5

### 17:26 — Проверка окружений
- Локальный PHP: 8.3.30 (поддерживает readonly class → проблема не локальная)
- В контейнере `api`: PHP 8.5.5 (тоже ок)
- Путь из ошибки `/builds/bringo/bcu/applications/client-api/` — это классический GitLab Runner path (`$CI_PROJECT_DIR`). Значит ошибка из CI, не из локалки
- `vendor/sebastian/version/src/Version.php:26` содержит `final readonly class Version` (PHP 8.2+)

### 17:27 — Root cause найден
- client-api/.gitlab-ci.yml:76 — PHPStan job использует `image: registry.bringo.tel/bringo/common/docker/php/cli-production:latest`
- Остальные PHP-джобы: PHPUnit → `cli-development` (с правильной PHP-версией), Pint → `composer:2`
- `cli-production:latest` содержит PHP < 8.2, поэтому парсер падает на `readonly class`
- Маскируется флагом `composer install --ignore-platform-reqs --no-scripts` — composer ставит phpunit 12, который требует PHP 8.3+, но runner не имеет такой версии
