"""CMS Medicare Coverage Database API client — NCDs, LCDs, Articles."""

import httpx

BASE_URL = "https://api.coverage.cms.gov/v1"
_client = httpx.AsyncClient(timeout=15.0)

# License token for LCD/Article endpoints (free, refreshes hourly)
_license_token: str | None = None


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


async def get_ncd(ncd_id: str) -> dict | None:
    """Get a National Coverage Determination by ID."""
    resp = await _client.get(f"{BASE_URL}/data/ncd/{ncd_id}")
    if resp.status_code in (400, 404):
        return None
    resp.raise_for_status()
    return resp.json()


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
    """Search NCDs by keyword using the NCD report endpoint."""
    resp = await _client.get(f"{BASE_URL}/data/ncd-report/annual")
    if resp.status_code != 200:
        return []

    data = resp.json()
    keyword_lower = keyword.lower()
    results = []

    for item in data if isinstance(data, list) else data.get("results", data.get("data", [])):
        title = str(item.get("title", item.get("ncdTitle", "")))
        ncd_id = str(item.get("ncdId", item.get("id", "")))
        if keyword_lower in title.lower():
            results.append({
                "ncd_id": ncd_id,
                "title": title,
            })

    return results[:20]


async def get_sad_exclusion_list() -> list[dict]:
    """Get the Self-Administered Drug (SAD) Exclusion List."""
    resp = await _client.get(f"{BASE_URL}/data/sad-exclusion-list")
    if resp.status_code != 200:
        return []
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else data.get("results", data.get("data", []))
