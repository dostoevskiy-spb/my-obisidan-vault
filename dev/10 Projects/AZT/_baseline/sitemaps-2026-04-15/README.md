---
type: project
tags: [azt, sitemap, snapshot, baseline]
created: 2026-04-15
---

# Sitemaps snapshot — 15 апреля 2026

Снимок всех XML-карт сайта `azt-teplica.ru` на момент **15 апреля 2026**. Скачано напрямую с сервера через curl. Это baseline для сверки после техфиксов.

## Содержимое папки

21 файл, **228 URL-записей** во всех child sitemaps.

### Структура

```
sitemap.xml                              ← индексный (20 ссылок на child sitemaps)
│
├── ОСНОВНЫЕ (5 файлов, 57 URL)
│   ├── sitemap-files.xml                7 URL — служебные/файлы
│   ├── sitemap-iblock-4.xml             37 URL — каталог товаров
│   ├── sitemap-iblock-9.xml             4 URL — статьи блога (битые!)
│   ├── sitemap-iblock-12.xml            3 URL — акции (битые!)
│   └── sitemap-iblock-20.xml            6 URL — промо-лендинги (битые!)
│
├── РЕГИОНАЛЬНЫЕ — Тюмень (5 файлов, 57 URL)
│   ├── sitemap-tmn-sitemap-files.xml
│   ├── sitemap-tmn-sitemap-iblock-4.xml
│   ├── sitemap-tmn-sitemap-iblock-9.xml
│   ├── sitemap-tmn-sitemap-iblock-12.xml
│   └── sitemap-tmn-sitemap-iblock-20.xml
│
├── РЕГИОНАЛЬНЫЕ — Екатеринбург (5 файлов, 57 URL)
│   ├── sitemap-ekb-sitemap-files.xml
│   ├── sitemap-ekb-sitemap-iblock-4.xml
│   ├── sitemap-ekb-sitemap-iblock-9.xml
│   ├── sitemap-ekb-sitemap-iblock-12.xml
│   └── sitemap-ekb-sitemap-iblock-20.xml
│
└── РЕГИОНАЛЬНЫЕ — Ижевск (5 файлов, 57 URL)
    ├── sitemap-izh-sitemap-files.xml
    ├── sitemap-izh-sitemap-iblock-4.xml
    ├── sitemap-izh-sitemap-iblock-9.xml
    ├── sitemap-izh-sitemap-iblock-12.xml
    └── sitemap-izh-sitemap-iblock-20.xml
```

## Известные проблемы

Согласно аудиту 2026-04-12, среди 56 уникальных URL — **14 битых** (отдают 404):

**Битые URL в `sitemap-iblock-9.xml` (статьи)** — 4 из 4:
- `/kak-vybrat-teplitsu-iz-polikarbonata-podrobnoe-rukovodstvo-pered-pokupkoy/`
- `/usilennye-teplitsy-iz-polikarbonata-reshenie-dlya-regionov-so-snegovoy-nagruzkoy/`
- `/kak-uvelichit-urozhaynost-v-teplitse-prakticheskie-metody-dlya-maksimalnogo-rezultata/`
- `/teplitsy-dlya-dachi-kakuyu-model-vybrat-dlya-komfortnogo-vyrashchivaniya/`

Должны быть в `/news/...`. Реальные URL живые, но в sitemap указаны без префикса.

**Битые URL в `sitemap-iblock-12.xml` (акции)** — 3 из 3:
- `/actions/rassrochka/`
- `/actions/khranenie/`
- `/actions/dostavka/`

**Битые URL в `sitemap-iblock-20.xml` (промо-лендинги)** — 6 из 6:
- `/promyshlennaya-teplitsa/`
- `/teplitsa-iz-alyuminievogo-profilya-pod-klyuch/`
- `/teplitsa-azt-kottedzh-iz-otsinkovannoy-profilnoy-truby-20kh40-mm/`
- `/parnik-lastochka-po-individualnomu-proektu/`
- `/teplitsa-azt-kapelyusha-lyuks-s-avtomaticheskimi-fortochkami/`
- `/teplitsa-azt-pavilon-dvoynaya-duga-na-krovle-krabovoe-soedinenie/`

**Битые URL в `sitemap-files.xml`** — 1 из 7:
- `/404.php` — служебная страница ошибки попала в sitemap

Все эти 14 битых URL **умножаются на 4 региона** = **56 битых записей** в общей структуре sitemap-индекса.

## Реальные живые статьи (которые ДОЛЖНЫ быть в sitemap-iblock-9 вместо битых)

- `/news/montazh-teplitsy-svoimi-rukami-vs-ustanovka-pod-klyuch-chto-vygodnee-i-bezopasnee/`
- `/news/teplitsa-ili-parnik-v-chem-raznitsa-i-chto-vybrat-dlya-vashego-uchastka/`
- `/news/teplitsy-dlya-dachi-kakuyu-model-vybrat-dlya-komfortnogo-vyrashchivaniya/`
- `/news/kak-uvelichit-urozhaynost-v-teplitse-prakticheskie-metody-dlya-maksimalnogo-rezultata/`
- `/news/usilennye-teplitsy-iz-polikarbonata-reshenie-dlya-regionov-so-snegovoy-nagruzkoy/`
- `/news/kak-vybrat-teplitsu-iz-polikarbonata-podrobnoe-rukovodstvo-pered-pokupkoy/`

## Страницы НЕ в sitemap, но живые (нужно добавить)

- `/contacts/`
- `/delivery/`
- `/portfolio/`
- `/reviews/`
- `/catalog/polikarbonat/`
- `/catalog/gryadki/`
- `/actions/`
- `/policy/`
- `/privacy/`

## Что делать с этой папкой

1. **Сравнить после техфиксов.** Когда разработчик пересоберёт sitemap, скачать новую версию в папку `sitemaps-YYYY-MM-DD` и сделать diff с этой.
2. **Передать разработчику.** Конкретные битые URL списком — для проверки правильности новой генерации.
3. **Использовать как доказательство.** Если возникнет спор о масштабе проблемы (агентство или собственник скажут "не так уж и плохо"), можно показать конкретные XML с битыми URL.

## Метаданные

- Скачано: 2026-04-15 ~17:30 МСК через `curl` на VPN
- Источник: `https://azt-teplica.ru/sitemap.xml` и 20 child sitemaps
- Размер всех файлов: ~28 КБ
- Total URLs (со всеми региональными копиями): 228
- Уникальных URL: ~57

## Связанные документы

- [[AZT — Полный аудит 2026-04-12]] — детальный анализ битых URL
- [[AZT — Baseline Яндекс Вебмастер 2026-04-15]] — снимок метрик Вебмастера
- [[AZT — ТЗ для разработчика Bitrix 2026-04-13-codex]] — ТЗ на пересборку sitemap
