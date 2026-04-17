# Сессия: AZT — follow-up по данным Яндекс Вебмастер
**Дата:** 2026-04-17 20:33
**Цель:** Проверить, продолжаются ли проблемы с канониклами (выкидывание страниц из индекса) и генерацией битой ссылочной массы по azt-teplica.ru. Сравнить с отчётом 2026-04-16.

---

## Лог

### 20:33 — Начало
- Задача: follow-up по отчёту [[AZT — Итоговый анализ данных Яндекс Вебмастер 2026-04-16]]
- Контекст на старте (данные отчёта от 16.04):
  - Broken internal links: 428 (`catalog/catalog` — 242, `/prm/` — 93, статьи без `/news/` — 4)
  - NOT_CANONICAL events: 22 (включая `/izh/` — 14, `/ekb/` — 1)
  - REDIRECT_NOTSEARCHABLE: 83 (включая `/prm/` — 60)
  - HTTP_ERROR: 27; LOW_QUALITY: 7 (в т.ч. `/prm/` — 6)
  - Страниц в поиске: 138 (было 168 на 26.03, 165 на 05.04)
  - Исключённых: 71
  - Broken links history: 72 (14.03) → 112 (25.03) → 213 (03.04) → 428 (выборка)
  - Нули по кликам/показам с 07.04 по 16.04
  - Диагностика: NO_METRIKA_COUNTER_BINDING, DUPLICATE_CONTENT_ATTRS, NOT_MOBILE_FRIENDLY
- Ограничения: Вебмастер — только read-only (feedback memory)

### 20:45 — Сравнение с отчётом от 16.04
- Что: выгружены host_summary, diagnostics, broken_internal_links (sample), broken_links_history, search_events_history, search_events_samples, indexing_history (10-15.04), indexing_samples, important_urls
- Результат: частичное улучшение + проблемы продолжаются

**Что изменилось:**
- `NO_METRIKA_COUNTER_BINDING` → ABSENT с 2026-04-16T16:41 ✅ **Связка Метрики восстановлена!**
- Исключённых страниц: 71 → 65 (−6)
- Активных POSSIBLE_PROBLEM: 2 → 1
- Страниц в поиске: 138 (без изменений)
- SQI: 140 (без изменений)

**Что НЕ изменилось:**
- Broken internal links sample count: 428 (тот же, history ещё не обновилась — следующая точка будет ~14-15.04)
- DUPLICATE_CONTENT_ATTRS: PRESENT (08.04)
- NOT_MOBILE_FRIENDLY: PRESENT (02.04)

**Канониклы продолжают выкидывать страницы:**
Search events history 08.04–16.04 → REMOVED=47 vs APPEARED=20, баланс −27:
- 08.04: −22 / +16
- 09.04: −11 / 0
- 12.04: −9 / +1
- 14.04: −4 / +2
- 16.04: −1 / +1

**Свежие NOT_CANONICAL за период 08–14.04:**
- `/izh/` → `/` (14.04)
- `/izh/delivery/` → `/delivery/` (14.04)
- `/izh/portfolio/` → `/portfolio/` (14.04)
- `/izh/about/` → `/about/` (12.04, 03.04)
- `/izh/store/` → `/store/` (09.04)
- `/izh/catalog/komplektuyushchie/*` — 5 URL (09.04)
- `/izh/catalog/teplicy/arochnye/teplitsa-azt-premium/` (09.04)
- `/izh/catalog/teplicy/steklyannye/` (08.04)
- `/ekb/actions/rassrochka/` → `/actions/rassrochka/` (08.04)
- `/catalog/teplicy/pryamostennye/teplitsa-azt-pavilon/?erid=...` (12.04) ← **рекламный URL с erid выпал как NOT_CANONICAL**

**Свежие HTTP_ERROR 404 за 08–12.04:**
- `/catalog/teplicy/azt-lyuminiy-pod-steklo-2-2-4-metra/`, `-2-5-6-metrov/`, `-3-6-metrov-t-obraznoy/`
- `/catalog/teplicy/teplitsa-azt-20-20/`, `-20-30/`, `-fermerskaya-next/`, `-kapelyusha-lyuks/`
- `/catalog/teplicy/teplitsa-azt-lyuks/?erid=3MtFQRkqfB2huzBcHHttGDZbm2gFPT` ← рекламный URL 404

**Свежие REDIRECT_NOTSEARCHABLE за 08.04 (пермский блок массово):**
- `/prm/catalog/`, `/prm/delivery/`, `/prm/reviews/`, `/prm/policy/`
- `/prm/catalog/teplicy/pryamostennye/`, `/prm/catalog/teplicy/teplitsa-azt-fermerskaya-next/`, `/prm/catalog/teplicy/teplitsa-azt-premium/`
- `/prm/catalog/besedki/besedka-azt-gribok/`, `/prm/catalog/parniki/parnik-azt-khlebnitsa/`
- `/prm/catalog/komplektuyushchie/fundament-dlya-teplitsy-brus-100kh100-mm-/`
- `/prm/catalog/teplicy/azt-lyuminiy-pod-steklo-2-5-6-metrov/`
- `/prm/news/pochemu-polikarbonatnye-teplicy-ostayutsya-samym-praktichnym-resheniem/`
- `/prm/portfolio/teplitsa-iz-alyuminievogo-profilya-pod-klyuch/` (05.04)

**Indexing history 10–15.04:**
- HTTP_2XX: 199 → 207 → 131 → 118 → 113 → 110 (частота обхода падает)
- HTTP_4XX: 27 → 4 → 11 → 10 → 8 → 12 (404 продолжают)
- HTTP_3XX: 30 → 7 → 18 → 9 → 8 → 13 (редиректы продолжают)

**Important URLs:** в Вебмастере как "важный URL" помечен только `/`. Другие посадочные не добавлены — это тоже стоит поправить.

### 20:50 — Промежуточные выводы
- Канониклы: проблема **продолжается**, за 8 дней после отчёта выпало ещё 47 страниц по NOT_CANONICAL/LOW_QUALITY/REDIRECT/HTTP_ERROR
- Битая ссылочная масса: по sample новых URL после 06.04 не видно, но история ещё не обновилась (ждём следующую точку broken_links_history после 03.04)
- Главное улучшение: NO_METRIKA_COUNTER_BINDING ушла — связка Метрики восстановлена (важная задача P0.1 сделана)
- Рекламные URL с `erid` продолжают генерировать проблемы (404 + NOT_CANONICAL) — это вопрос 4 из отчёта

## Что ещё можно проверить
1. **Рекламные URL с erid** (пункт 5 P0 в отчёте + вопрос 4) — в Search Events продолжают выпадать. Нужно собрать все URL с `?erid=` и сверить с рекламными кампаниями агентства.
2. **Popular queries / query_history** после 16.04 — должны восстановиться цифры после связки Метрики (нули 07.04–16.04). Проверить через ~3-5 дней.
3. **Important URLs** — в Вебмастере помечен только `/`. Стоит добавить ключевые посадочные (`/catalog/teplicy/`, `/catalog/teplicy/steklyannye/`, региональные `/prm/`, `/izh/`, `/ekb/`, `/tmn/` после выбора модели).
4. **Сверка sitemap** после 15.04 — последний доступ 15.04, пересборка не делалась. Можно проверить позже.
5. **LOW_QUALITY кластер** — 7 событий из отчёта + новые (`/catalog/komplektuyushchie/` от 16.04, `/prm/catalog/teplicy/arochnye/teplitsa-azt-20-40/` от 14.04). Стоит разобрать отдельно — какие именно URL и почему.
6. **Региональность `/tmn/`** — в Search Events появились `/tmn/teplitsa-azt-kapelyusha-lyuks-s-avtomaticheskimi-fortochkami/` (APPEARED 05.04), `/tmn/actions/rassrochka/` (APPEARED 31.03) — тюменский блок пока не выпадает, но риск тот же. Мониторить.
7. **DUPLICATE_CONTENT_ATTRS** (P1) — всё ещё PRESENT с 08.04. Не разобрана.
8. **NOT_MOBILE_FRIENDLY** (P1) — всё ещё PRESENT с 02.04. Не разобрана.
9. **broken_links_history** — следующая точка снимка должна появиться ~18–20.04 (интервал снимков 10-11 дней). Когда появится — можно судить, остановился ли рост битых ссылок в абсолютных числах.

---

## Итоги
- **Выполнено:** сверены текущие данные Вебмастера с отчётом от 16.04
- **Главный вывод:** 2 из 5 P0-задач частично двинулись (P0.1 Метрика — сделано; P0.2 битые ссылки — рост остановлен в sample, но история подтвердит позже), P0.3 канониклы — **нет, продолжают выкидывать региональные URL**
- **В память:** ничего нового сохранять не требуется — состояние отражено в заметке vault

