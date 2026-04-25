---
name: Не обрезать вывод тестов через tail
description: Use when running php artisan test or similar long outputs — tail/head hides actual errors, only shows summary
type: feedback
originSessionId: 25fbed6f-6dcf-4b97-a5c2-04dae6b14909
---
Никогда не пайпить `php artisan test` (и аналогичные многоблочные выводы) через `| tail -N` или `| head -N` — при обрезке теряются сами сообщения об ошибках, видна только сводка и хвост.

**Why:** пользователь явно сказал «увидишь число и толку не будет, только хвост». Обрезка особенно вредит в длинных тест-сьютах, где ошибки разбросаны по середине (напр. 4 fail посреди 600+ тестов — tail покажет только последний failed + summary, root причина скрыта).

**How to apply:**
- Запускать без pipe на tail, или сохранять в файл: `php artisan test > /tmp/test-output.log 2>&1`, потом читать через Read или Grep по конкретным блокам.
- Для коротких фильтров (`--filter=Foo`) tail всё-таки уместен, если явно видно что testsuite короткий.
- Применять то же правило для pint/phpstan при полной прогонке.
