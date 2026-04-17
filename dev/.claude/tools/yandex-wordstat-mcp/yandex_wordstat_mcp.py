"""
Yandex Wordstat MCP — обёртка над Yandex Search API v2 (AI Studio / Yandex Cloud).

Env:
  YANDEX_API_KEY — API-ключ сервисного аккаунта (обязателен)

Большие ответы кладутся в ./cache/ рядом со скриптом; тул возвращает саммари
плюс путь, читать чанками через read_cached(path, offset, limit).
"""
import hashlib
import json
import os
import pathlib
import time

import httpx
from mcp.server.fastmcp import FastMCP

BASE = "https://searchapi.api.cloud.yandex.net/v2/wordstat"
HERE = pathlib.Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache"
CACHE_DIR.mkdir(exist_ok=True)
TREE_TTL_SEC = 30 * 24 * 3600
LARGE_RESPONSE_CHARS = 15000

mcp = FastMCP("yandex-wordstat")


def _headers() -> dict[str, str]:
    key = os.getenv("YANDEX_API_KEY")
    if not key:
        raise RuntimeError("Задай YANDEX_API_KEY в окружении")
    return {"Authorization": f"Api-Key {key}", "Content-Type": "application/json"}


def _post(path: str, body: dict) -> dict:
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{BASE}/{path}", json=body, headers=_headers())
        r.raise_for_status()
        return r.json()


def _as_str_list(xs):
    if not xs:
        return None
    return [str(x) for x in xs]


def _cache_large(data: dict, tag: str) -> dict:
    """Если payload большой — кладём в cache/ и возвращаем саммари + путь."""
    raw = json.dumps(data, ensure_ascii=False)
    if len(raw) <= LARGE_RESPONSE_CHARS:
        return data
    digest = hashlib.md5(raw.encode()).hexdigest()[:8]
    fname = CACHE_DIR / f"{tag}_{int(time.time())}_{digest}.json"
    fname.write_text(raw, encoding="utf-8")
    results = data.get("results")
    summary: dict = {
        "cached_to": str(fname),
        "size_chars": len(raw),
        "hint": "Используй read_cached(path, offset, limit) чтобы прочитать полностью",
    }
    if isinstance(results, list):
        summary["total_results"] = len(results)
        summary["preview_top10"] = results[:10]
    if "totalCount" in data:
        summary["totalCount"] = data["totalCount"]
    assoc = data.get("associations")
    if isinstance(assoc, list):
        summary["associations_top10"] = assoc[:10]
    return summary


@mcp.tool()
def top_requests(
    phrase: str,
    regions: list | None = None,
    devices: list[str] | None = None,
) -> dict:
    """Популярные и ассоциативные запросы за последние 30 дней.

    regions: ID как строки или числа (напр. [50] = Пермь, [54] = Екатеринбург).
    devices: подмножество ['phone','tablet','desktop']."""
    body: dict = {"phrase": phrase}
    if regions:
        body["regions"] = _as_str_list(regions)
    if devices:
        body["devices"] = devices
    return _cache_large(_post("topRequests", body), "top_requests")


@mcp.tool()
def dynamics(
    phrase: str,
    from_date: str,
    to_date: str,
    period: str = "PERIOD_MONTHLY",
    regions: list | None = None,
    devices: list[str] | None = None,
) -> dict:
    """Динамика показов во времени.

    period: 'PERIOD_MONTHLY' или 'PERIOD_WEEKLY'.
    Даты RFC3339, напр. '2025-01-01T00:00:00Z'.
    Для MONTHLY to_date — последний день месяца; для WEEKLY from_date — понедельник."""
    body: dict = {
        "phrase": phrase,
        "period": period,
        "fromDate": from_date,
        "toDate": to_date,
    }
    if regions:
        body["regions"] = _as_str_list(regions)
    if devices:
        body["devices"] = devices
    return _cache_large(_post("dynamics", body), "dynamics")


@mcp.tool()
def regions_distribution(
    phrase: str,
    top: int = 20,
    devices: list[str] | None = None,
) -> dict:
    """Распределение показов по регионам (count, share, affinityIndex).

    top: сколько регионов вернуть в ответе (остальные — в кеш-файл)."""
    body: dict = {"phrase": phrase}
    if devices:
        body["devices"] = devices
    data = _post("regions", body)
    results = data.get("results", [])

    def _count(r):
        try:
            return int(r.get("count", 0))
        except (TypeError, ValueError):
            return 0

    results_sorted = sorted(results, key=_count, reverse=True)
    out: dict = {"top": results_sorted[:top], "total_regions": len(results_sorted)}
    payload = {**data, "results": results_sorted}
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) > LARGE_RESPONSE_CHARS:
        digest = hashlib.md5(raw.encode()).hexdigest()[:8]
        fname = CACHE_DIR / f"regions_{int(time.time())}_{digest}.json"
        fname.write_text(raw, encoding="utf-8")
        out["cached_to"] = str(fname)
        out["hint"] = "Используй read_cached(path, offset, limit) чтобы прочитать хвост"
    return out


def _load_regions_tree() -> dict:
    cache = CACHE_DIR / "regions_tree.json"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < TREE_TTL_SEC:
        return json.loads(cache.read_text(encoding="utf-8"))
    data = _post("getRegionsTree", {})
    cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


@mcp.tool()
def find_region(name: str) -> dict:
    """Найти ID региона(ов) по названию (подстрока без регистра).

    Дерево регионов кешируется на 30 дней."""
    tree = _load_regions_tree()
    q = name.lower()
    out: list[dict] = []

    def walk(nodes, path=""):
        for n in nodes:
            label = n.get("label", "")
            if q in label.lower():
                out.append({"id": n.get("id"), "label": label, "path": path})
            if n.get("children"):
                walk(n["children"], f"{path}/{label}")

    walk(tree.get("regions", []))
    return {"matches": out[:30], "total": len(out)}


@mcp.tool()
def read_cached(path: str, offset: int = 0, limit: int = 50) -> dict:
    """Прочитать закешированный JSON-результат чанком.

    Возвращает срез results[offset:offset+limit]."""
    p = pathlib.Path(path).resolve()
    if CACHE_DIR not in p.parents:
        raise RuntimeError("Путь вне cache-директории")
    if not p.is_file():
        raise RuntimeError(f"Нет файла: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    results = data.get("results", [])
    end = offset + limit
    return {
        "slice": results[offset:end],
        "offset": offset,
        "returned": len(results[offset:end]),
        "total": len(results),
        "has_more": end < len(results),
    }


if __name__ == "__main__":
    mcp.run()
