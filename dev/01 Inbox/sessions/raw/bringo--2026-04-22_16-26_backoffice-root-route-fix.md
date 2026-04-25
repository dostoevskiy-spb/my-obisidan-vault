---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-22_16-26_backoffice-root-route-fix.md
session_date: 2026-04-22
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# Сессия: [backoffice] Падение корневого роута
**Дата:** 2026-04-22 16:26
**Субмодуль:** backoffice
**Цель:** Починить 500 на https://nginx/backoffice/

---

## Лог

### 16:26 — Начало
- Задача: бекофис падает с `InvalidArgumentException: View [] not found`
- Контекст: скриншот показывает trace на `routes/web.php:6` → `return view(null);`

### 16:27 — Диагностика
- Что: прочитал `backoffice/routes/web.php` и `AdminPanelProvider.php`
- Результат: корневой роут `/` возвращает `view(null)` — мусорный placeholder из base Laravel-шаблона (коммит 56e31f6). Filament-панель смонтирована на `/admin` (строка 30 AdminPanelProvider)
- Детали: пользователь заходит на `/backoffice/` → nginx проксирует на Laravel как `/` → ловит мусорный роут

### 16:29 — Первая попытка: Route::redirect('/', '/admin')
- Что: заменил `view(null)` на `Route::redirect('/', '/admin')`
- Результат: 302 на `https://nginx/admin` — БЕЗ nginx-префикса `/backoffice`
- Детали: `Route::redirect` формирует относительный `Location: /admin`, браузер резолвит от корня домена. nginx конфиг (compose.d/nginx/conf.d/nginx.conf:35-52) проксирует `/backoffice/` → Laravel `/`, но Laravel ничего не знает про внешний префикс. Хотя `X-Forwarded-Prefix: /backoffice` передаётся, Laravel его по умолчанию не читает.

### 16:31 — Решение: использовать config('app.url')
- Что: `Route::get('/', fn() => redirect(config('app.url') . '/admin'))`
- Результат: 302 → `https://nginx/backoffice/admin` → 200 `https://nginx/backoffice/admin/login`
- Детали: `APP_URL=https://nginx/backoffice` в compose.d/backoffice/.env содержит префикс, поэтому редирект получается корректным. Filament-логин открывается.
- Файлы: backoffice/routes/web.php

---

## Итоги
- **Выполнено:** корневой роут `/` в backoffice теперь редиректит на Filament-панель `/backoffice/admin`
- **В память:** backoffice проксируется nginx с префиксом `/backoffice`, Laravel APP_URL содержит префикс — но X-Forwarded-Prefix по умолчанию не обрабатывается, для генерации URL нужно использовать `config('app.url')` либо абсолютные пути

## Реализация

### Роутинг
- `backoffice/routes/web.php`: корневой роут `/` теперь `redirect(config('app.url') . '/admin')` вместо `view(null)`. Отрабатывает с учётом внешнего nginx-префикса `/backoffice`.
