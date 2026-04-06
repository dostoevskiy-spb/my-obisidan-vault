---
name: vault-health
description: Audit vault integrity and identify issues
triggers:
  - user asks to check vault health
  - user says "аудит", "проверь vault", "health check"
---

# vault-health

Аудит целостности vault.

## Checks

1. **Broken links**: Find wiki-links `[[X]]` where X.md doesn't exist
2. **No frontmatter**: Notes missing YAML frontmatter
3. **Empty notes**: Files with no meaningful content
4. **Orphan notes**: Notes with no incoming links (not referenced by anything)
5. **Inbox overflow**: Count notes in `01 Inbox/` — flag if > 10
6. **Stale projects**: Active projects not modified in > 7 days
7. **Kill-List overload**: `today.md` has > 5 tasks
8. **Missing daily notes**: Gaps in recent daily notes
9. **Duplicate content**: Notes with very similar titles

## Workflow

1. Run all checks
2. Generate prioritized report:
   - Critical (broken links, no frontmatter)
   - Warning (orphans, stale projects)
   - Info (empty notes, duplicates)

3. Present report with specific file paths
4. Offer to fix issues (with confirmation)

## Report Format

```markdown
# Vault Health Report — YYYY-MM-DD

## Critical
- [ ] 3 broken links found
  - [[missing note]] referenced in file.md

## Warning
- [ ] 2 stale projects (no updates > 7 days)
  - 10 Projects/old-project.md

## Info
- [ ] Inbox has 12 notes — consider sorting
- [ ] 5 orphan notes found
```

## Rules
- Read-only by default — only fix with user confirmation
- Check triggers from `70 Alerts/triggers.md`
- Be specific about file paths in report
