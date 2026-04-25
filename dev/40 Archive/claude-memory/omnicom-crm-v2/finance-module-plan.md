# План: Модуль Finance (Account Ledger)

**Статус:** Спроектирован, не реализован
**Дата:** 2026-02-22
**Заменяет:** Plan 011 (money_movements) — НЕ реализовывать

## Суть

Новый модуль `Modules/Finance/` — Account Ledger для управления финансами юрлиц:
- `finance_accounts` — счета учёта (receivable, payable, settlement, manual) per legal entity
- `finance_entries` — проводки с morph-ссылкой на документ (Waybill, будущие Invoice, Act)
- Баланс пересчитываемый: `legal_entities.balance` = агрегат по счетам
- Автоматические проводки при создании/удалении Waybill через Listeners
- Сторнирование вместо удаления записей
- Ручные корректировки через UI

## Детальный план

Полный план сохранён в `/home/pavel/.claude/plans/buzzing-growing-hickey.md`

## Ключевые решения

- Account Ledger (не flat ledger, не double-entry)
- Отдельный модуль Finance (priority 82, tenant)
- Односторонняя зависимость: Finance слушает Waybill events
- Act интеграция отложена (нет сумм у актов)
- 4 типа счетов: receivable, payable, settlement, manual
- direction (debit/credit) + amount (всегда положительный)
- Frontend: замена заглушки "Движение ДС" в Show.vue юрлица
