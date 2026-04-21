#!/usr/bin/env python3
"""Готовит список корневых фраз для запроса базовой частотности."""
import json

d = json.load(open('/tmp/groups_roots.json'))

# Маппинг групп → поисковая фраза-корень
# Для групп "Главная", "Беседки" и СПК — используем более осмысленные или пропускаем
special = {
    "Главная": "купить теплицу",  # самый широкий запрос
    "Беседки": "купить беседку",
}

roots = []
for group_name, info in d.items():
    root = info["root"] if isinstance(info, dict) else info
    n = info.get("N", 0) if isinstance(info, dict) else 0
    # skip СПК groups (not search queries, agency's internal names)
    if root.startswith("СПК"):
        continue
    # use special for odd names
    if root in special:
        phrase = special[root]
    else:
        phrase = root
    roots.append({"group": group_name, "phrase": phrase, "N": n})

# deduplicate by phrase
seen = {}
for r in roots:
    if r["phrase"] not in seen:
        seen[r["phrase"]] = r
dedup = list(seen.values())

with open('/tmp/cluster_roots_list.json', 'w') as f:
    json.dump(dedup, f, ensure_ascii=False, indent=2)

print(f"Total groups: {len(d)}")
print(f"After skip СПК: {len(roots)}")
print(f"After dedup: {len(dedup)}")
for r in dedup[:5]:
    print(r)
