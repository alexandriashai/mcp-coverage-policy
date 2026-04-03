"""eCFR (Electronic Code of Federal Regulations) client."""

import httpx

BASE_URL = "https://www.ecfr.gov/api"
_client = httpx.AsyncClient(timeout=15.0)

# Insurance-critical CFR titles
INSURANCE_TITLES = {
    "42": "Public Health (CMS/Medicare/Medicaid)",
    "29": "Labor (ERISA)",
    "45": "Public Welfare (ACA/HHS)",
    "26": "Internal Revenue (tax treatment of insurance)",
}


async def search_regulations(
    query: str,
    title: str = "",
    per_page: int = 10,
) -> list[dict]:
    """Full-text search across the eCFR."""
    params = {"query": query, "per_page": min(per_page, 20)}
    if title:
        params["hierarchy[title]"] = title

    resp = await _client.get(f"{BASE_URL}/search/v1/results", params=params)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for r in data.get("results", []):
        hierarchy = r.get("hierarchy", {})
        headings = r.get("hierarchy_headings", {})
        results.append({
            "title": hierarchy.get("title", ""),
            "part": hierarchy.get("part", ""),
            "section": hierarchy.get("section", ""),
            "heading": headings.get("section", headings.get("part", "")),
            "title_heading": headings.get("title", ""),
            "type": r.get("type", ""),
            "starts_on": r.get("starts_on", ""),
            "snippet": r.get("full_text_excerpt", r.get("headings_text", ""))[:300],
            "url": f"https://www.ecfr.gov/current/title-{hierarchy.get('title', '')}/part-{hierarchy.get('part', '')}" +
                   (f"/section-{hierarchy.get('section', '')}" if hierarchy.get("section") else ""),
        })
    return results


async def get_section(title: str, part: str, section: str) -> dict | None:
    """Get full text of a specific CFR section."""
    resp = await _client.get(
        f"{BASE_URL}/versioner/v1/full/current/title-{title}.xml",
        params={"part": part, "section": section},
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()

    return {
        "title": title,
        "part": part,
        "section": section,
        "content": resp.text[:5000],  # Cap at 5K chars
        "url": f"https://www.ecfr.gov/current/title-{title}/part-{part}/section-{section}",
    }


async def list_titles() -> list[dict]:
    """List all CFR titles."""
    resp = await _client.get(f"{BASE_URL}/versioner/v1/titles")
    resp.raise_for_status()
    data = resp.json()

    return [
        {
            "number": t.get("number", ""),
            "name": t.get("name", ""),
            "insurance_relevant": str(t.get("number", "")) in INSURANCE_TITLES,
            "relevance_note": INSURANCE_TITLES.get(str(t.get("number", "")), ""),
        }
        for t in data.get("titles", [])
    ]
