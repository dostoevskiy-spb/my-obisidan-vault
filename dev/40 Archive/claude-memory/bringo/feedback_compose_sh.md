---
name: ТОЛЬКО ./compose.sh — НИКОГДА docker compose
description: КРИТИЧНО — всегда ./compose.sh {command}, никогда docker compose напрямую. Это касается up, down, build, exec, logs, config, run, restart и ЛЮБЫХ compose-команд.
type: feedback
---

**НИКОГДА** не использовать `docker compose` напрямую в проекте Bringo.
**ВСЕГДА** использовать `./compose.sh {command}`.

**Why:** Проект использует сабмодули и сложную конфигурацию. `compose.sh` корректно устанавливает DOCKER_SSH_AUTH_SOCK и другие переменные. Прямой вызов `docker compose` ломает конфигурацию и вызывает ошибки.

**How to apply:** В КАЖДОМ случае где нужна compose-команда — `./compose.sh`. Примеры:
```bash
./compose.sh up -d
./compose.sh build api
./compose.sh exec api bash
./compose.sh logs -f api
./compose.sh config --services
./compose.sh down
./compose.sh restart api
```

Это правило без исключений.
