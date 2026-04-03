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

    import re

    seen = set()
    results = []
    for r in data.get("results", []):
        hierarchy = r.get("hierarchy", {})
        headings = r.get("hierarchy_headings", {})
        # Deduplicate by title+part+section
        key = f"{hierarchy.get('title', '')}-{hierarchy.get('part', '')}-{hierarchy.get('section', '')}"
        if key in seen:
            continue
        seen.add(key)

        # Strip HTML from snippet, convert <strong> to markdown bold
        snippet = r.get("full_text_excerpt", r.get("headings_text", "")) or ""
        snippet = re.sub(r'<strong>(.*?)</strong>', r'**\1**', snippet)
        snippet = re.sub(r'<span class="elipsis">.*?</span>', '…', snippet)
        snippet = re.sub(r'<[^>]+>', '', snippet)
        snippet = snippet[:300]

        section_id = hierarchy.get("section", "")
        part_id = hierarchy.get("part", "")
        full_section = f"{part_id}.{section_id}" if section_id and not section_id.startswith(part_id) else section_id

        results.append({
            "title": hierarchy.get("title", ""),
            "part": part_id,
            "section": section_id,
            "heading": headings.get("section", headings.get("part", "")),
            "title_heading": headings.get("title", ""),
            "type": r.get("type", ""),
            "starts_on": r.get("starts_on", ""),
            "snippet": snippet,
            "url": f"https://www.ecfr.gov/current/title-{hierarchy.get('title', '')}/part-{part_id}" +
                   (f"/section-{full_section}" if section_id else ""),
        })
    return results


async def _get_latest_date(title: str) -> str:
    """Get the latest issue date for a CFR title."""
    resp = await _client.get(f"{BASE_URL}/versioner/v1/titles")
    if resp.status_code == 200:
        data = resp.json()
        for t in data.get("titles", []):
            if str(t.get("number", "")) == str(title):
                return t.get("latest_issue_date", t.get("up_to_date_as_of", ""))
    return ""


async def get_section(title: str, part: str, section: str) -> dict | None:
    """Get full text of a specific CFR section.

    Uses the versioner API with the latest issue date.
    Section format: just the number (e.g., "503-1", "712", "68") or full (e.g., "438.68").
    """
    import re

    # Build full section identifier
    full_section = f"{part}.{section}" if not section.startswith(part) else section

    # Get latest issue date for this title
    date = await _get_latest_date(title)
    if not date:
        return None

    # Versioner API with date and full section identifier
    versioner_url = f"{BASE_URL}/versioner/v1/full/{date}/title-{title}.xml"
    resp = await _client.get(versioner_url, params={"part": part, "section": full_section})
    if resp.status_code != 200:
        # Try with just the section number (without part prefix)
        resp = await _client.get(versioner_url, params={"part": part, "section": section})

    if resp.status_code == 200 and not resp.text.strip().startswith('<?xml version="1.0"?>\n<hash>'):
        text = re.sub(r'<[^>]+>', ' ', resp.text)
        text = re.sub(r'\s+', ' ', text).strip()
        return {
            "title": title,
            "part": part,
            "section": section,
            "content": text[:8000],
            "url": f"https://www.ecfr.gov/current/title-{title}/section-{full_section}",
        }

    return None


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
