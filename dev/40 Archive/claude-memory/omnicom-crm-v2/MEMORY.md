# Memory — CRM v2

## Специализированные агенты (slash commands)

Создано 6 агентов в `.claude/commands/`:

| Команда | Роль | Зона ответственности |
|---------|------|---------------------|
| `/api-designer` | API Architect | OpenAPI specs, paths, schemas, Orval генерация |
| `/backend` | Backend Dev | Модели, миграции, Actions, Queries, Controllers, DDD |
| `/frontend` | Frontend Dev | Vue pages, components, composables, DataGrid/DataView |
| `/analyst` | Аналитик | ТЗ, декомпозиция задач, spec-vs-implementation |
| `/tester` | Тестировщик | Pest unit/feature, Policy tests, E2E Playwright |
| `/tech-writer` | Тех. писатель | README, architecture.md, ADR, чек-листы |

## Важные правила работы

- **ВСЕГДА спрашивать перед радикальными изменениями** — замена компонента/подхода на другой (например, SchemaForm → ручные поля) требует согласования с пользователем. Не делать таких замен молча.
- **ВСЕГДА делать code review после завершения задачи** — перечитать все изменённые/созданные файлы, проверить корректность, консистентность с паттернами проекта, отсутствие ошибок и оверинжинирнга. Если находишь - показываешь и предлагаешь дальнейшие варианты действий. Я одобряю или отклоняю. Без разрешения правки не вносишь

## Работа с миграциями
- схема public, общая для всего проекта. С помощью php artisan module:migrate-fresh --seed --all
- каждый тенента в своей схеме
- создание тенанта и схемы: php artisan tenant:create Omnicomm --domain=crm.localhost --slug=omnicomm --seed
- миграции для каждого тенанта: php artisan tenant:migrate-fresh --seed --force

## Ключевые паттерны проекта

- UUID PK (Ramsey), soft deletes + activity log обязательны
- Модели в `app/Entities/`, namespace без `app`
- `casts()` метод, не свойство (Laravel 12)
- Update Request: `sometimes` + `filled` (НЕ `required`)
- SchemaDataGrid для Index.vue, DataView для секций табов Show.vue
- Glassmorphism стили для hero-карточек и контейнеров
- LogBatch::startBatch/endBatch в Actions
- Gen API: `docker compose exec workspace bash -c "source ~/.nvm/nvm.sh && npm run gen:api"`
- Модуль Finance (Account Ledger) спроектирован, не реализован → см. [finance-module-plan.md](finance-module-plan.md)
- Модуль УПД (Waybill) — не реализован. После его добавления: доработать вкладку УПД на карточке ТС (Vehicle) — обновить колонки грида (Номер документа, Дата документа), убрать заглушку, добавить linkTo

