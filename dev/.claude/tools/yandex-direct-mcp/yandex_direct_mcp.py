"""
Yandex Direct MCP — read-only обёртка над API v5 для аудита кабинета AZT.

Env:
  YANDEX_DIRECT_OAUTH          OAuth-токен (обязателен). Sandbox-токен ≠ prod-токен
  YANDEX_DIRECT_SANDBOX=1      переключает BASE на sandbox
  YANDEX_DIRECT_CLIENT_LOGIN   логин клиента (для агентского доступа)

Защитные механизмы:
- UnitsTracker: останавливается, если rest < MIN_UNITS_RESERVE
- Пагинация ограничена max_results=2000 (fetch_all=True — явный opt-in)
- Retry с Retry-After / RetryIn для кодов 52, 152 и 5xx
- In-memory cache 60 с для повторных get
- Большие ответы → cache/*.json, чтение через read_cached()
- Все вызовы логируются в cache/audit.log
"""
import csv
import hashlib
import io
import json
import os
import pathlib
import time
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

BASE_PROD = "https://api.direct.yandex.com/json/v5"
BASE_SANDBOX = "https://api-sandbox.direct.yandex.com/json/v5"
HERE = pathlib.Path(__file__).resolve().parent
CACHE_DIR = HERE / "cache"
CACHE_DIR.mkdir(exist_ok=True)
AUDIT_LOG = CACHE_DIR / "audit.log"

MIN_UNITS_RESERVE = 1000
DEFAULT_MAX_RESULTS = 2000
PAGE_LIMIT = 1000
MAX_PAGES = 100
MEMO_TTL = 60
LARGE_RESPONSE_CHARS = 15000
RETRY_ERROR_CODES = {52, 152}
RETRY_STATUS = {500, 502, 503, 504}
MAX_RETRIES = 3
HTTP_TIMEOUT = 60

mcp = FastMCP("yandex-direct")


# ─── utils ──────────────────────────────────────────────────────────────────


def _base() -> str:
    return BASE_SANDBOX if os.getenv("YANDEX_DIRECT_SANDBOX") else BASE_PROD


def _headers(extra: dict | None = None) -> dict[str, str]:
    token = os.getenv("YANDEX_DIRECT_OAUTH")
    if not token:
        raise RuntimeError("Задай YANDEX_DIRECT_OAUTH")
    h = {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    if login := os.getenv("YANDEX_DIRECT_CLIENT_LOGIN"):
        h["Client-Login"] = login
    if extra:
        h.update(extra)
    return h


def _hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _backoff(attempt: int, retry_after: str | None = None) -> float:
    if retry_after:
        try:
            return min(float(retry_after), 30.0)
        except ValueError:
            pass
    return min(2 ** attempt, 8.0)


def _log_audit(entry: dict) -> None:
    entry = {"ts": time.time(), **entry}
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─── units tracker ──────────────────────────────────────────────────────────


class _UnitsTracker:
    def __init__(self) -> None:
        self.rest: int | None = None
        self.daily_limit: int | None = None
        self.spent_session: int = 0
        self.last_spent: int = 0

    def update(self, units: dict) -> None:
        if not units:
            return
        self.rest = units.get("rest", self.rest)
        self.daily_limit = units.get("daily_limit", self.daily_limit)
        spent = units.get("spent", 0)
        self.last_spent = spent
        self.spent_session += spent

    def check_reserve(self) -> None:
        if self.rest is not None and self.rest < MIN_UNITS_RESERVE:
            raise RuntimeError(
                f"Низкий остаток units ({self.rest} < {MIN_UNITS_RESERVE}) — останавливаюсь"
            )

    def snapshot(self) -> dict:
        return {
            "rest": self.rest,
            "daily_limit": self.daily_limit,
            "spent_this_call": self.last_spent,
            "spent_session": self.spent_session,
        }


_units = _UnitsTracker()
_memo: dict[tuple, dict] = {}


# ─── core API call ──────────────────────────────────────────────────────────


def _call(service: str, method: str, params: dict) -> dict:
    client_login = os.getenv("YANDEX_DIRECT_CLIENT_LOGIN")
    key = (service, method, _hash(params), client_login)

    if method == "get":
        cached = _memo.get(key)
        if cached and time.time() - cached["t"] < MEMO_TTL:
            return cached["data"]

    _units.check_reserve()
    url = f"{_base()}/{service}"
    body = {"method": method, "params": params}

    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = httpx.post(url, json=body, headers=_headers(), timeout=HTTP_TIMEOUT)
        except httpx.HTTPError as e:
            last_err = e
            time.sleep(_backoff(attempt))
            continue
        if r.status_code in RETRY_STATUS:
            last_err = RuntimeError(f"HTTP {r.status_code}")
            time.sleep(_backoff(attempt, r.headers.get("Retry-After")))
            continue
        if r.status_code != 200:
            _log_audit({"service": service, "method": method, "status": r.status_code,
                        "body": r.text[:500]})
            r.raise_for_status()
        data = r.json()
        if "error" in data:
            err = data["error"]
            code = err.get("error_code")
            if code in RETRY_ERROR_CODES:
                last_err = RuntimeError(f"API {code}: {err.get('error_string')}")
                time.sleep(_backoff(attempt))
                continue
            _log_audit({"service": service, "method": method, "error": err})
            detail = err.get("error_detail") or err.get("error_string") or ""
            hint = ""
            if code == 53:
                hint = " (скорее всего нужен заголовок Client-Login)"
            raise RuntimeError(f"Direct API error {code}: {err.get('error_string')} — {detail}{hint}")

        _units.update(data.get("units", {}))
        _log_audit({"service": service, "method": method,
                    "units": data.get("units"), "ok": True})
        if method == "get":
            _memo[key] = {"data": data, "t": time.time()}
        return data
    raise RuntimeError(f"Retries exhausted for {service}/{method}: {last_err}")


# ─── pagination ─────────────────────────────────────────────────────────────


def _generic_get(
    service: str,
    result_key: str,
    *,
    selection: dict | None = None,
    fields: list[str] | None = None,
    subfields: dict[str, list[str]] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
    page_limit: int = PAGE_LIMIT,
) -> list[dict]:
    params: dict = {}
    if selection:
        params["SelectionCriteria"] = selection
    if fields:
        params["FieldNames"] = fields
    if subfields:
        params.update(subfields)
    results: list[dict] = []
    offset = 0
    for _ in range(MAX_PAGES):
        if not fetch_all and len(results) >= max_results:
            break
        _units.check_reserve()
        p = {**params, "Page": {"Limit": page_limit, "Offset": offset}}
        data = _call(service, "get", p)
        chunk = data.get("result", {}).get(result_key, [])
        results.extend(chunk)
        limited_by = data.get("result", {}).get("LimitedBy")
        if limited_by is None or len(chunk) < page_limit:
            break
        offset += page_limit
    return results if fetch_all else results[:max_results]


# ─── response packaging (cache large) ───────────────────────────────────────


def _pack(items: list, tag: str, extra: dict | None = None) -> dict:
    payload = {"items": items, "count": len(items), **(extra or {})}
    out: dict = {"_units": _units.snapshot(), **payload}
    raw = json.dumps(out, ensure_ascii=False, default=str)
    if len(raw) <= LARGE_RESPONSE_CHARS:
        return out
    digest = _hash(items)[:8]
    fname = CACHE_DIR / f"{tag}_{int(time.time())}_{digest}.json"
    fname.write_text(json.dumps({"results": items, **(extra or {})},
                                ensure_ascii=False, default=str), encoding="utf-8")
    return {
        "_units": _units.snapshot(),
        "cached_to": str(fname),
        "count": len(items),
        "preview_top10": items[:10],
        "hint": "Используй read_cached(path, offset, limit) чтобы прочитать полностью",
    }


def _wrap_dict(result: dict, tag: str) -> dict:
    """Для сервисов, где result — dict с несколькими массивами (dictionaries, changes).

    Если ответ большой — пишем в cache/ и возвращаем превью.
    """
    raw = json.dumps(result, ensure_ascii=False, default=str)
    if len(raw) <= LARGE_RESPONSE_CHARS:
        return {"_units": _units.snapshot(), **result}
    digest = _hash(result)[:8]
    fname = CACHE_DIR / f"{tag}_{int(time.time())}_{digest}.json"
    fname.write_text(raw, encoding="utf-8")
    preview: dict = {}
    for k, v in result.items():
        if isinstance(v, list):
            preview[f"{k}_count"] = len(v)
            preview[f"{k}_top3"] = v[:3]
        elif isinstance(v, dict):
            preview[k] = {"keys_sample": list(v.keys())[:10]}
        else:
            preview[k] = v
    return {
        "_units": _units.snapshot(),
        "cached_to": str(fname),
        "size_chars": len(raw),
        "preview": preview,
        "hint": "Используй read_cached(path, key=<имя_массива>, offset, limit) "
                "чтобы прочитать конкретный справочник.",
    }


# ─── default field sets (cheap minimums) ────────────────────────────────────


DEFAULT_FIELDS: dict[str, list[str]] = {
    "campaigns": ["Id", "Name", "State", "Status", "Type", "StartDate", "EndDate",
                  "DailyBudget", "Currency", "SourceId"],
    "adgroups": ["Id", "Name", "CampaignId", "Status", "Type", "RegionIds",
                 "NegativeKeywords", "TrackingParams"],
    "ads": ["Id", "AdGroupId", "CampaignId", "State", "Status", "Type", "Subtype"],
    "keywords": ["Id", "AdGroupId", "CampaignId", "Keyword", "State", "Status",
                 "ServingStatus", "Bid", "ContextBid"],
    "keywordbids": ["KeywordId", "AdGroupId", "CampaignId", "ServingStatus",
                    "SearchPrices", "NetworkPrices"],
    "bidmodifiers": ["Id", "CampaignId", "AdGroupId", "Type", "Level"],
    "sitelinks": ["Id"],
    "adextensions": ["Id", "Type", "State", "Status"],
    "adimages": ["AdImageHash", "Name", "Type", "Subtype", "Associated"],
    "advideos": ["AdVideoHash", "Name", "Associated"],
    "vcards": ["Id", "CampaignId", "CompanyName", "City", "Country"],
    "creatives": ["Id", "Name", "Type"],
    "negativekeywordsharedsets": ["Id", "Name", "NegativeKeywords"],
    "retargetinglists": ["Id", "Name", "Type", "Description", "IsAvailable"],
    "audiencetargets": ["Id", "AdGroupId", "CampaignId", "State", "RetargetingListId",
                        "InterestId", "ContextBid", "ContextPriceCoefficient"],
    "smartadtargets": ["Id", "AdGroupId", "CampaignId", "State", "Bid",
                       "ContextBid", "StrategyPriority"],
    "dynamictextadtargets": ["Id", "AdGroupId", "CampaignId", "State",
                             "Condition", "Bid", "StrategyPriority"],
    "feeds": ["Id", "Name", "BusinessType", "SourceType"],
    "turbopages": ["Id", "Name"],
    "businesses": ["Id", "Name"],
    "leads": ["Id", "AdId", "CampaignId", "Name"],
}

# Subfields (optional): keys match Yandex naming. Не включаем по умолчанию —
# пользователь сам передаёт, если нужна расширенная картина.


# ─── campaigns ──────────────────────────────────────────────────────────────


@mcp.tool()
def direct_campaigns_get(
    ids: list[int] | None = None,
    states: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    fields: list[str] | None = None,
    subfields: dict[str, list[str]] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Кампании. ~1 unit/объект, ~10 units/1000 объектов.

    states: ON/OFF/SUSPENDED/ENDED/CONVERTED/ARCHIVED
    subfields: {"TextCampaignFieldNames": [...], "DynamicTextCampaignFieldNames": [...], ...}
    """
    selection = {}
    if ids: selection["Ids"] = ids
    if states: selection["States"] = states
    if statuses: selection["Statuses"] = statuses
    if types: selection["Types"] = types
    items = _generic_get("campaigns", "Campaigns",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["campaigns"],
                         subfields=subfields,
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "campaigns")


# ─── adgroups ───────────────────────────────────────────────────────────────


@mcp.tool()
def direct_adgroups_get(
    campaign_ids: list[int] | None = None,
    ids: list[int] | None = None,
    types: list[str] | None = None,
    fields: list[str] | None = None,
    subfields: dict[str, list[str]] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Группы объявлений."""
    selection: dict = {}
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if ids: selection["Ids"] = ids
    if types: selection["Types"] = types
    items = _generic_get("adgroups", "AdGroups",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["adgroups"],
                         subfields=subfields,
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "adgroups")


# ─── ads ────────────────────────────────────────────────────────────────────


@mcp.tool()
def direct_ads_get(
    campaign_ids: list[int] | None = None,
    adgroup_ids: list[int] | None = None,
    ids: list[int] | None = None,
    states: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    fields: list[str] | None = None,
    subfields: dict[str, list[str]] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Объявления.

    Для получения текстов/картинок передай subfields, напр.:
      {"TextAdFieldNames": ["Title","Title2","Text","Href","DisplayUrlPath"]}
    """
    selection: dict = {}
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if adgroup_ids: selection["AdGroupIds"] = adgroup_ids
    if ids: selection["Ids"] = ids
    if states: selection["States"] = states
    if statuses: selection["Statuses"] = statuses
    if types: selection["Types"] = types
    items = _generic_get("ads", "Ads",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["ads"],
                         subfields=subfields,
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "ads")


# ─── keywords ───────────────────────────────────────────────────────────────


@mcp.tool()
def direct_keywords_get(
    campaign_ids: list[int] | None = None,
    adgroup_ids: list[int] | None = None,
    ids: list[int] | None = None,
    states: list[str] | None = None,
    statuses: list[str] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Ключевые фразы. Дорогая операция на больших аккаунтах — ставь фильтры."""
    selection: dict = {}
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if adgroup_ids: selection["AdGroupIds"] = adgroup_ids
    if ids: selection["Ids"] = ids
    if states: selection["States"] = states
    if statuses: selection["Statuses"] = statuses
    items = _generic_get("keywords", "Keywords",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["keywords"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "keywords")


# ─── keywordbids ────────────────────────────────────────────────────────────


@mcp.tool()
def direct_keyword_bids_get(
    keyword_ids: list[int] | None = None,
    campaign_ids: list[int] | None = None,
    adgroup_ids: list[int] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Ставки по ключам + прогноз позиций."""
    selection: dict = {}
    if keyword_ids: selection["KeywordIds"] = keyword_ids
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if adgroup_ids: selection["AdGroupIds"] = adgroup_ids
    items = _generic_get("keywordbids", "KeywordBids",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["keywordbids"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "keywordbids")


# ─── bidmodifiers ───────────────────────────────────────────────────────────


@mcp.tool()
def direct_bidmodifiers_get(
    campaign_ids: list[int] | None = None,
    adgroup_ids: list[int] | None = None,
    ids: list[int] | None = None,
    types: list[str] | None = None,
    levels: list[str] | None = None,
    fields: list[str] | None = None,
    subfields: dict[str, list[str]] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Корректировки ставок (устройства, пол/возраст, регионы, время, аудитории)."""
    selection: dict = {}
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if adgroup_ids: selection["AdGroupIds"] = adgroup_ids
    if ids: selection["Ids"] = ids
    if types: selection["Types"] = types
    if levels: selection["Levels"] = levels
    items = _generic_get("bidmodifiers", "BidModifiers",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["bidmodifiers"],
                         subfields=subfields,
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "bidmodifiers")


# ─── sitelinks ──────────────────────────────────────────────────────────────


@mcp.tool()
def direct_sitelinks_get(
    ids: list[int] | None = None,
    fields: list[str] | None = None,
    subfields: dict[str, list[str]] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Наборы быстрых ссылок.

    Для текстов ссылок передай subfields={'SitelinkFieldNames': ['Title','Href','Description']}.
    """
    selection = {"Ids": ids} if ids else {}
    items = _generic_get("sitelinks", "SitelinksSets",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["sitelinks"],
                         subfields=subfields,
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "sitelinks")


# ─── adextensions ───────────────────────────────────────────────────────────


@mcp.tool()
def direct_adextensions_get(
    ids: list[int] | None = None,
    types: list[str] | None = None,
    states: list[str] | None = None,
    statuses: list[str] | None = None,
    fields: list[str] | None = None,
    subfields: dict[str, list[str]] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Расширения (Callouts — уточнения).

    Для текстов: subfields={'CalloutFieldNames': ['CalloutText']}.
    """
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if types: selection["Types"] = types
    if states: selection["States"] = states
    if statuses: selection["Statuses"] = statuses
    items = _generic_get("adextensions", "AdExtensions",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["adextensions"],
                         subfields=subfields,
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "adextensions")


# ─── adimages / advideos ────────────────────────────────────────────────────


@mcp.tool()
def direct_adimages_get(
    hashes: list[str] | None = None,
    types: list[str] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Картинки для объявлений."""
    selection: dict = {}
    if hashes: selection["AdImageHashes"] = hashes
    if types: selection["Types"] = types
    items = _generic_get("adimages", "AdImages",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["adimages"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "adimages")


@mcp.tool()
def direct_advideos_get(
    hashes: list[str] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Видео для объявлений."""
    selection = {"AdVideoHashes": hashes} if hashes else {}
    items = _generic_get("advideos", "AdVideos",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["advideos"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "advideos")


# ─── vcards ─────────────────────────────────────────────────────────────────


@mcp.tool()
def direct_vcards_get(
    ids: list[int] | None = None,
    campaign_ids: list[int] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Визитки с контактами."""
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    items = _generic_get("vcards", "VCards",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["vcards"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "vcards")


# ─── creatives ──────────────────────────────────────────────────────────────


@mcp.tool()
def direct_creatives_get(
    ids: list[int] | None = None,
    types: list[str] | None = None,
    fields: list[str] | None = None,
    subfields: dict[str, list[str]] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Креативы (смарт-баннеры)."""
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if types: selection["Types"] = types
    items = _generic_get("creatives", "Creatives",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["creatives"],
                         subfields=subfields,
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "creatives")


# ─── negative keyword shared sets ───────────────────────────────────────────


@mcp.tool()
def direct_negative_keywords_get(
    ids: list[int] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Общие наборы минус-слов."""
    selection = {"Ids": ids} if ids else {}
    items = _generic_get("negativekeywordsharedsets", "NegativeKeywordSharedSets",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["negativekeywordsharedsets"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "negative_keyword_sets")


# ─── retargeting & audiences ────────────────────────────────────────────────


@mcp.tool()
def direct_retargeting_lists_get(
    ids: list[int] | None = None,
    types: list[str] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Списки ретаргетинга/аудиторий."""
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if types: selection["Types"] = types
    items = _generic_get("retargetinglists", "RetargetingLists",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["retargetinglists"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "retargeting_lists")


@mcp.tool()
def direct_audience_targets_get(
    ids: list[int] | None = None,
    campaign_ids: list[int] | None = None,
    adgroup_ids: list[int] | None = None,
    states: list[str] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Привязка аудиторий к группам объявлений."""
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if adgroup_ids: selection["AdGroupIds"] = adgroup_ids
    if states: selection["States"] = states
    items = _generic_get("audiencetargets", "AudienceTargets",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["audiencetargets"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "audience_targets")


# ─── smart ad / dynamic text targets ────────────────────────────────────────


@mcp.tool()
def direct_smart_ad_targets_get(
    ids: list[int] | None = None,
    campaign_ids: list[int] | None = None,
    adgroup_ids: list[int] | None = None,
    states: list[str] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Таргетинг умных баннеров."""
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if adgroup_ids: selection["AdGroupIds"] = adgroup_ids
    if states: selection["States"] = states
    items = _generic_get("smartadtargets", "SmartAdTargets",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["smartadtargets"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "smart_ad_targets")


@mcp.tool()
def direct_dynamic_targets_get(
    ids: list[int] | None = None,
    campaign_ids: list[int] | None = None,
    adgroup_ids: list[int] | None = None,
    states: list[str] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Таргетинг динамических объявлений."""
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if adgroup_ids: selection["AdGroupIds"] = adgroup_ids
    if states: selection["States"] = states
    items = _generic_get("dynamictextadtargets", "Webpages",
                         selection=selection,
                         fields=fields or DEFAULT_FIELDS["dynamictextadtargets"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "dynamic_targets")


# ─── feeds / turbopages / businesses / leads ────────────────────────────────


@mcp.tool()
def direct_feeds_get(
    ids: list[int] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Товарные фиды."""
    selection = {"Ids": ids} if ids else {}
    items = _generic_get("feeds", "Feeds", selection=selection,
                         fields=fields or DEFAULT_FIELDS["feeds"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "feeds")


@mcp.tool()
def direct_turbopages_get(
    ids: list[int] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Турбо-страницы."""
    selection = {"Ids": ids} if ids else {}
    items = _generic_get("turbopages", "TurboPages", selection=selection,
                         fields=fields or DEFAULT_FIELDS["turbopages"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "turbopages")


@mcp.tool()
def direct_businesses_get(
    ids: list[int] | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Бизнес-профили рекламодателя."""
    selection = {"Ids": ids} if ids else {}
    items = _generic_get("businesses", "Businesses", selection=selection,
                         fields=fields or DEFAULT_FIELDS["businesses"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "businesses")


@mcp.tool()
def direct_leads_get(
    ids: list[int] | None = None,
    campaign_ids: list[int] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Лиды (из форм на объявлениях)."""
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if date_from or date_to:
        selection["DateRange"] = {k: v for k, v in
                                  {"DateFrom": date_from, "DateTo": date_to}.items() if v}
    items = _generic_get("leads", "Leads", selection=selection,
                         fields=fields or DEFAULT_FIELDS["leads"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "leads")


# ─── dictionaries / clients ─────────────────────────────────────────────────


@mcp.tool()
def direct_dictionaries_get(names: list[str]) -> dict:
    """Справочники. Доступные names:
    GeoRegions, Currencies, TimeZones, AdCategories, Constants, Interests,
    OperationSystemVersions, ProductivityTargetCategories, SupplySidePlatforms.

    Большие ответы (>15k символов) автоматически кешируются; используй
    read_cached(path, key='Currencies', offset, limit) для чанков.
    """
    data = _call("dictionaries", "get", {"DictionaryNames": names})
    return _wrap_dict(data.get("result", {}), "dictionaries")


@mcp.tool()
def direct_client_get(fields: list[str] | None = None) -> dict:
    """Владелец текущего токена.

    ⚠️ Баланс рекламного счёта в Direct API v5 недоступен — смотри balance.yandex.ru.
    Косвенные сигналы: AccountQuality, Restrictions, Notification.
    """
    default = ["AccountQuality", "ClientId", "ClientInfo", "CountryId",
               "Currency", "Grants", "Login", "Notification", "Phone",
               "Restrictions", "Settings", "Type", "VatRate"]
    data = _call("clients", "get",
                 {"FieldNames": fields or default})
    return {"_units": _units.snapshot(), **data.get("result", {})}


@mcp.tool()
def direct_agency_clients_get(
    logins: list[str] | None = None,
    archived: bool | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Клиенты агентства (для агентского токена)."""
    selection: dict = {}
    if logins: selection["Logins"] = logins
    if archived is not None:
        selection["Archived"] = "YES" if archived else "NO"
    default = ["AccountQuality", "ClientId", "ClientInfo", "Currency",
               "Grants", "Login", "Notification", "Phone", "Representatives",
               "Restrictions", "Settings", "Type", "VatRate"]
    items = _generic_get("agencyclients", "Clients",
                         selection=selection,
                         fields=fields or default,
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "agency_clients")


# ─── changes ────────────────────────────────────────────────────────────────


def _to_iso_utc(ts: int | str) -> str:
    """Принимает ISO-строку или Unix seconds, возвращает YYYY-MM-DDThh:mm:ssZ."""
    if isinstance(ts, str):
        return ts if ts.endswith("Z") else ts + "Z"
    from datetime import datetime, timezone
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@mcp.tool()
def direct_changes_dictionaries(timestamp: str | int | None = None) -> dict:
    """changes.checkDictionaries — изменились ли справочники с момента X.

    timestamp: ISO8601 (YYYY-MM-DDThh:mm:ssZ) или Unix seconds.
    """
    params: dict = {}
    if timestamp is not None:
        params["Timestamp"] = _to_iso_utc(timestamp)
    data = _call("changes", "checkDictionaries", params)
    return {"_units": _units.snapshot(), **data.get("result", {})}


@mcp.tool()
def direct_changes_campaigns(timestamp: str | int) -> dict:
    """changes.checkCampaigns — ID кампаний, изменённых с Timestamp.

    timestamp: ISO8601 (YYYY-MM-DDThh:mm:ssZ) или Unix seconds.
    ⚠️ Окно ≤ 7 дней (см. direct_audit_changes_since для скользящего).
    """
    data = _call("changes", "checkCampaigns",
                 {"Timestamp": _to_iso_utc(timestamp)})
    return {"_units": _units.snapshot(), **data.get("result", {})}


@mcp.tool()
def direct_changes_check(
    campaign_ids: list[int],
    timestamp: str | int,
    field_names: list[str] | None = None,
) -> dict:
    """changes.check — детальный дифф по указанным кампаниям.

    timestamp: ISO8601 или Unix seconds.
    field_names: CampaignIds/AdGroupIds/AdIds/TargetIds/Statistics.
    """
    fields = field_names or ["CampaignIds", "AdGroupIds", "AdIds", "TargetIds"]
    data = _call("changes", "check", {
        "CampaignIds": campaign_ids,
        "Timestamp": _to_iso_utc(timestamp),
        "FieldNames": fields,
    })
    return _wrap_dict(data.get("result", {}), "changes_check")


@mcp.tool()
def direct_audit_changes_since(
    hours_back: int = 24,
    field_names: list[str] | None = None,
) -> dict:
    """Composite аудит: какие кампании/группы/объявления изменялись за N часов.

    ⚠️ Окно ограничено 7 днями (168ч). При больших значениях — обрезается до 168ч.
    Связка: checkDictionaries → checkCampaigns → check (батчами по 1000).
    Стоимость: ~3 + N_batches вызовов.
    """
    hours = min(hours_back, 168)
    iso = _to_iso_utc(int(time.time()) - hours * 3600)

    dict_data = _call("changes", "checkDictionaries", {"Timestamp": iso})
    camp_data = _call("changes", "checkCampaigns", {"Timestamp": iso})
    changed_camp_ids = camp_data.get("result", {}).get("Ids", [])

    diffs: list[dict] = []
    if changed_camp_ids:
        fields = field_names or ["CampaignIds", "AdGroupIds", "AdIds", "TargetIds"]
        for i in range(0, len(changed_camp_ids), 1000):
            batch = changed_camp_ids[i:i + 1000]
            _units.check_reserve()
            chunk = _call("changes", "check", {
                "CampaignIds": batch, "Timestamp": iso, "FieldNames": fields,
            })
            diffs.append(chunk.get("result", {}))

    return {
        "_units": _units.snapshot(),
        "window_hours": hours,
        "since": iso,
        "dictionaries": dict_data.get("result", {}),
        "changed_campaign_ids": changed_camp_ids,
        "changed_campaign_count": len(changed_camp_ids),
        "diffs": diffs,
    }


# ─── reports ────────────────────────────────────────────────────────────────


REPORT_TYPES = {
    "CAMPAIGN_PERFORMANCE_REPORT", "ADGROUP_PERFORMANCE_REPORT",
    "AD_PERFORMANCE_REPORT", "CRITERIA_PERFORMANCE_REPORT",
    "SEARCH_QUERY_PERFORMANCE_REPORT", "CUSTOM_REPORT",
    "REACH_AND_FREQUENCY_PERFORMANCE_REPORT",
}


def _parse_tsv_preview(path: pathlib.Path, rows: int = 10) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [row for _, row in zip(range(rows), reader)]


def _count_tsv_rows(path: pathlib.Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


@mcp.tool()
def direct_report(
    report_type: str,
    field_names: list[str],
    date_from: str | None = None,
    date_to: str | None = None,
    date_range_type: str = "CUSTOM_DATE",
    filters: list[dict] | None = None,
    goals: list[int] | None = None,
    attribution_models: list[str] | None = None,
    order_by: list[dict] | None = None,
    include_vat: bool = True,
    include_discount: bool = True,
    max_wait_sec: int = 600,
) -> dict:
    """Отчёт Direct. Async long-running, TSV сохраняется в cache/.

    report_type: CAMPAIGN_PERFORMANCE_REPORT | ADGROUP_PERFORMANCE_REPORT |
      AD_PERFORMANCE_REPORT | CRITERIA_PERFORMANCE_REPORT |
      SEARCH_QUERY_PERFORMANCE_REPORT | CUSTOM_REPORT |
      REACH_AND_FREQUENCY_PERFORMANCE_REPORT
    date_range_type: CUSTOM_DATE | LAST_7_DAYS | LAST_30_DAYS | LAST_90_DAYS |
      YESTERDAY | THIS_MONTH | LAST_MONTH | ALL_TIME | …
    filters: [{"Field":"...","Operator":"EQUALS|IN|...","Values":["..."]}]
    Стоимость — отдельная квота Reports, **не** тратит units get-операций.
    """
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Unknown report_type: {report_type}")

    selection: dict = {}
    if date_range_type == "CUSTOM_DATE":
        if not (date_from and date_to):
            raise ValueError("date_from и date_to обязательны при CUSTOM_DATE")
        selection["DateFrom"] = date_from
        selection["DateTo"] = date_to
    if filters:
        selection["Filter"] = filters

    params: dict = {
        "SelectionCriteria": selection,
        "FieldNames": field_names,
        "ReportName": f"report_{int(time.time())}",
        "ReportType": report_type,
        "DateRangeType": date_range_type,
        "Format": "TSV",
        "IncludeVAT": "YES" if include_vat else "NO",
        "IncludeDiscount": "YES" if include_discount else "NO",
    }
    if goals: params["Goals"] = goals
    if attribution_models: params["AttributionModels"] = attribution_models
    if order_by: params["OrderBy"] = order_by

    body = {"params": params}
    report_headers = _headers({
        "processingMode": "auto",
        "returnMoneyInMicros": "false",
        "skipReportHeader": "true",
        "skipColumnHeader": "false",
        "skipReportSummary": "true",
    })
    url = f"{_base()}/reports"
    start = time.time()
    digest = _hash(params)[:8]
    path = CACHE_DIR / f"report_{int(time.time())}_{digest}.tsv"

    with httpx.Client(timeout=120) as c:
        while True:
            r = c.post(url, json=body, headers=report_headers)
            if r.status_code == 200:
                path.write_text(r.text, encoding="utf-8")
                break
            if r.status_code in (201, 202):
                if time.time() - start > max_wait_sec:
                    raise TimeoutError(
                        f"Отчёт не готов за {max_wait_sec}s — сузь даты или увеличь max_wait_sec"
                    )
                retry_in = r.headers.get("retryIn") or r.headers.get("Retry-After")
                time.sleep(int(retry_in) if retry_in and retry_in.isdigit() else 5)
                continue
            _log_audit({"service": "reports", "status": r.status_code, "body": r.text[:500]})
            r.raise_for_status()

    rows = _count_tsv_rows(path)
    preview = _parse_tsv_preview(path, rows=10)
    _log_audit({"service": "reports", "report_type": report_type,
                "rows": rows, "path": str(path), "ok": True})
    return {
        "path": str(path),
        "rows": rows,
        "size_bytes": path.stat().st_size,
        "preview_top10": preview,
        "hint": "Полное чтение: read_cached_tsv(path, offset, limit)",
    }


# ─── cached readers ─────────────────────────────────────────────────────────


def _inside_cache(p: pathlib.Path) -> bool:
    return CACHE_DIR in p.parents or p.parent == CACHE_DIR


@mcp.tool()
def read_cached(path: str, offset: int = 0, limit: int = 50,
                key: str | None = None) -> dict:
    """Прочитать закешированный JSON-результат чанком.

    key: имя массива в JSON (для dictionaries — 'Currencies', 'GeoRegions' и т.п.).
    Без key — ищет 'results'/'items' автоматически.
    """
    p = pathlib.Path(path).resolve()
    if not _inside_cache(p):
        raise RuntimeError("Путь вне cache-директории")
    if not p.is_file():
        raise RuntimeError(f"Нет файла: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if key:
        items = data.get(key, [])
        if not isinstance(items, list):
            raise RuntimeError(f"Ключ '{key}' не является массивом")
    else:
        items = data.get("results") or data.get("items") or []
    end = offset + limit
    return {
        "slice": items[offset:end],
        "offset": offset,
        "returned": len(items[offset:end]),
        "total": len(items),
        "has_more": end < len(items),
        "available_keys": [k for k, v in data.items() if isinstance(v, list)],
    }


@mcp.tool()
def read_cached_tsv(path: str, offset: int = 0, limit: int = 50) -> dict:
    """Прочитать TSV-отчёт чанком."""
    p = pathlib.Path(path).resolve()
    if not _inside_cache(p):
        raise RuntimeError("Путь вне cache-директории")
    if not p.is_file():
        raise RuntimeError(f"Нет файла: {p}")
    out = []
    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader):
            if i < offset:
                continue
            if len(out) >= limit:
                break
            out.append(row)
    total = _count_tsv_rows(p)
    return {
        "slice": out,
        "offset": offset,
        "returned": len(out),
        "total": total,
        "has_more": offset + len(out) < total,
    }


# ─── navigation helpers ─────────────────────────────────────────────────────


@mcp.tool()
def find_campaign(query: str) -> dict:
    """Поиск кампании по подстроке в имени или по точному ID."""
    items = _generic_get("campaigns", "Campaigns",
                         fields=["Id", "Name", "State", "Status", "Type"],
                         max_results=DEFAULT_MAX_RESULTS)
    q = query.strip().lower()
    matches = [c for c in items
               if q in str(c.get("Name", "")).lower() or q == str(c.get("Id"))]
    return {"_units": _units.snapshot(), "matches": matches[:30],
            "total_matches": len(matches)}


def _all_campaign_ids() -> list[int]:
    items = _generic_get("campaigns", "Campaigns", fields=["Id"],
                         max_results=DEFAULT_MAX_RESULTS)
    return [c["Id"] for c in items]


@mcp.tool()
def find_adgroup(query: str, campaign_id: int | None = None) -> dict:
    """Поиск группы объявлений. Без campaign_id сначала подгружаются все кампании."""
    if campaign_id:
        selection = {"CampaignIds": [campaign_id]}
    else:
        camp_ids = _all_campaign_ids()
        if not camp_ids:
            return {"_units": _units.snapshot(), "matches": [], "total_matches": 0}
        selection = {"CampaignIds": camp_ids}
    items = _generic_get("adgroups", "AdGroups",
                         selection=selection,
                         fields=["Id", "Name", "CampaignId", "Type", "Status"],
                         max_results=DEFAULT_MAX_RESULTS)
    q = query.strip().lower()
    matches = [g for g in items
               if q in str(g.get("Name", "")).lower() or q == str(g.get("Id"))]
    return {"_units": _units.snapshot(), "matches": matches[:30],
            "total_matches": len(matches)}


@mcp.tool()
def find_keyword(query: str, adgroup_id: int | None = None,
                 campaign_id: int | None = None) -> dict:
    """Поиск ключа. Без фильтров — подгружаются все кампании."""
    selection: dict = {}
    if adgroup_id:
        selection["AdGroupIds"] = [adgroup_id]
    elif campaign_id:
        selection["CampaignIds"] = [campaign_id]
    else:
        camp_ids = _all_campaign_ids()
        if not camp_ids:
            return {"_units": _units.snapshot(), "matches": [], "total_matches": 0}
        selection["CampaignIds"] = camp_ids
    items = _generic_get("keywords", "Keywords",
                         selection=selection,
                         fields=["Id", "Keyword", "AdGroupId", "CampaignId",
                                 "State", "Status", "Bid"],
                         max_results=DEFAULT_MAX_RESULTS)
    q = query.strip().lower()
    matches = [k for k in items if q in str(k.get("Keyword", "")).lower()]
    return {"_units": _units.snapshot(), "matches": matches[:50],
            "total_matches": len(matches)}


@mcp.tool()
def direct_units_status() -> dict:
    """Текущий баланс units (дешёвый probe через campaigns.get Limit=1)."""
    _call("campaigns", "get", {
        "SelectionCriteria": {}, "FieldNames": ["Id"],
        "Page": {"Limit": 1, "Offset": 0},
    })
    return _units.snapshot()


@mcp.tool()
def account_summary(lightweight: bool = True) -> dict:
    """Быстрая сводка по аккаунту.

    lightweight=True — только счётчики (campaigns сначала, потом по их ID adgroups/ads/keywords).
    lightweight=False — возвращает полные списки всех сущностей (дорого).

    Direct API требует фильтры (CampaignIds/AdGroupIds) для adgroups/ads/keywords,
    поэтому они считаются через preload кампаний.
    """
    summary: dict = {"_units_before": _units.snapshot()}

    campaigns = _generic_get("campaigns", "Campaigns",
                             fields=["Id", "Name", "State", "Status", "Type"],
                             max_results=DEFAULT_MAX_RESULTS)
    summary["campaigns_count"] = len(campaigns)
    if not lightweight:
        summary["campaigns"] = campaigns

    if not campaigns:
        summary["_units_after"] = _units.snapshot()
        return summary

    camp_ids = [c["Id"] for c in campaigns]

    def _count_by_campaigns(service: str, key: str, selection_key: str = "CampaignIds") -> int:
        items = _generic_get(service, key,
                             selection={selection_key: camp_ids},
                             fields=["Id"], max_results=DEFAULT_MAX_RESULTS)
        return len(items)

    for service, key, sel in [
        ("adgroups", "AdGroups", "CampaignIds"),
        ("ads", "Ads", "CampaignIds"),
        ("keywords", "Keywords", "CampaignIds"),
    ]:
        try:
            summary[f"{service}_count"] = _count_by_campaigns(service, key, sel)
        except RuntimeError as e:
            summary[f"{service}_count"] = f"error: {e}"

    summary["_units_after"] = _units.snapshot()
    return summary


@mcp.tool()
def estimate_cost(service: str, expected_objects: int,
                  expected_fields: int = 5) -> dict:
    """Примерная оценка стоимости вызова в units.

    Эмпирика: ~0.5 units на объект при дешёвых полях + 1 за страницу.
    Оценка консервативная — реальная стоимость зависит от поля (Productivity/Stat дороже).
    """
    pages = max(1, (expected_objects + PAGE_LIMIT - 1) // PAGE_LIMIT)
    est = max(1, int(expected_objects * 0.5 + pages))
    multiplier = 1.0
    if expected_fields > 10:
        multiplier = 1.5
    est_hi = int(est * multiplier * 2)
    return {
        "service": service,
        "expected_objects": expected_objects,
        "pages": pages,
        "estimate_low": est,
        "estimate_high": est_hi,
        "current_rest": _units.rest,
        "daily_limit": _units.daily_limit,
        "hint": "Оценка грубая. Точные тарифы зависят от полей (Productivity/Stat — дороже).",
    }


if __name__ == "__main__":
    mcp.run()
