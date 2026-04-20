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
                        "InterestId", "ContextBid", "StrategyPriority"],
    "smartadtargets": ["Id", "AdGroupId", "CampaignId", "Name", "State",
                       "AverageCpc", "AverageCpa", "StrategyPriority"],
    "dynamictextadtargets": ["Id", "AdGroupId", "CampaignId", "Name", "State",
                             "Conditions", "ConditionType", "Bid", "StrategyPriority"],
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
    """Список кампаний. Фильтры опциональны — без них вернёт все.

    Цена: ~10 units + 1 unit на объект.

    Фильтры (все опциональны, можно комбинировать):
      ids       — [int, ...] точные ID кампаний.
      states    — подмножество ['ON','OFF','SUSPENDED','ENDED','CONVERTED','ARCHIVED'].
      statuses  — подмножество ['DRAFT','MODERATION','ACCEPTED','REJECTED'].
      types     — подмножество ['TEXT_CAMPAIGN','UNIFIED_CAMPAIGN',
                   'DYNAMIC_TEXT_CAMPAIGN','MOBILE_APP_CAMPAIGN','SMART_CAMPAIGN',
                   'MCBANNER_CAMPAIGN','CPM_BANNER_CAMPAIGN','CPM_VIDEO_CAMPAIGN',
                   'CPM_PRICE_CAMPAIGN','CPM_OUTDOOR_CAMPAIGN','CPM_AUDIO_CAMPAIGN'].

    fields — имена полей верхнего уровня. По умолчанию: Id, Name, State, Status,
      Type, StartDate, EndDate, DailyBudget, Currency, SourceId.
      Дополнительно доступны: ClientInfo, Funds, Notification, RepresentedBy,
      TimeTargeting, TimeZone, BlockedIps, ExcludedSites, NegativeKeywords,
      Statistics, PriorityGoals.

    subfields — поля по типу кампании. Формат:
      {"TextCampaignFieldNames":          [...],   # классическая текстовая
       "UnifiedCampaignFieldNames":       [...],   # единая перфоманс-кампания (ЕПК)
       "DynamicTextCampaignFieldNames":   [...],
       "SmartCampaignFieldNames":         [...],
       "MobileAppCampaignFieldNames":     [...],
       "MCBannerCampaignFieldNames":      [...],
       "CpmBannerCampaignFieldNames":     [...],
       "CpmVideoCampaignFieldNames":      [...]}
      Внутри типичные поля: BiddingStrategy, CounterIds, PriorityGoals,
      RelevantKeywords, Settings, TrackingParams.
      Пример получения стратегии назначения ставок:
        subfields={"TextCampaignFieldNames":["BiddingStrategy"]}

    max_results — потолок (по умолч. 2000). fetch_all=True — снять потолок (осторожно).

    Ответ: {"items": [...], "count": N, "_units": {...}}.
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
    """Группы объявлений. ⚠️ Обязательно передать ids ИЛИ campaign_ids.

    Без одного из этих фильтров API вернёт 8000 (нужен SelectionCriteria).
    Типовой сценарий: сначала вызвать direct_campaigns_get, забрать Id кампаний,
    передать их как campaign_ids.

    Цена: ~15 units + 1 unit на объект.

    Фильтры:
      campaign_ids — [int, ...] ID родительских кампаний.
      ids          — [int, ...] точные ID групп.
      types        — подмножество ['TEXT_AD_GROUP','MOBILE_APP_AD_GROUP',
                     'DYNAMIC_TEXT_AD_GROUP','CPM_BANNER_AD_GROUP',
                     'CPM_VIDEO_AD_GROUP','SMART_AD_GROUP','CPM_BANNER_USER_PROFILE_AD_GROUP'].

    fields по умолчанию: Id, Name, CampaignId, Status, Type, RegionIds,
      NegativeKeywords, TrackingParams. Ещё доступны: ServingStatus,
      RegionalAdjustments, RestrictedRegionIds, Subtype.

    subfields (по типу группы): MobileAppAdGroupFieldNames,
      DynamicTextAdGroupFieldNames, DynamicTextFeedAdGroupFieldNames,
      CpmBannerAdGroupFieldNames, CpmVideoAdGroupFieldNames,
      SmartAdGroupFieldNames.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Объявления. ⚠️ Обязательно передать ids ИЛИ adgroup_ids ИЛИ campaign_ids.

    Без одного из них API вернёт 8000. Типично: сначала direct_adgroups_get
    по нужным кампаниям, потом сюда — adgroup_ids.

    Цена: ~15 units + 1 unit на объект.

    Фильтры:
      campaign_ids — [int, ...] ID кампаний.
      adgroup_ids  — [int, ...] ID групп.
      ids          — [int, ...] точные ID объявлений.
      states       — ['ON','OFF','SUSPENDED','OFF_BY_MONITORING','ARCHIVED'].
      statuses     — ['DRAFT','MODERATION','PREACCEPTED','ACCEPTED','REJECTED'].
      types        — ['TEXT_AD','MOBILE_APP_AD','DYNAMIC_TEXT_AD','IMAGE_AD',
                      'CPM_BANNER_AD','CPM_VIDEO_AD','SMART_AD_BUILDER_AD',
                      'MCBANNER_AD','CPM_PRICE_AD','CPM_OUTDOOR_AD','CPM_AUDIO_AD',
                      'UNIFIED_AD','BILLBOARD_AD'].

    fields по умолчанию: Id, AdGroupId, CampaignId, State, Status, Type, Subtype.
      (без текстов/изображений — они тянутся через subfields).

    subfields — чтобы получить тексты/креативы, выбери по типу:
      TextAdFieldNames         = ['Title','Title2','Text','Href','DisplayUrlPath',
                                  'VCardId','SitelinkSetId','AdImageHash',
                                  'AdExtensions','Mobile','Business']
      MobileAppAdFieldNames    = ['Title','Text','TrackingUrl','ActionLinks',
                                  'Features','BundleId','AdImageHash']
      DynamicTextAdFieldNames  = ['Text','VCardId','AdImageHash','Sitelinks']
      TextImageAdFieldNames    = ['AdImageHash','Href','TrackingParams']
      CpmBannerAdFieldNames    = ['CreativeId','Href','AdImageHash']
      CpmVideoAdFieldNames     = ['CreativeId','Href','TrackingPixels']
      SmartAdBuilderAdFieldNames = ['CreativeId','Href','TrackingParams']
      TextAdBuilderAdFieldNames = ['CreativeId','Href','AdExtensions']
      Пример:
        subfields={"TextAdFieldNames":["Title","Title2","Text","Href"]}

    Ответ: {"items": [...], "count": N, "_units": {...}}.
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
    """Ключевые фразы. ⚠️ Обязательно передать ids ИЛИ adgroup_ids ИЛИ campaign_ids.

    На большом аккаунте с 10+ тыс. ключей стоимость ощутимая —
    ВСЕГДА фильтруй по кампании или группе, если не нужна вся семантика.

    Цена: ~15 units + 1 unit на объект. Добавление полей Stat/Productivity
    удорожает вызов в несколько раз — избегай без необходимости.

    Фильтры:
      campaign_ids, adgroup_ids, ids — [int, ...]
      states     — ['ON','OFF','SUSPENDED']
      statuses   — ['DRAFT','MODERATION','PREACCEPTED','ACCEPTED','REJECTED']

    fields по умолчанию: Id, AdGroupId, CampaignId, Keyword, State, Status,
      ServingStatus, Bid, ContextBid.
      Дополнительно: StrategyPriority, UserParam1, UserParam2, ProductivityInfo,
      Statistics.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Ставки по ключевым фразам + прогнозы позиций.

    ⚠️ Обязательно передать keyword_ids ИЛИ campaign_ids ИЛИ adgroup_ids.

    Цена: ~15 units + 1 unit на объект.

    Фильтры:
      keyword_ids, campaign_ids, adgroup_ids — [int, ...]

    fields по умолчанию: KeywordId, AdGroupId, CampaignId, ServingStatus,
      SearchPrices, NetworkPrices.
      Вложенные поля SearchPrices / NetworkPrices содержат:
        Position (POSITION_1, POSITION_2, POSITION_3, …), Price.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Корректировки ставок. ⚠️ Обязательно campaign_ids ИЛИ adgroup_ids ИЛИ ids.

    Корректировки — проценты, на которые меняется ставка в зависимости от
    устройства, демографии, региона, времени, аудитории ретаргетинга.

    Цена: ~15 units + 1 unit на объект.

    Фильтры:
      campaign_ids, adgroup_ids, ids — [int, ...]
      types  — ['MOBILE_ADJUSTMENT','DEMOGRAPHICS_ADJUSTMENT',
                'RETARGETING_ADJUSTMENT','REGIONAL_ADJUSTMENT',
                'VIDEO_ADJUSTMENT','INCOME_ADJUSTMENT']
      levels — ['CAMPAIGN','AD_GROUP'] — уровень применения корректировки.
        Если не передан, инструмент запросит оба уровня.

    fields по умолчанию: Id, CampaignId, AdGroupId, Type, Level.

    subfields для получения самих коэффициентов по типу:
      MobileAdjustmentFieldNames, DemographicsAdjustmentFieldNames,
      RetargetingAdjustmentFieldNames, RegionalAdjustmentFieldNames,
      VideoAdjustmentFieldNames, IncomeAdjustmentFieldNames.
      Пример: subfields={"MobileAdjustmentFieldNames":["BidModifier","OsType"]}

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
    selection: dict = {}
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if adgroup_ids: selection["AdGroupIds"] = adgroup_ids
    if ids: selection["Ids"] = ids
    if types: selection["Types"] = types
    selection["Levels"] = levels or ["CAMPAIGN", "AD_GROUP"]
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
    """Наборы быстрых ссылок (sitelinks).

    Без фильтров вернёт все наборы пользователя.

    Фильтры:
      ids — [int, ...] ID наборов.

    fields по умолчанию: Id. Ещё доступны: Sitelinks (массив ссылок).

    subfields — для текстов ссылок:
      {"SitelinkFieldNames": ['Title','Href','Description','TurboPageId']}
      Пример:
        subfields={"SitelinkFieldNames":["Title","Href","Description"]}

    Ответ: {"items": [...], "count": N, "_units": {...}}.
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
    """Расширения объявлений (Callouts — уточнения).

    Без фильтров вернёт все расширения пользователя.

    Фильтры:
      ids      — [int, ...]
      types    — ['CALLOUT'] (на момент 2026 v5 поддерживает только Callout через этот метод)
      states   — ['ON','OFF']
      statuses — ['ACCEPTED','DRAFT','MODERATION','REJECTED']

    fields по умолчанию: Id, Type, State, Status.

    subfields — для текстов:
      {"CalloutFieldNames": ['CalloutText']}

    Ответ: {"items": [...], "count": N, "_units": {...}}.
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
    """Картинки, загруженные в кабинет.

    Без фильтров вернёт все картинки пользователя.

    Фильтры:
      hashes — [str, ...] хеши картинок (поле AdImageHash).
      types  — ['REGULAR','TURBO'] — обычные или турбо-страниц.

    fields по умолчанию: AdImageHash, Name, Type, Subtype, Associated.
      Associated — используется ли картинка в объявлениях.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Видео, загруженные в кабинет.

    Без фильтров вернёт все видео пользователя.

    Фильтры:
      hashes — [str, ...] хеши видео (поле AdVideoHash).

    fields по умолчанию: AdVideoHash, Name, Associated.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Визитки с контактами организации.

    Без фильтров вернёт все визитки пользователя.

    Фильтры:
      ids, campaign_ids — [int, ...]

    fields по умолчанию: Id, CampaignId, CompanyName, City, Country.
      Дополнительно доступны: WorkTime, Phone, ExtraMessage, InstantMessenger,
      MetroStationId, OgrnNumber, Email, Street, House, PointOnMap.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Креативы (шаблоны для смарт-баннеров, видео, текстовых баннеров).

    Без фильтров вернёт все креативы пользователя.

    Фильтры:
      ids   — [int, ...]
      types — ['SMART_CENTER','HTML5','VIDEO_EXTENSION',
               'CPC_VIDEO_CREATIVE','CPM_VIDEO_CREATIVE','CUSTOM']

    fields по умолчанию: Id, Name, Type.
      Дополнительно: ThumbnailUrl, PreviewUrl, Size, LayoutId, CreativeId.

    subfields по типу:
      VideoExtensionCreativeFieldNames, Html5CreativeFieldNames,
      CpcVideoCreativeFieldNames, CpmVideoCreativeFieldNames.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Общие наборы минус-слов/минус-фраз (shared).

    Без фильтров вернёт все наборы пользователя.
    (Для минус-слов уровня кампании используй поле NegativeKeywords
     в direct_campaigns_get, для уровня группы — в direct_adgroups_get.)

    Фильтры:
      ids — [int, ...]

    fields по умолчанию: Id, Name, NegativeKeywords.
      NegativeKeywords — объект с подмассивом Items (до 4 096 слов).

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Условия ретаргетинга и подбора аудиторий.

    Без фильтров вернёт все условия пользователя.

    Фильтры:
      ids   — [int, ...]
      types — ['RETARGETING_LIST','AUDIENCE_TARGET','LOOKALIKE','DYNAMIC']

    fields по умолчанию: Id, Name, Type, Description, IsAvailable.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Привязки аудиторий/ретаргетинга к группам объявлений.

    ⚠️ Обязательно передать ids ИЛИ campaign_ids ИЛИ adgroup_ids.

    Фильтры:
      ids, campaign_ids, adgroup_ids — [int, ...]
      states — ['ON','OFF','SUSPENDED']

    fields по умолчанию: Id, AdGroupId, CampaignId, State, RetargetingListId,
      InterestId, ContextBid, StrategyPriority.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Таргетинг умных баннеров (Smart Ads).

    ⚠️ Обязательно передать ids ИЛИ campaign_ids ИЛИ adgroup_ids.

    Фильтры:
      ids, campaign_ids, adgroup_ids — [int, ...]
      states — ['ON','OFF','SUSPENDED']

    fields по умолчанию: Id, AdGroupId, CampaignId, Name, State,
      AverageCpc, AverageCpa, StrategyPriority.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Таргетинги динамических текстовых объявлений (по страницам сайта).

    ⚠️ Обязательно передать ids ИЛИ campaign_ids ИЛИ adgroup_ids.

    Фильтры:
      ids, campaign_ids, adgroup_ids — [int, ...]
      states — ['ON','OFF','SUSPENDED']

    fields по умолчанию: Id, AdGroupId, CampaignId, Name, State,
      Conditions, ConditionType, Bid, StrategyPriority.
      Conditions — правило отбора страниц (список операций типа URL/TITLE EQUALS/CONTAINS).

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Товарные фиды (XML/CSV/YML), используемые в смарт-баннерах и динамических объявлениях.

    Без фильтров вернёт все фиды пользователя.

    Фильтры:
      ids — [int, ...]

    fields по умолчанию: Id, Name, BusinessType, SourceType.
      BusinessType: RETAIL, AUTO, REALTY, TRAVEL, HOTEL, JOB_SEARCH, AVIATION, OTHER.
      SourceType:   FILE, URL.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Турбо-страницы пользователя.

    Без фильтров вернёт все Турбо-страницы пользователя.

    Фильтры:
      ids — [int, ...]

    fields по умолчанию: Id, Name.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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
    """Бизнес-профили рекламодателя (связанные с Яндекс.Бизнесом).

    Без фильтров вернёт все бизнес-профили.

    Фильтры:
      ids — [int, ...]

    fields по умолчанию: Id, Name.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
    selection = {"Ids": ids} if ids else {}
    items = _generic_get("businesses", "Businesses", selection=selection,
                         fields=fields or DEFAULT_FIELDS["businesses"],
                         max_results=max_results, fetch_all=fetch_all)
    return _pack(items, "businesses")


@mcp.tool()
def direct_leads_get(
    ids: list[int] | None = None,
    campaign_ids: list[int] | None = None,
    turbo_page_ids: list[int] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    fields: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_all: bool = False,
) -> dict:
    """Лиды, полученные через формы в объявлениях.

    ⚠️ Обязательно передать DateRange (date_from+date_to) и фильтр.
    В текущем Direct API для лидов может требоваться TurboPageIds; если
    CampaignIds недостаточно, передай turbo_page_ids.

    Фильтры:
      ids          — [int, ...] точные ID лидов.
      campaign_ids — [int, ...] ID кампаний, из которых берём лиды.
      turbo_page_ids — [int, ...] ID турбо-страниц/форм.
      date_from    — 'YYYY-MM-DD' начало диапазона.
      date_to      — 'YYYY-MM-DD' конец диапазона (включительно).

    fields по умолчанию: Id, AdId, CampaignId, Name.
      Дополнительно: SubmissionDatetime, FieldValues (массив пар name/value
      с данными из формы — телефон, email, имя и т.п.).

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
    selection: dict = {}
    if ids: selection["Ids"] = ids
    if campaign_ids: selection["CampaignIds"] = campaign_ids
    if turbo_page_ids: selection["TurboPageIds"] = turbo_page_ids
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
    """Справочники Direct API (глобальные, не зависят от клиента).

    names — список названий справочников, перечисли нужные:
      GeoRegions                     — дерево регионов РФ и мира (большой).
      Currencies                     — валюты с параметрами (мин/макс ставка и т.п.).
      TimeZones                      — часовые пояса.
      AdCategories                   — тематические категории объявлений.
      Constants                      — служебные константы API.
      Interests                      — категории интересов пользователей.
      OperationSystemVersions        — версии ОС для таргетинга мобильных.
      ProductivityTargetCategories   — категории для подбора видеообъявлений.
      SupplySidePlatforms            — SSP-платформы.
      VideoIABCategories             — IAB-категории видеообъявлений (если доступны).

    GeoRegions возвращает порядка 30k строк — ответ автоматически
    складывается в cache/. Читай чанками:
      read_cached(path, key='GeoRegions', offset=0, limit=100)

    Ответ: {"_units": {...}, <имя_справочника>: [...], ...} либо,
    если большой: {"cached_to": "...", "preview": {...}}.
    """
    data = _call("dictionaries", "get", {"DictionaryNames": names})
    return _wrap_dict(data.get("result", {}), "dictionaries")


@mcp.tool()
def direct_client_get(fields: list[str] | None = None) -> dict:
    """Данные владельца токена (или клиента из CLIENT_LOGIN).

    Возвращает: логин, ClientId, валюту, лимиты, настройки, уведомления.

    ⚠️ Баланс рекламного счёта в Direct API v5 НЕ доступен —
      смотри в balance.yandex.ru или в веб-кабинете Директа.
      Косвенные сигналы есть в Restrictions (квоты) и AccountQuality.

    fields — по умолчанию максимальный набор: AccountQuality, ClientId, ClientInfo,
      CountryId, Currency, Grants, Login, Notification, Phone, Restrictions,
      Settings, Type, VatRate.
      Type — 'CLIENT' | 'AGENCY' | 'REPRESENTATIVE'.

    Ответ: {"_units": {...}, "Clients": [{...}]}.
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
    """Клиенты агентства. Работает только если токен выдан АГЕНТСТВОМ.

    Для обычного клиентского токена вернёт 54 «Нет прав для доступа в агентский сервис».

    Фильтры:
      logins   — [str, ...] конкретные логины клиентов.
      archived — bool, показать архивных (True) или активных (False).

    fields — полный набор по клиенту: AccountQuality, ClientId, ClientInfo,
      Currency, Grants, Login, Notification, Phone, Representatives,
      Restrictions, Settings, Type, VatRate.

    Ответ: {"items": [...], "count": N, "_units": {...}}.
    """
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


CHANGE_CHECK_FIELDS = {"CampaignIds", "AdGroupIds", "AdIds", "CampaignsStat"}
CHANGE_CHECK_FIELD_ALIASES = {"Statistics": "CampaignsStat"}


def _changed_campaign_ids(result: dict) -> list[int]:
    """Normalize old/new checkCampaigns response shapes to plain campaign IDs."""
    raw = result.get("Ids")
    if raw is None:
        raw = result.get("Campaigns", [])

    ids: list[int] = []
    for item in raw or []:
        if isinstance(item, int):
            ids.append(item)
        elif isinstance(item, dict):
            cid = item.get("CampaignId") or item.get("Id")
            if cid is not None:
                ids.append(int(cid))
    return ids


def _change_check_fields(field_names: list[str] | None) -> tuple[list[str], list[str]]:
    """Normalize deprecated field aliases from earlier tool descriptions."""
    requested = field_names or ["CampaignIds", "AdGroupIds", "AdIds"]
    fields: list[str] = []
    warnings: list[str] = []
    for name in requested:
        if name in CHANGE_CHECK_FIELD_ALIASES:
            replacement = CHANGE_CHECK_FIELD_ALIASES[name]
            warnings.append(f"{name} устарело; использую {replacement}")
            name = replacement
        if name == "TargetIds":
            warnings.append("TargetIds больше не поддерживается changes.check и пропущен")
            continue
        if name not in CHANGE_CHECK_FIELDS:
            warnings.append(f"{name} не поддерживается changes.check и пропущен")
            continue
        if name not in fields:
            fields.append(name)
    if not fields:
        raise RuntimeError(
            "Нет валидных FieldNames для changes.check. "
            "Доступны: CampaignIds, AdGroupIds, AdIds, CampaignsStat"
        )
    return fields, warnings


@mcp.tool()
def direct_changes_dictionaries(timestamp: str | int | None = None) -> dict:
    """Проверка, менялись ли глобальные справочники (changes.checkDictionaries).

    timestamp: момент, с которого проверяем.
      Формат: ISO8601 UTC ('YYYY-MM-DDThh:mm:ssZ') или Unix seconds (int).
      Если не указан — вернёт текущий Timestamp сервера (как точку отсчёта).
    ⚠️ Timestamp не должен быть старше 7 суток назад.

    Полезно вызывать ПЕРВЫМ в сценарии аудита — чтобы понять, не
    пересчитались ли справочники регионов/валют.

    Ответ: {"_units": {...}, "Timestamp": "...", "Regions": true/false,
            "TimeTargeting": true/false}.
    """
    params: dict = {}
    if timestamp is not None:
        params["Timestamp"] = _to_iso_utc(timestamp)
    data = _call("changes", "checkDictionaries", params)
    return {"_units": _units.snapshot(), **data.get("result", {})}


@mcp.tool()
def direct_changes_campaigns(timestamp: str | int) -> dict:
    """Какие кампании изменились с момента X (changes.checkCampaigns).

    timestamp (обязательно): ISO8601 UTC ('YYYY-MM-DDThh:mm:ssZ') или Unix seconds.
    ⚠️ Timestamp не должен быть старше 7 суток назад (API вернёт ошибку).

    Используй как шаг 2 в аудите: взял список изменённых Ids — потом
    direct_changes_check(campaign_ids=...) для подробностей.

    API может вернуть кампании как Campaigns=[{"CampaignId":..., "ChangesIn":[...]}].
    Инструмент нормализует это в Ids=[...], сохраняя исходные поля ответа.

    Ответ: {"_units": {...}, "Timestamp": "...", "Campaigns": [...],
            "Ids": [...campaign_ids...]}.
    """
    data = _call("changes", "checkCampaigns",
                 {"Timestamp": _to_iso_utc(timestamp)})
    result = data.get("result", {})
    return {"_units": _units.snapshot(), **result, "Ids": _changed_campaign_ids(result)}


@mcp.tool()
def direct_changes_check(
    campaign_ids: list[int],
    timestamp: str | int,
    field_names: list[str] | None = None,
) -> dict:
    """Детальный дифф изменений в кампаниях (changes.check).

    campaign_ids (обязательно): [int, ...] до 1000 штук. Обычно берутся
      из direct_changes_campaigns().Ids.
    timestamp    (обязательно): ISO8601 UTC или Unix seconds.
      ⚠️ Не старше 7 суток назад.
    field_names: подмножество ['CampaignIds','AdGroupIds','AdIds','CampaignsStat'].
      По умолчанию ['CampaignIds','AdGroupIds','AdIds'].
      Старое имя Statistics автоматически заменяется на CampaignsStat,
      старое TargetIds пропускается, потому что API его больше не принимает.

    Ответ содержит массивы Ids изменённых сущностей каждого уровня.

    Ответ: {"_units": {...}, "Timestamp": "...", "Campaigns":[...],
            "AdGroups":[...], "Ads":[...], "CampaignsStat":[...]}.
    """
    fields, warnings = _change_check_fields(field_names)
    data = _call("changes", "check", {
        "CampaignIds": campaign_ids,
        "Timestamp": _to_iso_utc(timestamp),
        "FieldNames": fields,
    })
    result = _wrap_dict(data.get("result", {}), "changes_check")
    if warnings:
        result["_warnings"] = warnings
    return result


@mcp.tool()
def direct_audit_changes_since(
    hours_back: int = 24,
    field_names: list[str] | None = None,
) -> dict:
    """Composite: «что изменилось за N часов» — готовая связка трёх вызовов.

    Что делает:
      1) checkDictionaries(Timestamp = now − N ч)
      2) checkCampaigns   — получить Ids изменившихся кампаний
      3) check            — детальный дифф по каждой батчами до 1000 ID

    Параметры:
      hours_back — окно в часах (1..168). Больше 168 обрежется до 168
        (ограничение API — 7 суток).
      field_names — что включить в дифф (см. direct_changes_check).

    Стоимость: ~3 вызова + по 1 на каждые 1000 изменённых кампаний.

    Ответ: {"_units": {...}, "window_hours": N, "since": "ISO",
            "dictionaries": {...}, "changed_campaign_ids": [...],
            "changed_campaign_count": N, "diffs": [{...}, ...]}.
    """
    hours = min(hours_back, 168)
    iso = _to_iso_utc(int(time.time()) - hours * 3600)

    dict_data = _call("changes", "checkDictionaries", {"Timestamp": iso})
    camp_data = _call("changes", "checkCampaigns", {"Timestamp": iso})
    camp_result = camp_data.get("result", {})
    changed_camp_ids = _changed_campaign_ids(camp_result)
    fields, warnings = _change_check_fields(field_names)

    diffs: list[dict] = []
    if changed_camp_ids:
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
        "changed_campaigns": camp_result.get("Campaigns", []),
        "field_names_used": fields,
        "warnings": warnings,
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
    """Отчёт Direct API (async). TSV сохраняется в cache/, путь возвращается.

    Стоимость: отдельная квота Reports (до 5 отчётов в очереди), не тратит
    обычные units get-операций.

    ——— report_type (обязательно) ———
      CAMPAIGN_PERFORMANCE_REPORT          — по кампаниям (показы, клики, расход)
      ADGROUP_PERFORMANCE_REPORT           — по группам объявлений
      AD_PERFORMANCE_REPORT                — по объявлениям
      CRITERIA_PERFORMANCE_REPORT          — по ключевым фразам/таргетингам
      SEARCH_QUERY_PERFORMANCE_REPORT      — реальные поисковые запросы (для минусовки)
      CUSTOM_REPORT                        — произвольная агрегация
      REACH_AND_FREQUENCY_PERFORMANCE_REPORT — охваты/частота (для CPM)

    ——— field_names (обязательно) ———
    Базовые измерения (для группировки):
      Date, CampaignId, CampaignName, CampaignType,
      AdGroupId, AdGroupName, AdId, AdFormat, AdNetworkType,
      Criterion, CriterionId, CriterionType, MatchedKeyword, Keyword,
      Query (только для SEARCH_QUERY_PERFORMANCE_REPORT),
      Device, CarrierType, ClickType, Gender, Age, Placement,
      LocationOfPresenceId, LocationOfPresenceName, TargetingLocationId,
      TargetingLocationName.
    Базовые метрики:
      Impressions, Clicks, Cost, Ctr, AvgCpc, AvgImpressionPosition,
      AvgClickPosition, AvgTrafficVolume, Bounces, BounceRate,
      Conversions, ConversionRate, CostPerConversion, Revenue, GoalsRoi,
      AvgPageviews, Sessions.
    ⚠️ Разрешены не все комбинации полей и типов отчёта — свериться
    с таблицей «поддерживаемые поля» в документации при выборе.

    ——— date_range_type ———
      CUSTOM_DATE — требует date_from+date_to в формате 'YYYY-MM-DD'.
      TODAY, YESTERDAY, LAST_3_DAYS, LAST_5_DAYS, LAST_7_DAYS, LAST_14_DAYS,
      LAST_30_DAYS, LAST_90_DAYS, LAST_365_DAYS, THIS_WEEK_MON_TODAY,
      THIS_WEEK_SUN_TODAY, LAST_WEEK, LAST_BUSINESS_WEEK, LAST_WEEK_SUN_SAT,
      THIS_MONTH, LAST_MONTH, ALL_TIME, AUTO.
    Для этих значений date_from/date_to НЕ передаются.

    ——— filters (опционально) ———
      Список условий вида:
        [{"Field":"CampaignId","Operator":"IN","Values":["12345","67890"]}]
      Operator: EQUALS, NOT_EQUALS, IN, NOT_IN, LESS_THAN, GREATER_THAN,
                STARTS_WITH_IGNORE_CASE, DOES_NOT_START_WITH_IGNORE_CASE.

    ——— Остальное ———
      goals              — [int, ...] ID целей Метрики для построения конверсий.
      attribution_models — ['LSC','FC','LC','LYDC','MCSC','FCCD']
                           (LastSignificantClick, First, Last, LastYandex…).
      order_by           — [{"Field":"Clicks","SortOrder":"DESCENDING"}, ...]
      include_vat, include_discount — True/False (по умолчанию True).
      max_wait_sec       — таймаут polling'а (по умолчанию 600).

    ——— Что возвращается ———
      {"path": "cache/report_*.tsv", "rows": N, "size_bytes": B,
       "preview_top10": [...], "hint": "read_cached_tsv(...)"}.
    Полные строки — через read_cached_tsv(path, offset, limit).

    Пример: отчёт по запросам за последние 30 дней, топ по кликам.
      direct_report(
        report_type="SEARCH_QUERY_PERFORMANCE_REPORT",
        field_names=["Date","CampaignName","Query","Impressions","Clicks","Cost"],
        date_range_type="LAST_30_DAYS",
        order_by=[{"Field":"Clicks","SortOrder":"DESCENDING"}])
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
    """Чтение закешированного JSON-ответа чанками.

    Кеш-файлы появляются автоматически, когда тул возвращает «cached_to:…».

    Параметры:
      path   (обязательно) — значение из поля `cached_to` предыдущего ответа.
      offset — сколько элементов пропустить с начала (по умолч. 0).
      limit  — сколько элементов вернуть (по умолч. 50, максимум разумно 500).
      key    — имя конкретного массива в JSON. Нужно для dictionaries
               (где в одном файле могут быть GeoRegions + Currencies + ...).
               Без key тул автоматически ищет 'results' или 'items'.

    Ответ: {"slice":[...N элементов], "offset":N, "returned":N, "total":N,
            "has_more": true/false, "available_keys":[...имена массивов в файле...]}.
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
    """Чтение TSV-отчёта Reports API чанками.

    Путь берётся из ответа direct_report (поле `path`).

    Параметры:
      path   (обязательно) — путь к TSV-файлу в cache/.
      offset — сколько строк пропустить (без заголовка).
      limit  — сколько строк вернуть.

    Каждая строка парсится по заголовкам TSV в dict {колонка: значение}.
    Денежные значения приходят в минимальных единицах × 1 000 000 (микро)
    только если в запросе `returnMoneyInMicros=true` — по умолчанию в обёртке false.

    Ответ: {"slice":[{"Колонка":"значение",...}], "offset":N, "returned":N,
            "total":N, "has_more":true/false}.
    """
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
    """Найти кампанию по подстроке в имени или точному ID.

    Сначала внутри вызывает direct_campaigns_get (дешёвый минимум полей),
    затем фильтрует локально. Возвращает до 30 совпадений.

    query — строка. Если это число-строка — ищется ещё и точное совпадение по Id.

    Ответ: {"_units": {...}, "matches":[{...}], "total_matches": N}.
    """
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
    """Найти группу объявлений по подстроке в имени.

    campaign_id — если знаешь конкретную кампанию, передай её Id, это
      дешевле (1 запрос вместо 2).
    Без campaign_id — тул сам подгрузит все кампании и пройдёт по ним.

    Ответ: {"_units": {...}, "matches":[{...}], "total_matches": N}.
    """
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
    """Найти ключевую фразу по подстроке.

    Приоритет фильтров: adgroup_id → campaign_id → всё. Чем уже скоуп,
    тем дешевле вызов (ключей может быть тысячи).

    Ответ: {"_units": {...}, "matches":[{...}], "total_matches": N}.
    """
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
    """Текущий остаток units (баллов) API-квоты.

    Внутри делает самый дешёвый запрос — campaigns.get Limit=1 — и вытаскивает
    значения из заголовка `units`. Рекомендуется вызывать ПЕРЕД большими
    операциями (например, перед fetch_all=True или перед большим отчётом).

    Ответ: {"rest": int, "daily_limit": int, "spent_this_call": int,
            "spent_session": int}.
    """
    _call("campaigns", "get", {
        "SelectionCriteria": {}, "FieldNames": ["Id"],
        "Page": {"Limit": 1, "Offset": 0},
    })
    return _units.snapshot()


@mcp.tool()
def account_summary(lightweight: bool = True) -> dict:
    """Быстрая сводка по кабинету: сколько кампаний, групп, объявлений, ключей.

    Логика: сначала выкачивает список кампаний, дальше запрашивает
    остальные сущности с фильтром CampaignIds по всем кампаниям
    (иначе API возвращает 8000).

    lightweight=True (по умолчанию) — возвращает только количества.
    lightweight=False — дополнительно полный список кампаний (без остального).

    Стоимость: при lightweight обычно 50-200 units (зависит от размера кабинета).

    Ответ: {"_units_before": {...}, "campaigns_count": N, "adgroups_count": N,
            "ads_count": N, "keywords_count": N, "_units_after": {...}}.
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
    """Грубая оценка стоимости планируемого вызова в units (без похода в API).

    Эмпирика:
      - Фиксированная стоимость метода: 10-15 units за вызов (зависит от сервиса).
      - ~0.5-1 unit на объект при дешёвых полях.
      - Для полей Productivity / Statistics / Stat цена удорожается в 2-5 раз.
      - Пагинация: +фиксированная стоимость за каждый дополнительный Page.get.

    Параметры:
      service          — имя сервиса (для логов, на расчёт не влияет).
      expected_objects — сколько объектов ожидаешь вернуть.
      expected_fields  — сколько полей в FieldNames (по умолч. 5).

    Ответ: {"service":..., "expected_objects":..., "pages":..., "estimate_low":...,
            "estimate_high":..., "current_rest":..., "daily_limit":..., "hint":"..."}.
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


# ─── wordstat & forecasts (через legacy API v4 Live) ────────────────────────
#
# В Direct API v5 сервисы wordstatreports и forecasts отсутствуют,
# поэтому используется устаревший, но рабочий endpoint v4 Live:
#   https://api.direct.yandex.ru/live/v4/json/
# Квота v4 своя — на скрине «Осталось баллов (API версии 4 и Live 4): 32 000».


BASE_V4_LIVE = "https://api.direct.yandex.ru/live/v4/json/"


def _v4_call(method: str, param: Any = None) -> Any:
    """Вызов legacy v4 Live endpoint. Возвращает поле `data` при успехе."""
    token = os.getenv("YANDEX_DIRECT_OAUTH")
    if not token:
        raise RuntimeError("Задай YANDEX_DIRECT_OAUTH")
    body: dict = {"method": method, "token": token, "locale": "ru"}
    if param is not None:
        body["param"] = param
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    if login := os.getenv("YANDEX_DIRECT_CLIENT_LOGIN"):
        headers["Client-Login"] = login

    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = httpx.post(BASE_V4_LIVE, content=raw, headers=headers, timeout=HTTP_TIMEOUT)
        except httpx.HTTPError as e:
            last_err = e
            time.sleep(_backoff(attempt))
            continue
        if r.status_code in RETRY_STATUS:
            last_err = RuntimeError(f"HTTP {r.status_code}")
            time.sleep(_backoff(attempt, r.headers.get("Retry-After")))
            continue
        if r.status_code != 200:
            _log_audit({"api": "v4", "method": method, "status": r.status_code,
                        "body": r.text[:500]})
            r.raise_for_status()
        data = r.json()
        if "error_code" in data:
            code = data.get("error_code")
            if code in RETRY_ERROR_CODES:
                last_err = RuntimeError(f"v4 error {code}")
                time.sleep(_backoff(attempt))
                continue
            _log_audit({"api": "v4", "method": method, "error": data})
            raise RuntimeError(
                f"Direct v4 error {code}: {data.get('error_str')} — "
                f"{data.get('error_detail', '')}"
            )
        _log_audit({"api": "v4", "method": method, "ok": True})
        return data.get("data")
    raise RuntimeError(f"Retries exhausted for v4 {method}: {last_err}")


def _v4_wait_done(list_method: str, report_id: int,
                  max_wait_sec: int, poll_interval: int = 5) -> None:
    """Ждём StatusReport=Done в ответе list-метода."""
    start = time.time()
    while True:
        lst = _v4_call(list_method) or []
        mine = next((r for r in lst if r.get("ReportID") == report_id), None)
        if mine:
            status = mine.get("StatusReport")
            if status == "Done":
                return
            if status == "Failed":
                raise RuntimeError(f"v4 отчёт {list_method}#{report_id} упал с ошибкой")
        if time.time() - start > max_wait_sec:
            raise TimeoutError(
                f"v4 отчёт {list_method}#{report_id} не готов за {max_wait_sec}s"
            )
        time.sleep(poll_interval)


def _v4_safe_delete(delete_method: str, report_id: int) -> None:
    try:
        _v4_call(delete_method, report_id)
    except Exception:
        pass


@mcp.tool()
def direct_wordstat_report(
    phrases: list[str],
    geo_ids: list[int] | None = None,
    max_wait_sec: int = 300,
    keep_report: bool = False,
) -> dict:
    """Частотность фраз через legacy Direct API v4 Live.

    Использует отдельную квоту v4 (на скрине «Осталось баллов v4 = 32 000»),
    не пересекается с Cloud Wordstat API (Search API). Удобно, когда там
    закончилась суточная квота.

    Параметры:
      phrases — [str, ...] до 10 фраз за один запрос.
        Синтаксис: "купить теплицу" (широкое),
        '"купить теплицу"' (фразовое), '!купить !теплицу' (точное),
        'купить -дёшево' (исключение).
      geo_ids — [int, ...] до 7 регионов. Без параметра — вся Россия.
        ID регионов: Пермь=50, Екатеринбург=54, Ижевск=44, Тюмень=55,
        Москва=213, Санкт-Петербург=2.
      max_wait_sec — таймаут polling'а (по умолч. 300).
      keep_report — True: не удалять отчёт, освобождение слота не произойдёт.

    Что возвращает:
      Items[] — по одному элементу на каждую фразу. Внутри:
        Phrase — исходная фраза.
        GeoID  — регионы.
        SearchedWith — массив {Phrase, Shows} — основная колонка Wordstat.
        SearchedAlso — массив {Phrase, Shows} — правая колонка (связанные).

    Пример:
      direct_wordstat_report(
        phrases=["теплица пермь","купить теплицу в перми"],
        geo_ids=[50])

    ⚠️ Ограничения: 10 фраз и 7 регионов за вызов, 5 отчётов одновременно в очереди.
    """
    if len(phrases) > 10:
        raise ValueError("Максимум 10 фраз за один отчёт")
    if geo_ids and len(geo_ids) > 7:
        raise ValueError("Максимум 7 регионов за один отчёт")

    param: dict = {"Phrases": phrases}
    if geo_ids:
        param["GeoID"] = geo_ids

    report_id = _v4_call("CreateNewWordstatReport", param)
    if not isinstance(report_id, int):
        raise RuntimeError(f"Ожидался ReportID (int), получено: {report_id!r}")

    try:
        _v4_wait_done("GetWordstatReportList", report_id, max_wait_sec)
        items = _v4_call("GetWordstatReport", report_id) or []
    finally:
        if not keep_report:
            _v4_safe_delete("DeleteWordstatReport", report_id)

    return _wrap_dict({"ReportID": report_id, "Items": items}, "wordstat_report")


@mcp.tool()
def direct_forecast(
    phrases: list[str],
    geo_ids: list[int] | None = None,
    max_wait_sec: int = 300,
    keep_report: bool = False,
) -> dict:
    """Прогноз показов/кликов/расходов по фразам (Direct v4 Live Forecast API).

    Использует legacy v4 (в v5 forecasts нет). Квота v4 отдельная.

    Параметры:
      phrases — [str, ...] до 10 фраз (v4-лимит).
      geo_ids — [int, ...] регионы. Без параметра — вся Россия.
      max_wait_sec — таймаут polling'а.
      keep_report — True: не удалять после получения.

    Что возвращает:
      Phrases[] — по элементу на фразу. Внутри:
        Phrase, IsRubric (bool), Min/Max (диапазон позиций),
        PremiumMin, PremiumMax, Shows, Clicks,
        FirstPlaceClicks, PremiumClicks, CTR, FirstPlaceCTR, PremiumCTR.

    Пример:
      direct_forecast(
        phrases=["теплица пермь","купить теплицу в перми"],
        geo_ids=[50])

    ⚠️ Ограничения: до 10 фраз за вызов, 5 прогнозов в очереди, хранятся 5 часов.
    """
    if len(phrases) > 10:
        raise ValueError("Максимум 10 фраз за один прогноз")

    param: dict = {"Phrases": phrases}
    if geo_ids:
        param["GeoID"] = geo_ids

    report_id = _v4_call("CreateNewForecast", param)
    if not isinstance(report_id, int):
        raise RuntimeError(f"Ожидался ForecastID (int), получено: {report_id!r}")

    try:
        _v4_wait_done("GetForecastList", report_id, max_wait_sec)
        data = _v4_call("GetForecast", report_id)
    finally:
        if not keep_report:
            _v4_safe_delete("DeleteForecastReport", report_id)

    return _wrap_dict({"ForecastID": report_id, **(data or {})}, "forecast")


@mcp.tool()
def direct_async_queue_status(kind: str) -> dict:
    """Очередь async-отчётов v4 (когда слоты "5 в очереди" забиты).

    kind: 'wordstat' | 'forecast'.

    Ответ: {"kind":..., "count":N, "reports":[{"ReportID":..., "StatusReport":...}, ...]}.
    """
    if kind == "wordstat":
        lst = _v4_call("GetWordstatReportList") or []
    elif kind == "forecast":
        lst = _v4_call("GetForecastList") or []
    else:
        raise ValueError("kind: 'wordstat' | 'forecast'")
    return {"kind": kind, "count": len(lst), "reports": lst}


@mcp.tool()
def direct_async_delete(kind: str, report_id: int) -> dict:
    """Удалить async-отчёт v4 вручную (освободить слот в очереди из 5).

    kind: 'wordstat' | 'forecast'.
    report_id: ReportID из direct_async_queue_status.
    """
    if kind == "wordstat":
        res = _v4_call("DeleteWordstatReport", report_id)
    elif kind == "forecast":
        res = _v4_call("DeleteForecastReport", report_id)
    else:
        raise ValueError("kind: 'wordstat' | 'forecast'")
    return {"kind": kind, "deleted_id": report_id, "result": res}


if __name__ == "__main__":
    mcp.run()
