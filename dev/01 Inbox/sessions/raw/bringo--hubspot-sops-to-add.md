---
type: session-log-raw
project: bringo
source: /home/pavel/dev/www/bringo/bringo-co-uk/main/.claude/sessions/hubspot-sops-to-add.md
session_date: 2026-04-22
tags:
  - session-log
  - raw
  - bringo
created: 2026-04-26
status: unprocessed
---

# HubSpot — секреты для SOPS

Зашифровать одно и то же значение `HUBSPOT_ENCRYPTION_KEY` в четыре SOPS-файла. Значения в backend и backoffice **должны совпадать** — иначе токен, зашифрованный в backoffice UI, не расшифруется в backend handler'е.

## Ключ (plaintext)

```
HUBSPOT_ENCRYPTION_KEY=XPIjHclyS4fRk/wgDVUDvMPCQLE3zIL9fJbpkYRHzmY=
```

Это 32 случайных байта, base64-encoded (сгенерировано `php -r 'echo base64_encode(sodium_crypto_secretbox_keygen());'`). Если планируешь сгенерить свой — перегенерируй и прокинь во все 6 файлов ниже (оба .env файла компоуза + 4 SOPS-файла).

## Куда подложить в SOPS (под `commonSecretEnvs`)

1. `backend/helmfile.d/values/stg/ie/dc1/backend_secrets.yaml`
2. `backend/helmfile.d/values/prod/ie/dc1/backend_secrets.yaml`
3. `backoffice/helmfile.d/values/stg/ie/dc1/backoffice.secrets.yaml`
4. `backoffice/helmfile.d/values/prod/ie/dc1/backoffice.secrets.yaml`

В каждом файле добавить одну строку в секцию `commonSecretEnvs:` — рядом с остальными ключами. Пример для backend (до шифрования):

```yaml
commonSecretEnvs:
  # ...existing keys...
  APOLLO_API_KEY: <already encrypted>
  APOLLO_POSTBACK_API_SECRET: <already encrypted>
  HUBSPOT_ENCRYPTION_KEY: XPIjHclyS4fRk/wgDVUDvMPCQLE3zIL9fJbpkYRHzmY=
```

После `sops --encrypt --in-place backend_secrets.yaml` значение превратится в `ENC[AES256_GCM,…]` как у остальных ключей.

## Что НЕ идёт в SOPS

- `HUBSPOT_ENABLED` — обычный ConfigMap env, уже добавлен в `backend/helmfile.d/values/common/backend.yaml → commonEnvs`.
- Сам HubSpot Private App token — **не** в env и не в SOPS. Админ вводит его в backoffice UI (HubSpot CRM Settings), он сохраняется в `hubspot_config.access_token_encrypted` зашифрованным через `HUBSPOT_ENCRYPTION_KEY`.
