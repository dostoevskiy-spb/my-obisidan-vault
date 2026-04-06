---
name: vault-capture
description: Capture URLs, quotes, and ideas into the Obsidian vault Inbox
triggers:
  - user asks to save a URL, link, or article
  - user shares a quote or idea to remember
  - user says "capture", "save", "запомни", "сохрани"
---

# vault-capture

Захват контента в Inbox vault.

## Workflow

1. Determine content type:
   - URL → extract title, create literature note
   - Quote → create note with quote and source
   - Idea → create note with the idea

2. Create note in `01 Inbox/` with proper frontmatter:

```yaml
---
type: literature  # or zettel for ideas
tags: [inbox]
source: "<URL or source>"
created: YYYY-MM-DD
---
```

3. Add content:
   - For URLs: title as heading, URL in source field, key points if extractable
   - For quotes: quote in blockquote, source attribution
   - For ideas: idea as main content

4. Add wiki-links to related existing notes (search vault first)

5. Confirm to user what was captured and where

## Rules
- Always create in `01 Inbox/`
- Always add frontmatter
- Always search for related notes and add wiki-links
- Filename: descriptive, lowercase with hyphens
