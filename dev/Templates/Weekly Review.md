---
type: weekly
week: <% tp.date.now("YYYY-[W]ww") %>
tags: [weekly]
---

# Обзор недели <% tp.date.now("YYYY-[W]ww") %>

## Что сделано

```tasks
done
done after <% tp.date.now("YYYY-MM-DD", -7) %>
done before <% tp.date.now("YYYY-MM-DD", 1) %>
short mode
```

## Что не сделано (перенести?)

```tasks
not done
due before <% tp.date.now("YYYY-MM-DD") %>
sort by priority
```

## Ключевые мысли недели
- 

## Фокус на следующую неделю
- 
