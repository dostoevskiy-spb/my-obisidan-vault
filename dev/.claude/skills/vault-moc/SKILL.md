---
name: vault-moc
description: Generate Maps of Content for vault topics
triggers:
  - user asks to create a map of content
  - user says "MOC", "карта контента", "навигация по теме"
---

# vault-moc

Генерация Maps of Content (MOC).

## Workflow

1. Identify the topic for MOC
2. Search vault for all related notes:
   - By content (grep)
   - By tags
   - By folder location
   - By wiki-link references

3. Categorize found notes into subtopics

4. Generate MOC in `00 HUB/`:

```yaml
---
type: moc
tags: [moc, <topic-tag>]
created: YYYY-MM-DD
---
```

5. Structure:

```markdown
# MOC: [Topic]

## Overview
Brief description of the topic area.

## Category 1
- [[Note A]] — brief description
- [[Note B]] — brief description

## Category 2
- [[Note C]] — brief description

## Related MOCs
- [[Other MOC]]
```

6. Update `00 HUB/MOC Index.md` — it uses Dataview, but verify the new MOC will appear

## Rules
- MOCs go in `00 HUB/` folder
- Always use wiki-links
- Include brief descriptions for each link
- Group logically by subtopic
