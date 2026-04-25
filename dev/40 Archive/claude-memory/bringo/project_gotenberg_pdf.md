---
name: gotenberg-pdf-migration
description: Планируется замена Dompdf на Gotenberg (headless Chrome) для конверсии HTML→PDF финансовых отчётов. Gotenberg будет отдельным сервисом — контейнер в Docker Compose локально, Deployment+Service в Kubernetes на prod/stage.
type: project
---

## Контекст
Текущий HtmlToPdfConverter использует Dompdf, который плохо рендерит разнородный HTML от Companies House (обрезанные отступы, слипшиеся таблицы, пустые страницы). Решено заменить на Gotenberg — stateless сервис с Chrome внутри.

## Архитектура
- Локально: compose.d/gotenberg/ — Docker Compose сервис
- Prod/Stage: helmfile.d/ — Helm chart для Gotenberg Deployment + Service
- Backend обращается по URL из env: `GOTENBERG_URL=http://gotenberg:3000`
- Вызов синхронный (1-3 сек), результат кэшируется в S3 навсегда

## Важно
- compose.d — только для локальной Docker-сборки
- На prod/stage — Kubernetes, конфиг через helmfile.d/
- helmfile.d/values/*_secrets.yaml зашифрованы SOPS — не редактировать
