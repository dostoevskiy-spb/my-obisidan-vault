# Сессия: AZT — проверка техничких правок
**Дата:** 2026-04-20 17:17
**Цель:** Проверить, действительно ли поправили техничку на azt-teplica.ru по P0/P1 из отчёта 2026-04-14

---

## Лог

### 17:17 — Начало
- Задача: перепроверить P0/P1 блок технических правок после заявления "поправили"
- Контекст: отчёт 2026-04-14 описывал sitemap с 404.php/thank.php, битые URL статей/кейсов, canonical с двойным слешем, региональные title с пермским заголовком, мусорные meta, HTML entities в schema
- План: curl по ключевым URL, парсинг sitemap, проверка canonical/title на региональных, schema на карточке, наличие живых страниц

### 17:25 — Sitemap проверен
- Что: прочитаны sitemap.xml, sitemap-files.xml, sitemap-iblock-9.xml, sitemap-iblock-20.xml
- Результат: полностью пересобран, lastmod 2026-04-20T11:41
- Детали:
  - sitemap-files: 8 живых URL (/, about, catalog, contacts, delivery, news, portfolio, reviews). Нет 404.php/thank.php ✓
  - sitemap-iblock-9: 6 статей все с префиксом /news/... ✓
  - sitemap-iblock-20: 6 кейсов все с префиксом /portfolio/... ✓
  - НЕТ privacy и policy в sitemap (в отчёте просили добавить)

### 17:30 — Canonical главной
- Что: curl главной, grep canonical
- Результат: `https://azt-teplica.ru/` без двойного слеша ✓
- Детали: но тег `<link rel="canonical">` дублируется ДВАЖДЫ в HTML — баг шаблона

### 17:35 — Региональные страницы
- Что: curl /ekb/, /tyumen/, /izh/
- Результат: title исправлен на города ✓, canonical ещё сломан ✗
- Детали:
  - /ekb/: title "Теплицы в Екатеринбурге...", H1 про Екатеринбург, но canonical=`https://azt-teplica.ru//` (двойной слеш не убрали)
  - /izh/: title "Теплицы в Ижевске...", H1 про Ижевск, canonical=`https://azt-teplica.ru//` (тот же баг)
  - /tyumen/: 404! title "Страница не найдена", при этом canonical=/tyumen/. Раздел удалили или сломан
  - hreflang не найден ни на одной региональной

### 17:40 — 404.php и thank.php
- Что: проверка индексируемости
- Результат: 404.php исправлен ✓, thank.php НЕ исправлен ✗
- Детали:
  - 404.php: HTTP 404 + `<meta name="robots" content="noindex, follow">` + title "Страница не найдена" — корректно
  - thank.php: HTTP 200 + `<meta name="robots" content="index, follow">` + `<title>Title</title>` (пустой) — всё ещё мусор в индексе

### 17:45 — Внутренние ссылки с главной
- Что: grep ссылок на статьи и /prm/
- Результат: статьи починены ✓, /prm/ редиректы остались ⚠️
- Детали:
  - Ссылки на статьи: /news/kak-vybrat-teplitsu... — корректно с префиксом /news/
  - Ссылки `/prm/catalog/teplicy/`, `/prm/about/` и т.д. отдают 301 → редирект. Двойной `/prm/catalog/catalog/` (из исходного отчёта) больше не встречается
  - Редирект-цепочки с главной — слабый перелинк, но не критично

### 17:50 — Product schema на АЗТ Премиум
- Что: grep ld+json
- Результат: НЕ расширена, HTML entity остался ✗
- Детали: schema содержит только name + offers (priceCurrency, availability, eligibleRegion). Нет description, image, brand, sku, url, price (числового). Имя загрязнено: `"name": "Теплица &quot;АЗТ Премиум&quot;"` — HTML entity `&quot;` не заменили на чистые кавычки

### 17:55 — Privacy/policy, meta keywords, категории
- Что: grep заглушек и meta
- Результат: privacy/policy очищены ✓, meta keywords НЕ удалён ✗
- Детали:
  - `/privacy/`: заглушки "ваш-сайт" не найдены
  - `/policy/`: заглушки "Образец Описание" не найдены
  - Главная: `<meta name="keywords" content=".">` остался (было просили удалить)
  - Категории: OG у /catalog/besedki/ и /catalog/gryadki/ корректно про беседки и грядки. Body проверять глубже не стал

---

## Итоги

### Что действительно починили (P0 и часть P1)
- **Sitemap** полностью пересобран (4 файла, lastmod 2026-04-20): нет 404.php/thank.php, статьи с /news/, кейсы с /portfolio/, добавлены about/contacts/delivery/news/portfolio/reviews
- **Canonical главной** исправлен: `https://azt-teplica.ru/` (без двойного слеша)
- **Региональные страницы:** title и H1 теперь про города (Екатеринбург, Ижевск), OG тоже
- **404.php:** отдаёт 404 + noindex
- **Ссылки с главной на статьи:** префикс /news/ добавлен
- **Privacy/policy:** заглушки удалены
- **Двойной /prm/catalog/catalog/** исчез

### Что НЕ исправлено (критичное)
- **Canonical региональных** = `https://azt-teplica.ru//` (двойной слеш остался на /ekb/, /izh/). Self-canonical не внедрили
- **thank.php** = 200 OK + `index, follow` + `<title>Title</title>`. Из sitemap убрали, но страница всё ещё индексируется как мусор
- **/tyumen/** = 404. Либо раздел удалили, либо сломали — canonical указывает на /tyumen/, но страница отдаёт "Страница не найдена"
- **Product schema** на карточке АЗТ Премиум не расширена (только name+offers, HTML entity `&quot;` в name)
- **meta keywords="."** на главной остался
- **hreflang** нет ни на одной региональной
- **privacy/policy** не добавлены в sitemap
- **Дубль `<link rel="canonical">`** на всех страницах (по 2 тега)

