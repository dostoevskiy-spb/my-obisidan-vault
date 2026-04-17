"""
Yandex Wordstat MCP — обёртка над Yandex Search API v2 (AI Studio / Yandex Cloud).

Env:
  YANDEX_API_KEY   — API-ключ сервисного аккаунта (обязателен)

Запуск:
  uv run --with 'mcp[cli]' --with httpx python yandex_wordstat_mcp.py
"""
import os
import httpx
from mcp.server.fastmcp import FastMCP

BASE = "https://searchapi.api.cloud.yandex.net/v2/wordstat"
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


@mcp.tool()
def top_requests(
    phrase: str,
    regions: list[int] | None = None,
    devices: list[str] | None = None,
) -> dict:
    """Популярные и ассоциативные запросы за последние 30 дней.

    devices: подмножество ["phone","tablet","desktop"]; regions: ID из regions_tree."""
    body: dict = {"phrase": phrase}
    if regions:
        body["regions"] = regions
    if devices:
        body["devices"] = devices
    return _post("topRequests", body)


@mcp.tool()
def dynamics(
    phrase: str,
    from_date: str,
    to_date: str,
    period: str = "PERIOD_MONTHLY",
    regions: list[int] | None = None,
    devices: list[str] | None = None,
) -> dict:
    """Динамика показов во времени.

    period: "PERIOD_MONTHLY" или "PERIOD_WEEKLY".
    from_date / to_date: RFC3339, напр. "2025-01-01T00:00:00Z".
    Ограничения API: для MONTHLY to_date — последний день месяца; для WEEKLY from_date — понедельник."""
    body: dict = {
        "phrase": phrase,
        "period": period,
        "fromDate": from_date,
        "toDate": to_date,
    }
    if regions:
        body["regions"] = regions
    if devices:
        body["devices"] = devices
    return _post("dynamics", body)


@mcp.tool()
def regions_distribution(
    phrase: str,
    devices: list[str] | None = None,
) -> dict:
    """Распределение показов по регионам (count, share, affinityIndex)."""
    body: dict = {"phrase": phrase}
    if devices:
        body["devices"] = devices
    return _post("regions", body)


@mcp.tool()
def regions_tree() -> dict:
    """Иерархия поддерживаемых регионов (ID → название)."""
    return _post("getRegionsTree", {})


if __name__ == "__main__":
    mcp.run()
