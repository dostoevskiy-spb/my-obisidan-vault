---
name: Multi-agent Telegram architecture
description: Future plan for splitting single Бадян agent into topic-specific agents in Telegram threads
type: project
---

Павел хочет позже распилить единого агента Бадян на мульти-агентную систему в Telegram:
- Telegram канал с тредами: личный, семейный, рабочий, рецепты, праздники, знания
- Каждый тред → свой agent с фокусом, но shared Obsidian vault
- OpenClaw bindings по peer/topic ID

Входящие в Telegram могут быть: фото еды (калории), аудио, URL, YouTube, скриншоты цитат из книг, новости, пересланные сообщения, вопросы, задачи — всё что угодно.

**Why:** Один агент не масштабируется по контекстам — семейные дела и рабочие задачи мешают друг другу.

**How to apply:** Сейчас строим всё на одном агенте, но архитектура skills и vault должна быть готова к разделению. Skills shared, AGENTS.md per-agent.
