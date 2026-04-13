---
type: session-log-raw
project: bringo
submodule: backend
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-13_21-49_email-subscriber-doc.md
session_date: 2026-04-13
tags:
  - session-log-raw
  - bringo
  - backend
created: 2026-04-14
status: unprocessed
---

# Сессия: [backend] Документация эндпоинта email-subscriber
**Дата:** 2026-04-13 21:49
**Субмодуль:** backend
**Цель:** Подготовить доку для коллеги по REST-эндпоинту EmailSubscriberController

---

## Лог

### 21:49 — Начало
- Задача: написать markdown-доку по `POST /api/email-subscriber/subscribe`
- Контекст: контроллер прочитан, нужно изучить сервис, конфиг и rate limiter

### 21:50 — Анализ контроллера и сервиса
- Контроллер: [EmailSubscriberController.php](../../backend/src/Controller/V2/Rest/EmailSubscriberController.php)
- Сервис: [EmailSubscriberService.php](../../backend/src/Service/EmailSubscriber/EmailSubscriberService.php)
- Префикс роутов: `/api` (из `backend/config/routes.yaml:23`) → полный URL `POST /api/email-subscriber/subscribe`
- Rate limiter `limiter.api`: sliding_window, 10 req / 1 min, ключ — IP клиента (`backend/config/packages/rate_limiter.yaml:3`)
- Параметр `app.email_subscriber.gdpr_consent_required` = `false` (`backend/config/parameters.yaml:240`)
- Email нормализуется (trim + lowercase) и валидируется как HTML5 email
- Если email уже существует — возвращается success без записи (идемпотентность)
- Поля entity: gdprConsent, ipAddress, source, name, message; subscriber сразу confirm() + activate(), welcome email пока TODO
- Enum статусов: FAILED=0, SUCCESS=1, PENDING=2 — в JSON отдаётся числом через `->value`
