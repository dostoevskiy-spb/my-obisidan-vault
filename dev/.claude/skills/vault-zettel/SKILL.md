---
name: vault-zettel
description: Create atomic Zettelkasten notes from ideas
triggers:
  - user describes an idea or insight
  - user says "zettel", "заметка-идея", "атомарная заметка"
---

# vault-zettel

Создание атомарных заметок в Zettelkasten.

## Workflow

1. Distill the idea to ONE core concept
2. Search vault for related notes
3. Create note in `50 Zettelkasten/`:

```yaml
---
type: zettel
tags: [<relevant tags>]
source: "<where the idea came from>"
related:
  - "[[Related Note 1]]"
  - "[[Related Note 2]]"
created: YYYY-MM-DD
---
```

4. Write the note:
   - Title: the core idea as a statement (not a question)
   - Body: explanation in own words, 1-3 paragraphs
   - Related notes section with wiki-links

5. Update related notes — add backlink to new zettel

## Principles

- **Atomicity**: one idea per note
- **Own words**: rewrite, don't copy
- **Connections**: always link to existing notes
- **Title as statement**: "REST API should be stateless" not "REST API"

## Rules
- Always create in `50 Zettelkasten/`
- Always search for related notes first
- Title should be a clear statement of the idea
- Keep notes concise (1-3 paragraphs)
