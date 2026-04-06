---
name: vault-review
description: Generate weekly review notes
triggers:
  - user asks for a weekly review
  - user says "обзор недели", "weekly review", "итоги"
---

# vault-review

Еженедельный обзор.

## Workflow

1. Determine the review period (current week by default)
2. Collect data:
   - Completed tasks (done this week)
   - Overdue tasks (due before today, not done)
   - New notes created this week
   - Updated projects
   - Daily notes from this week

3. Create review in `Weekly/`:

```yaml
---
type: weekly
week: YYYY-Www
tags: [weekly]
---
```

4. Structure:

```markdown
# Обзор недели YYYY-Www

## Что сделано
- (completed tasks with sources)

## Что не сделано (перенести?)
- (overdue tasks)

## Ключевые мысли недели
- (insights from daily notes and new zettels)

## Новые заметки
- [[new note 1]]
- [[new note 2]]

## Фокус на следующую неделю
- (suggestions based on upcoming deadlines and priorities)
```

5. Update `60 Kill-List/this-week.md` with next week's priorities

## Rules
- Weekly reviews go in `Weekly/` folder
- Filename format: `YYYY-Www.md`
- Always suggest focus for next week
- Include wiki-links to all referenced notes
