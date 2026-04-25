---
name: Vault structure
description: Obsidian vault uses PARA+Zettelkasten+Kill-List+Alerts with frontmatter conventions
type: project
---

Vault at `/home/pavel/dev/obsidian/dev/` uses combined PARA + Zettelkasten approach:
- 00 HUB (Dashboard, MOC Index), 01 Inbox, 10 Projects, 20 Areas, 30 Resources, 40 Archive, 50 Zettelkasten, 60 Kill-List (today/this-week/someday), 70 Alerts (Dashboard + triggers)
- Daily/, Weekly/, Templates/, Files/
- CLAUDE.md in vault root
- 7 skills in .claude/skills/, 3 commands in .claude/commands/
- All notes have YAML frontmatter with `type` field
- Wiki-links [[]] for connections between notes

**Why:** Pavel wants a systematic knowledge management system that AI agents can interact with.
**How to apply:** When working in this vault, follow CLAUDE.md conventions. New content goes to Inbox. Always use frontmatter and wiki-links.
