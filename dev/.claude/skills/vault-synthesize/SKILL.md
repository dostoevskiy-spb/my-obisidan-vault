---
name: vault-synthesize
description: Search vault and synthesize knowledge on a topic
triggers:
  - user asks "what do I know about X"
  - user asks to find connections between topics
  - user says "synthesize", "синтез", "что я знаю о"
---

# vault-synthesize

Поиск и синтез знаний по теме из vault.

## Workflow

1. Search vault comprehensively:
   - Grep for the topic keyword(s) across all .md files
   - Check tags matching the topic
   - Check frontmatter fields (source, related, area)

2. Analyze found notes:
   - Read each relevant note
   - Extract key points
   - Identify connections between notes

3. Generate synthesis:
   - Create a summary document with citations
   - Use wiki-links `[[note name]]` for every referenced note
   - Group findings by subtopic
   - Highlight gaps (topics mentioned but not explored)

4. Present to user — don't save automatically (let user decide)

## Output Format

```markdown
# Синтез: [Topic]

## Найдено заметок: N

## Ключевые идеи
1. ... (из [[note1]])
2. ... (из [[note2]])

## Связи
- [[note1]] связана с [[note3]] через ...

## Пробелы
- Упоминается X, но нет заметки об этом
```

## Rules
- Always use wiki-links for citations
- Don't modify existing notes
- Show results, let user decide what to save
