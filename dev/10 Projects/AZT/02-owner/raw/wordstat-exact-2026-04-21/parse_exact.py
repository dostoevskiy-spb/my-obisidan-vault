#!/usr/bin/env python3
"""Парсит все cache-файлы wordstat_report_*.json и собирает точные частотности
в /tmp/exact_results.json. Сопоставляет по точной форме '!word1 !word2 ...'."""
import json
import glob
import os

CACHE_DIR = "/home/pavel/dev/obsidian/dev/.claude/tools/yandex-direct-mcp/cache"
PHRASES_FILE = "/tmp/phrases_all.json"
OUT_FILE = "/tmp/exact_results.json"
INLINE_FILE = "/tmp/inline_exact.json"

with open(PHRASES_FILE) as f:
    phrases = json.load(f)

# exact form -> list[(index, original phrase)] — handles dupes
exact_map = {}
for i, p in enumerate(phrases):
    exact_map.setdefault(p["exact"], []).append((i, p["phrase"]))

# load existing results if any
results = {}
if os.path.exists(OUT_FILE):
    with open(OUT_FILE) as f:
        results = json.load(f)

def process_items(items, source):
    new = 0
    for it in items:
        phrase = it.get("Phrase", "")
        if not phrase.startswith("!"):
            continue
        if phrase not in exact_map:
            continue
        sw = it.get("SearchedWith", [])
        shows = 0
        if sw:
            # SearchedWith[0].Phrase should equal the exact form
            if sw[0].get("Phrase", "").strip() == phrase.strip():
                shows = int(sw[0].get("Shows", 0))
            else:
                # find the row with exact match
                for r in sw:
                    if r.get("Phrase", "").strip() == phrase.strip():
                        shows = int(r.get("Shows", 0))
                        break
        for idx, orig in exact_map[phrase]:
            key = str(idx + 1)
            if key not in results:
                new += 1
            results[key] = {
                "phrase": orig,
                "exact": phrase,
                "shows": shows,
                "source": source,
            }
    return new

# 1) inline results (batches without cache file)
if os.path.exists(INLINE_FILE):
    with open(INLINE_FILE) as f:
        inline = json.load(f)
    for it in inline:
        n = process_items([it], "inline")

# 2) cache files (only recent session)
cache_files = sorted(glob.glob(f"{CACHE_DIR}/wordstat_report_*.json"))
# only timestamps >= 1776722000 (today's session, Apr 21 01:07+)
recent_cutoff = 1776722000
recent = [f for f in cache_files if int(os.path.basename(f).split("_")[2]) >= recent_cutoff]

total_new = 0
for cf in recent:
    with open(cf) as f:
        data = json.load(f)
    items = data.get("Items", [])
    new = process_items(items, os.path.basename(cf))
    total_new += new

with open(OUT_FILE, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Loaded {len(results)} results. New from this run: {total_new}")
print(f"Cache files processed: {len(recent)}")
print(f"Missing from 1..{len(phrases)}:")
missing = [i + 1 for i in range(len(phrases)) if str(i + 1) not in results]
print(f"  count={len(missing)}, first={missing[:15]}, last={missing[-15:] if missing else []}")
