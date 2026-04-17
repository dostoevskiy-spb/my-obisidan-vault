---
type: project
tags: [azt, yandex-webmaster, follow-up, seo, owner]
created: 2026-04-17
---

# AZT — Follow-up Яндекс Вебмастер

Дата: 17 апреля 2026  
Источник: Яндекс Вебмастер (MCP, read-only)  
База сравнения: [[AZT — Итоговый анализ данных Яндекс Вебмастер 2026-04-16]]

## 1. Цель

Проверить, продолжаются ли через сутки после отчёта две ключевые проблемы:

- выкидывание страниц из индекса по канониклам,
- генерация битой ссылочной массы.

Дополнительно — зафиксировать, что изменилось за сутки и какие блоки ещё можно проверить.

---

## 2. Что изменилось за сутки

| Показатель | 16.04 | 17.04 | Дельта |
|---|---:|---:|---:|
| SQI | `140` | `140` | без изменений |
| Страниц в поиске | `138` | `138` | без изменений |
| Исключённых | `71` | `65` | `-6` |
| Активных POSSIBLE_PROBLEM | `2` | `1` | `-1` |
| Активных RECOMMENDATION | `1` | `1` | без изменений |
| Broken internal links (sample count) | `428` | `428` | без изменений |

Диагностика:

| Код | 16.04 | 17.04 |
|---|---|---|
| `NO_METRIKA_COUNTER_BINDING` | `PRESENT` | `ABSENT` (обновлено `2026-04-16T16:41`) |
| `DUPLICATE_CONTENT_ATTRS` | `PRESENT` | `PRESENT` |
| `NOT_MOBILE_FRIENDLY` | `PRESENT` | `PRESENT` |

Итог:

> Главное положительное изменение — связка Яндекс Метрики восстановлена. Это закрывает P0.1 из отчёта. Остальная диагностика не двинулась.

---

## 3. Канониклы и исключения из индекса — **проблема продолжается**

За `2026-04-08` — `2026-04-16` Search Events зафиксировал баланс появления/исключения URL:

| Дата | APPEARED | REMOVED | Баланс |
|---|---:|---:|---:|
| 2026-04-08 | `16` | `22` | `-6` |
| 2026-04-09 | `0` | `11` | `-11` |
| 2026-04-12 | `1` | `9` | `-8` |
| 2026-04-14 | `2` | `4` | `-2` |
| 2026-04-16 | `1` | `1` | `0` |
| **Итого** | `20` | `47` | **`-27`** |

Динамика затухающая, но отрицательная: после 7 апреля в поиск вернулось 20 URL, выпало 47. В поисковой выдаче реакции пока нет — 138 URL держится стабильно, часть новых страниц компенсирует выпадающие.

### 3.1. Свежие NOT_CANONICAL (08.04 — 14.04)

Региональные URL продолжают массово отдавать canonical на корневые, что приводит к исключению из поиска:

| URL | Canonical цель | Дата REMOVED |
|---|---|---|
| `/izh/` | `/` | `2026-04-14` |
| `/izh/delivery/` | `/delivery/` | `2026-04-14` |
| `/izh/portfolio/` | `/portfolio/` | `2026-04-14` |
| `/izh/about/` | `/about/` | `2026-04-12`, `2026-04-03` |
| `/izh/store/` | `/store/` | `2026-04-09` |
| `/izh/catalog/komplektuyushchie/bokovaya-fortochka/` | `/catalog/komplektuyushchie/bokovaya-fortochka/` | `2026-04-09` |
| `/izh/catalog/komplektuyushchie/fundament-dlya-teplitsy-brus-100kh100-mm-/` | корневой | `2026-04-09` |
| `/izh/catalog/komplektuyushchie/profil-soedenitelnyy/` | корневой | `2026-04-09` |
| `/izh/catalog/komplektuyushchie/profil-tortsevoy/` | корневой | `2026-04-09` |
| `/izh/catalog/komplektuyushchie/termoshayba/` | корневой | `2026-04-09` |
| `/izh/catalog/teplicy/arochnye/teplitsa-azt-premium/` | корневой | `2026-04-09` |
| `/izh/catalog/teplicy/steklyannye/` | корневой | `2026-04-08` |
| `/ekb/actions/rassrochka/` | `/actions/rassrochka/` | `2026-04-08` |
| `/catalog/teplicy/pryamostennye/teplitsa-azt-pavilon/?erid=…` | рекламный URL | `2026-04-12` |

### 3.2. Свежие HTTP_ERROR 404 (08.04 — 12.04)

| URL | Статус | Дата |
|---|---|---|
| `/catalog/teplicy/azt-lyuminiy-pod-steklo-2-2-4-metra/` | `404` | `2026-04-12` |
| `/catalog/teplicy/azt-lyuminiy-pod-steklo-2-5-6-metrov/` | `404` | `2026-04-12` |
| `/catalog/teplicy/azt-lyuminiy-pod-steklo-3-6-metrov-t-obraznoy-formy-s-tamburom/` | `404` | `2026-04-12` |
| `/catalog/teplicy/teplitsa-azt-20-20/` | `404` | `2026-04-12` |
| `/catalog/teplicy/teplitsa-azt-20-30/` | `404` | `2026-04-12` |
| `/catalog/teplicy/teplitsa-azt-20-40/` | `404` | `2026-04-08` |
| `/catalog/teplicy/teplitsa-azt-fermerskaya-next/` | `404` | `2026-04-12` |
| `/catalog/teplicy/teplitsa-azt-fermerskaya-lyuks/` | `404` | `2026-04-08` |
| `/catalog/teplicy/teplitsa-azt-kapelyusha-lyuks/` | `404` | `2026-04-12` |
| `/catalog/teplicy/teplitsa-azt-kapelyusha/` | `404` | `2026-04-08` |
| `/catalog/teplicy/teplitsa-azt-kottedzh/` | `404` | `2026-04-08` |
| `/catalog/teplicy/teplitsa-azt-premium/` | `404` | `2026-04-08` |
| `/catalog/teplicy/teplitsa-azt-20-20-shirina-2-metra/` | `404` | `2026-04-08` |
| `/catalog/teplicy/teplitsa-azt-lyuks/?erid=3MtFQRkqfB2huzBcHHttGDZbm2gFPT` | `404` | `2026-04-09` |

### 3.3. Свежие REDIRECT_NOTSEARCHABLE (массово `/prm/`, 08.04)

| URL | Цель редиректа |
|---|---|
| `/prm/catalog/` | `/catalog/` |
| `/prm/delivery/` | `/delivery/` |
| `/prm/reviews/` | `/reviews/` |
| `/prm/policy/` | `/policy/` |
| `/prm/catalog/teplicy/pryamostennye/` | корневой |
| `/prm/catalog/teplicy/pryamostennye/teplitsa-azt-pavilon/` | корневой |
| `/prm/catalog/teplicy/teplitsa-azt-fermerskaya-next/` | корневой |
| `/prm/catalog/teplicy/teplitsa-azt-premium/` | корневой |
| `/prm/catalog/teplicy/azt-lyuminiy-pod-steklo-2-5-6-metrov/` | корневой |
| `/prm/catalog/besedki/besedka-azt-gribok/` | корневой |
| `/prm/catalog/parniki/parnik-azt-khlebnitsa/` | корневой |
| `/prm/catalog/komplektuyushchie/fundament-dlya-teplitsy-brus-100kh100-mm-/` | корневой |
| `/prm/news/pochemu-polikarbonatnye-teplicy-ostayutsya-samym-praktichnym-resheniem/` | корневой |
| `/prm/portfolio/teplitsa-iz-alyuminievogo-profilya-pod-klyuch/` | корневой (05.04) |

Заключение по разделу:

> Источник проблемы не устранён. Bitrix-шаблоны продолжают отдавать canonical на корневые URL для региональных страниц `/izh/`, `/ekb/`, пермский блок `/prm/` массово редиректит на корень. Рекламные URL с `?erid=` дают одновременно 404 и NOT_CANONICAL. До внедрения единой региональной модели и фикса canonical выпадение продолжится.

---

## 4. Битая ссылочная масса — рост остановлен в выборке, но история ещё не обновилась

Sample из `broken_internal_links` сегодня:

| Показатель | 16.04 | 17.04 |
|---|---:|---:|
| Count | `428` | `428` |

История `broken_links_history` возвращает те же 3 точки:

| Дата | `DISALLOWED_BY_USER` | `SITE_ERROR` |
|---|---:|---:|
| `2026-03-14` | `72` | `1` |
| `2026-03-25` | `112` | `1` |
| `2026-04-03` | `213` | `2` |

Новой точки истории не появилось. Интервал между снимками ~10–11 дней, значит следующая точка ожидается `2026-04-14` — `2026-04-15`. Пока её нет, однозначно утверждать «рост остановился» нельзя.

По sample свежих `discovery_date` после `2026-04-02` не встречается, самые свежие `source_last_access_date` — `2026-04-06`. Это может означать, что источник битых ссылок в шаблонах временно замолчал или просто не попал в текущий sample.

Заключение по разделу:

> Источник битых ссылок шаблонно не исправлен, но в выборке за последние 2 недели новых `discovery_date` не добавилось. Финальный ответ дадут ближайшее обновление истории (~`2026-04-14` — `2026-04-15`). Если `DISALLOWED_BY_USER` не превысит `213`, можно зафиксировать остановку роста. Если превысит — шаблоны продолжают генерировать битые URL.

---

## 5. Индексация 10.04 — 15.04

| Дата | HTTP_2XX | HTTP_3XX | HTTP_4XX |
|---|---:|---:|---:|
| `2026-04-10` | `199` | `30` | `27` |
| `2026-04-11` | `207` | `7` | `4` |
| `2026-04-12` | `131` | `18` | `11` |
| `2026-04-13` | `118` | `9` | `10` |
| `2026-04-14` | `113` | `8` | `8` |
| `2026-04-15` | `110` | `13` | `12` |

Частота обхода `HTTP_2XX` снижается с 207 до 110 за 5 дней. `HTTP_4XX` продолжают фиксироваться ежедневно. Если связывать со снижением доверия Яндекса к URL-структуре — логично: выше доля ошибок → ниже краулинговый бюджет.

---

## 6. Что ещё можно проверить

### 6.1. Рекламные URL с erid (P0.5)

В Search Events зафиксированы минимум 2 проблемных рекламных URL:

- `/catalog/teplicy/teplitsa-azt-lyuks/?erid=3MtFQRkqfB2huzBcHHttGDZbm2gFPT` — `HTTP_ERROR 404` на `2026-04-09`;
- `/catalog/teplicy/pryamostennye/teplitsa-azt-pavilon/?erid=3MtFQRkqfB2huzBcHHttGDZbm2faGn` — `NOT_CANONICAL` на `2026-04-12`, canonical со слешем на конце `?erid=.../` (лишний слеш).

Это совпадает с вопросом 4 из отчёта. До ответа агентства имеет смысл собрать все `?erid=` URL из `indexing_samples` и сверить с рекламными кампаниями.

### 6.2. Popular queries после восстановления Метрики

Связка Метрики восстановлена `2026-04-16T16:41`. В документации Яндекса обновление поисковых данных может занимать до 2 недель. Контрольная проверка `get_popular_queries` и `get_query_history` целесообразна `2026-04-22` и далее — должна появиться ненулевая статистика после `2026-04-07`.

### 6.3. Important URLs

В Вебмастере помечен как важный URL только `/`. Для мониторинга изменений стоит добавить ключевые посадочные:

- `/catalog/teplicy/`, `/catalog/teplicy/arochnye/`, `/catalog/teplicy/steklyannye/`, `/catalog/teplicy/pryamostennye/`, `/catalog/teplicy/dvuskatnaya/`;
- карточки товаров `/catalog/teplicy/arochnye/teplitsa-azt-20-40/`, `/teplitsa-azt-lyuks/`, `/teplitsa-azt-premium/`;
- `/actions/rassrochka/`, `/portfolio/`, `/delivery/`;
- после выбора региональной модели — соответствующие `/prm/`, `/izh/`, `/ekb/`, `/tmn/`.

Это задача владельца Вебмастера — через интерфейс добавить URL в «Важные страницы».

### 6.4. LOW_QUALITY — отдельный разбор

За период видны 3 новых `LOW_QUALITY` вне списка из отчёта:

- `/catalog/komplektuyushchie/` — `2026-04-16`;
- `/prm/catalog/teplicy/arochnye/teplitsa-azt-20-40/` — `2026-04-14`;
- `/prm/catalog/komplektuyushchie/komplekt-6-7-peremychka/` — `2026-04-09`;
- `/prm/catalog/komplektuyushchie/profil-soedenitelnyy/` — `2026-04-09`.

Нужно отдельно разобрать, что именно Яндекс считает низким качеством: тонкий контент, шаблонный title/description, отсутствие уникального H1, мало текстового описания. Это P1 из отчёта.

### 6.5. Региональный блок `/tmn/`

В Search Events зафиксированы `APPEARED_IN_SEARCH` для Тюмени:

- `/tmn/teplitsa-azt-kapelyusha-lyuks-s-avtomaticheskimi-fortochkami/` — `2026-04-05`;
- `/tmn/actions/rassrochka/` — `2026-03-31`.

Пока тюменский блок не выпадает, но при той же шаблонной логике canonical риск аналогичный. Мониторить до внедрения региональной модели.

### 6.6. DUPLICATE_CONTENT_ATTRS и NOT_MOBILE_FRIENDLY (P1)

Обе активные проблемы не разобраны. Ни по одной нет прогресса за неделю. Соответствующие P1-задачи из отчёта остаются открытыми.

### 6.7. Следующая точка broken_links_history

Ожидается `2026-04-14` — `2026-04-15`. Если она так и не появится к концу недели — стоит проверить, продолжаются ли снимки вообще, или связать с обновлением региона/других настроек.

---

## 7. Выводы

1. Канониклы продолжают выкидывать страницы из индекса. За `2026-04-08` — `2026-04-16` баланс `-27` URL, основная доля — региональные `/izh/`, `/ekb/`, массовые редиректы `/prm/`. Рекламные URL с `erid` вносят вклад дополнительно.
2. Битая ссылочная масса в выборке стабилизирована на `428`, но следующей точки истории пока нет. Фиксировать остановку рано. В свежих записях `discovery_date` моложе `2026-04-02` в sample не встречается.
3. P0.1 (связка Метрики) выполнена. Это единственная задача из отчёта, по которой есть зафиксированный прогресс.
4. P0.2 (шаблоны битых ссылок), P0.3 (региональная модель и canonical), P0.4 (пересборка sitemap), P0.5 (рекламные URL) — без изменений по данным Вебмастера.
5. Доверие к URL-структуре снижается: дневной `HTTP_2XX` обхода упал с `207` до `110` за 5 дней при стабильной частоте `HTTP_4XX`.
6. Дополнительно стоит собрать список рекламных URL с `erid`, добавить важные посадочные в Вебмастер, разобрать `LOW_QUALITY` кластер и держать под наблюдением тюменский блок.
