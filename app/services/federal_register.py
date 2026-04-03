"""Federal Register API client — rules, proposed rules, notices."""

import httpx

BASE_URL = "https://www.federalregister.gov/api/v1"
_client = httpx.AsyncClient(timeout=15.0)

# Key insurance-related agencies
INSURANCE_AGENCIES = {
    "cms": "centers-for-medicare-medicaid-services",
    "ebsa": "employee-benefits-security-administration",
    "hhs": "health-and-human-services-department",
    "dol": "labor-department",
    "irs": "internal-revenue-service",
    "cciio": "center-for-consumer-information-insurance-oversight",
}


async def search_documents(
    query: str,
    agency: str = "",
    doc_type: str = "",
    per_page: int = 10,
) -> list[dict]:
    """Search the Federal Register for rules, proposed rules, and notices.

    Args:
        query: Search terms
        agency: Agency slug (cms, ebsa, hhs, dol, irs, cciio) or empty for all
        doc_type: RULE, PRORULE, NOTICE, PRESDOCU, or empty for all
        per_page: Results per page (max 20)
    """
    params = {
        "conditions[term]": query,
        "per_page": min(per_page, 20),
        "order": "relevance",
    }

    if agency:
        slug = INSURANCE_AGENCIES.get(agency.lower(), agency)
        params["conditions[agencies][]"] = slug

    if doc_type:
        params["conditions[type][]"] = doc_type

    resp = await _client.get(f"{BASE_URL}/documents.json", params=params)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for r in data.get("results", []):
        agencies = [a.get("name", "") for a in r.get("agencies", [])]
        results.append({
            "title": r.get("title", ""),
            "type": r.get("type", ""),
            "document_number": r.get("document_number", ""),
            "publication_date": r.get("publication_date", ""),
            "agencies": agencies,
            "abstract": (r.get("abstract", "") or "")[:500],
            "html_url": r.get("html_url", ""),
            "pdf_url": r.get("pdf_url", ""),
            "citation": r.get("citation", ""),
            "cfr_references": [
                f"{ref.get('title', '')} CFR {ref.get('part', '')}"
                for ref in r.get("cfr_references", [])
            ],
        })

    return {"count": data.get("count", 0), "results": results}


async def get_document(document_number: str) -> dict | None:
    """Get full details for a specific Federal Register document."""
    resp = await _client.get(f"{BASE_URL}/documents/{document_number}.json")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    r = resp.json()

    return {
        "title": r.get("title", ""),
        "type": r.get("type", ""),
        "document_number": r.get("document_number", ""),
        "publication_date": r.get("publication_date", ""),
        "agencies": [a.get("name", "") for a in r.get("agencies", [])],
        "abstract": r.get("abstract", ""),
        "body_html_url": r.get("body_html_url", ""),
        "html_url": r.get("html_url", ""),
        "pdf_url": r.get("pdf_url", ""),
        "citation": r.get("citation", ""),
        "effective_on": r.get("effective_on", ""),
        "cfr_references": [
            f"{ref.get('title', '')} CFR {ref.get('part', '')}"
            for ref in r.get("cfr_references", [])
        ],
        "regulation_id_numbers": r.get("regulation_id_numbers", []),
        "docket_ids": r.get("docket_ids", []),
    }
