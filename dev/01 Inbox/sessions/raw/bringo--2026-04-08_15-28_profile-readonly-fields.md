---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/2026-04-08_15-28_profile-readonly-fields.md
session_date: 2026-04-08
tags: [session-log-raw, bringo, backend, front, profile, readonly]
created: 2026-04-09
status: unprocessed
---

# Сессия: [backend, front] Readonly поля в профиле ЛК
**Дата:** 2026-04-08 15:28
**Субмодуль:** backend, front
**Цель:** Сделать поля имя, фамилия и номер компании в настройках профиля read-only (отображаем, но не даём редактировать)

---

## Лог

### 15:28 — Начало
- Задача: подготовить план из двух частей — бекенд (реализуем сами) и фронт (описание для коллеги)
- Контекст: в ЛК в настройках профиля есть поля first name, last name, company number — нужно сделать их read-only

### 15:30 — Исследование бекенда и фронта
- Что: параллельно исследованы backend (UserProfileService, User entity, proto) и frontend (ProfileForm, useUpdateProfile, schema)
- Результат: полная картина
- Детали:
  - Бекенд: gRPC V2 UserProfileService.Update() в backend/src/Controller/V2/Grpc/Account/UserProfileService.php обновляет name, phone, companyName, password
  - Фронтенд: ProfileForm с полями email (disabled), phone, firstName, lastName, companyName, passwords
  - Поля companyNumber нет в User entity — есть только companyName. Пользователь подтвердил что имеется в виду companyName

### 15:43 — Правки бекенда
- Что: удалены блоки обновления name (firstName/lastName) и companyName из метода Update()
- Результат: успех
- Файлы: backend/src/Controller/V2/Grpc/Account/UserProfileService.php
- Детали: API теперь игнорирует эти поля в запросе, но продолжает возвращать их в Get/GetFull. Линтер автоматически убрал неиспользуемый импорт PersonName
