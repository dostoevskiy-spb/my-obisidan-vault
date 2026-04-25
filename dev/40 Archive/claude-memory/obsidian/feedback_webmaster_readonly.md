---
name: Yandex Webmaster — только чтение
description: КРИТИЧНО — в Яндекс Вебмастере выполнять ТОЛЬКО read-only действия. Никогда не добавлять/удалять sitemap, не отправлять URL на переобход, не менять настройки хоста через MCP или API.
type: feedback
originSessionId: 21cba679-a2bd-4695-ba6e-e5d2a84fe313
---
В Яндекс Вебмастере (MCP `yandex-webmaster` и любые API-вызовы) — **ТОЛЬКО чтение**.

**Why:** Любое write-действие (добавление sitemap, submit recrawl, удаление URL, изменение настроек хоста) может повлиять на боевой сайт. Такие действия выполняет только владелец или ответственный — вручную, через интерфейс.

**How to apply:** Перед вызовом любого MCP-инструмента Вебмастера проверять: это `get`, `list`, `query` (чтение) или `add`, `submit`, `delete`, `verify` (запись)? Запись — НЕ вызывать. Если нужно что-то изменить — описать действие текстом и передать владельцу для ручного выполнения.

Конкретно запрещено:
- `ywm_add_sitemap`, `ywm_delete_sitemap`
- `ywm_submit_recrawl`
- `ywm_add_host`, `ywm_delete_host`
- `ywm_verify_host`
- `ywm_add_original_text`, `ywm_delete_original_text`
- `ywm_batch_add_feeds`, `ywm_batch_remove_feeds`
- `ywm_start_feed_upload`

Разрешено всё, что начинается с `ywm_get_`, `ywm_list_`, `ywm_query_`.
