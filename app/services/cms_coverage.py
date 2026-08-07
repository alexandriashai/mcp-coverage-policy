"""CMS Medicare Coverage Database API client — NCDs, LCDs, Articles."""

import asyncio
import json
import time
from pathlib import Path

import httpx

BASE_URL = "https://api.coverage.cms.gov/v1"
_client = httpx.AsyncClient(timeout=15.0)

# License token for LCD/Article endpoints (free, refreshes hourly)
_license_token: str | None = None

# NCD display_id -> document_id index. The API has no list endpoint, so this is
# built by enumeration once and cached; NCDs change on the order of months.
_INDEX_PATH = Path.home() / ".cache" / "mcp-coverage" / "ncd-index.json"
_TITLES_PATH = Path.home() / ".cache" / "mcp-coverage" / "ncd-titles.json"
_INDEX_TTL_SECONDS = 30 * 24 * 3600
_INDEX_SCAN_MAX = 600  # 357 NCDs found in 1..400 on 2026-08-06; headroom for new ones
_index_cache: dict[str, str] | None = None
_titles_cache: dict[str, str] | None = None


async def _get_license_token() -> str:
    """Get or refresh the license agreement token required for LCD/Article endpoints."""
    global _license_token
    if _license_token:
        return _license_token

    resp = await _client.get(f"{BASE_URL}/metadata/license-agreement")
    resp.raise_for_status()
    data = resp.json()
    _license_token = data.get("token", "")
    return _license_token


async def _fetch_ncd_by_document_id(document_id: int | str) -> dict | None:
    """One NCD by its INTERNAL document_id, via the query parameter the API actually takes."""
    resp = await _client.get(f"{BASE_URL}/data/ncd", params={"ncdid": str(document_id)})
    if resp.status_code in (400, 404):
        return None
    resp.raise_for_status()
    rows = resp.json().get("data") or []
    return rows[0] if rows else None


async def _build_ncd_index() -> dict[str, str]:
    """
    Map display_id ("140.9") -> document_id ("368") by walking the id space.

    The API offers no list, search, or alphabetical endpoint — /data/ncd-report/annual,
    /data/ncd-alphabetical-index and a bare /data/ncd all return 400, and /docs/v1/swagger
    404s — so enumeration is the only way to resolve a display id. ~357 NCDs live in
    1..400; the scan runs once and is cached on disk.
    """
    sem = asyncio.Semaphore(12)

    async def one(i: int) -> tuple[str, str] | None:
        async with sem:
            try:
                row = await _fetch_ncd_by_document_id(i)
            except Exception:
                return None
        if not row:
            return None
        disp = str(row.get("document_display_id") or "").strip()
        return (disp, str(row.get("document_id"))) if disp else None

    pairs = await asyncio.gather(*(one(i) for i in range(1, _INDEX_SCAN_MAX + 1)))
    return {d: n for p in pairs if p for d, n in [p]}


async def _ncd_index() -> dict[str, str]:
    """Cached display_id -> document_id map. Disk cache survives restarts."""
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    try:
        if _INDEX_PATH.exists():
            age = time.time() - _INDEX_PATH.stat().st_mtime
            if age < _INDEX_TTL_SECONDS:
                _index_cache = json.loads(_INDEX_PATH.read_text())
                return _index_cache
    except Exception:
        pass  # a corrupt or unreadable cache is a rebuild, never a failure

    _index_cache = await _build_ncd_index()
    try:
        _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        _INDEX_PATH.write_text(json.dumps(_index_cache))
    except Exception:
        pass  # cache is an optimisation; a read-only FS must not break lookups
    return _index_cache


async def get_ncd(ncd_id: str) -> dict | None:
    """
    Get a National Coverage Determination by its PUBLISHED id, e.g. "140.9".

    Two bugs lived here (found 2026-08-06, both silent):

      1. The request was `GET /data/ncd/{id}` — a path segment. The API takes
         `GET /data/ncd?ncdid={id}` and 400s on the path form.
      2. Callers pass the published id ("240.4", "140.9") but the API keys on an
         internal `document_id` ("270", "368"). Even with the URL right, a published
         id is rejected.

    Both surfaced as `None`, which `lookup_ncd` reported as "NCD X not found" — the
    tool's own documented example ("240.4") returned not-found, so every answer it
    ever gave was that string. A broken lookup that says "not found" reads exactly
    like a correct lookup of something absent, which is how it survived: the failure
    was indistinguishable from the answer. It also made the tool actively misleading
    on this box's live work — "no NCD for gender-affirming surgery" looked confirmed
    while NCD 140.9 was sitting in the database.
    """
    key = str(ncd_id).strip()

    # A bare integer is already an internal document_id — accept both id spaces.
    if key.isdigit():
        row = await _fetch_ncd_by_document_id(key)
        if row:
            return row

    document_id = (await _ncd_index()).get(key)
    return await _fetch_ncd_by_document_id(document_id) if document_id else None


async def get_lcd(lcd_id: str) -> dict | None:
    """Get a Local Coverage Determination by ID (requires license token)."""
    token = await _get_license_token()
    resp = await _client.get(
        f"{BASE_URL}/data/lcd/{lcd_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code in (400, 404):
        return None
    if resp.status_code == 401:
        _license_token = None  # Token expired, will refresh on next call
        return None
    resp.raise_for_status()
    return resp.json()


async def search_ncds(keyword: str) -> list[dict]:
    """
    Search NCDs by title keyword.

    Was hitting /data/ncd-report/annual, which 400s — so this returned [] for every
    keyword ever passed, and an empty result set is not distinguishable from "no NCD
    matches". Now filters the cached title index built by _build_ncd_index().
    """
    index = await _ncd_index()
    if not index:
        return []

    titles = await _ncd_titles()
    kw = keyword.lower()
    return [
        {"ncd_id": disp, "title": title}
        for disp, title in sorted(titles.items())
        if kw in title.lower()
    ][:20]


async def _ncd_titles() -> dict[str, str]:
    """display_id -> title, cached alongside the id index."""
    global _titles_cache
    if _titles_cache is not None:
        return _titles_cache
    try:
        if _TITLES_PATH.exists() and time.time() - _TITLES_PATH.stat().st_mtime < _INDEX_TTL_SECONDS:
            _titles_cache = json.loads(_TITLES_PATH.read_text())
            return _titles_cache
    except Exception:
        pass

    index = await _ncd_index()
    sem = asyncio.Semaphore(12)

    async def one(disp: str, doc: str) -> tuple[str, str] | None:
        async with sem:
            try:
                row = await _fetch_ncd_by_document_id(doc)
            except Exception:
                return None
        return (disp, str(row.get("title") or "")) if row else None

    pairs = await asyncio.gather(*(one(d, n) for d, n in index.items()))
    _titles_cache = {d: t for p in pairs if p for d, t in [p]}
    try:
        _TITLES_PATH.write_text(json.dumps(_titles_cache))
    except Exception:
        pass
    return _titles_cache


async def get_sad_exclusion_list() -> list[dict]:
    """Get the Self-Administered Drug (SAD) Exclusion List."""
    resp = await _client.get(f"{BASE_URL}/data/sad-exclusion-list")
    if resp.status_code != 200:
        return []
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else data.get("results", data.get("data", []))
