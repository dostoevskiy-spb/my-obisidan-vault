---
name: OpenClaw setup
description: OpenClaw workspace is separate from vault, config drafts stored in Бадян project
type: project
---

OpenClaw workspace stays at `~/.openclaw/workspace/` (default). Config files (SOUL.md, AGENTS.md, etc.) live there, NOT in the vault root.

Config drafts are stored in vault as notes: `10 Projects/Бадян/`. Each *-draft.md contains the config content wrapped in a code block. Deploy by extracting content to workspace.

**Why:** User explicitly chose separate storage — vault is pure Obsidian, OpenClaw workspace is its own thing. Бадян project is for iteration on configs.
**How to apply:** Never put OpenClaw config files in vault root. Reference Бадян project for OpenClaw-related work.
