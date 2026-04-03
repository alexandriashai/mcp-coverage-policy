"""MCP Server for Coverage Policy — eCFR, Federal Register, CMS Coverage Database."""

from mcp.server.fastmcp import FastMCP
from .services import ecfr, federal_register, cms_coverage

mcp = FastMCP(
    "Coverage Policy",
    instructions="Search federal regulations, CMS coverage policies, and Federal Register "
                 "rulemaking for insurance coverage arguments. Covers 42 CFR (Medicare/Medicaid), "
                 "29 CFR (ERISA), 45 CFR (ACA), NCDs, LCDs, and insurance-related federal rules.",
    host="0.0.0.0",
    port=8121,
)


@mcp.tool()
async def search_cfr(
    query: str,
    title: str = "",
    max_results: int = 10,
) -> str:
    """Search the Code of Federal Regulations (eCFR) for insurance-related regulations.

    Args:
        query: Search terms (e.g., "network adequacy", "mental health parity", "prior authorization")
        title: CFR title number — "42" (Medicare/Medicaid), "29" (ERISA), "45" (ACA), "26" (tax), or "" for all
        max_results: Number of results (default 10, max 20)
    """
    results = await ecfr.search_regulations(query, title, min(max_results, 20))

    if not results:
        return f"No CFR regulations found for: {query}"

    lines = [f"**CFR search:** {query}" + (f" (Title {title})" if title else "") + "\n"]
    for r in results:
        lines.append(f"### {r['title_heading']} — {r['heading']}")
        lines.append(f"**{r['title']} CFR §{r['section'] or r['part']}** | [{r['type']}]({r['url']})")
        if r.get("snippet"):
            lines.append(f"\n{r['snippet']}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_cfr_section(
    title: str,
    part: str,
    section: str,
) -> str:
    """Get the full text of a specific CFR section.

    Args:
        title: CFR title number (e.g., "42")
        part: CFR part number (e.g., "438")
        section: Section number (e.g., "438.68")
    """
    result = await ecfr.get_section(title, part, section)
    if not result:
        return f"Section {title} CFR §{section} not found."

    return f"## {title} CFR §{section}\n\n[Full text]({result['url']})\n\n{result['content']}"


@mcp.tool()
async def search_federal_register(
    query: str,
    agency: str = "",
    doc_type: str = "",
    max_results: int = 10,
) -> str:
    """Search the Federal Register for rules, proposed rules, and notices.
    Essential for finding recent rulemaking on insurance coverage topics.

    Args:
        query: Search terms (e.g., "surprise billing", "no surprises act", "prior authorization")
        agency: Filter by agency — "cms", "ebsa", "hhs", "dol", "irs", "cciio", or "" for all
        doc_type: Filter by type — "RULE" (final rules), "PRORULE" (proposed rules), "NOTICE", or "" for all
        max_results: Number of results (default 10, max 20)
    """
    data = await federal_register.search_documents(query, agency, doc_type, min(max_results, 20))
    results = data.get("results", [])

    if not results:
        return f"No Federal Register documents found for: {query}"

    lines = [f"**Federal Register:** {query} ({data['count']} total results)\n"]
    for r in results:
        agencies = ", ".join(r["agencies"][:2])
        cfr_refs = ", ".join(r["cfr_references"][:3]) if r["cfr_references"] else ""
        lines.append(f"### {r['title']}")
        lines.append(f"**{r['type']}** | {r['publication_date']} | {agencies}")
        lines.append(f"Doc #{r['document_number']} | [HTML]({r['html_url']})" + (f" | CFR: {cfr_refs}" if cfr_refs else ""))
        if r.get("abstract"):
            abstract = r["abstract"][:400]
            if len(r["abstract"]) > 400:
                abstract += "..."
            lines.append(f"\n{abstract}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_federal_register_document(document_number: str) -> str:
    """Get full details for a specific Federal Register document.

    Args:
        document_number: The FR document number (e.g., "2025-18649")
    """
    doc = await federal_register.get_document(document_number)
    if not doc:
        return f"Document {document_number} not found."

    lines = [
        f"## {doc['title']}",
        f"**Type:** {doc['type']} | **Published:** {doc['publication_date']}",
        f"**Agencies:** {', '.join(doc['agencies'])}",
        f"**Citation:** {doc.get('citation', 'N/A')}",
        f"**Effective:** {doc.get('effective_on', 'N/A')}",
        f"[Full text]({doc['html_url']}) | [PDF]({doc['pdf_url']})",
    ]

    if doc.get("cfr_references"):
        lines.append(f"**CFR References:** {', '.join(doc['cfr_references'])}")
    if doc.get("docket_ids"):
        lines.append(f"**Docket IDs:** {', '.join(doc['docket_ids'])}")

    if doc.get("abstract"):
        lines.append(f"\n### Abstract\n\n{doc['abstract']}")

    return "\n".join(lines)


@mcp.tool()
async def lookup_ncd(ncd_id: str) -> str:
    """Look up a National Coverage Determination (NCD) by ID from the CMS Coverage Database.

    Args:
        ncd_id: The NCD ID (e.g., "240.4" for continuous positive airway pressure)
    """
    result = await cms_coverage.get_ncd(ncd_id)
    if not result:
        return f"NCD {ncd_id} not found. NCD IDs are formatted like '240.4' or '110.3'."

    lines = [f"## NCD {ncd_id}"]
    for key, value in result.items():
        if value and isinstance(value, str) and len(value) < 2000:
            lines.append(f"**{key}:** {value}")
    return "\n".join(lines)


@mcp.tool()
async def coverage_policy_search(
    topic: str,
    scope: str = "all",
) -> str:
    """Comprehensive search for coverage policies across CFR regulations and Federal Register rulemaking.
    Use this for coverage denial arguments — finds the legal and regulatory basis.

    Args:
        topic: The coverage topic (e.g., "gender affirming care", "autism ABA therapy", "bariatric surgery")
        scope: "all", "cfr" (regulations only), or "rules" (Federal Register only)
    """
    sections = []

    if scope in ("all", "cfr"):
        # Search insurance-critical CFR titles
        for title_num in ["42", "45", "29"]:
            regs = await ecfr.search_regulations(topic, title_num, per_page=3)
            if regs:
                title_name = ecfr.INSURANCE_TITLES.get(title_num, "")
                lines = [f"### {title_num} CFR — {title_name}\n"]
                for r in regs:
                    lines.append(f"- **§{r['section'] or r['part']}** {r['heading']} [{r['type']}]({r['url']})")
                sections.append("\n".join(lines))

    if scope in ("all", "rules"):
        # Search Federal Register for recent rules
        for agency in ["cms", "ebsa"]:
            data = await federal_register.search_documents(topic, agency, doc_type="RULE", per_page=3)
            results = data.get("results", [])
            if results:
                lines = [f"### Federal Register — {agency.upper()} Final Rules\n"]
                for r in results:
                    lines.append(f"- **{r['title']}** ({r['publication_date']}) [Doc #{r['document_number']}]({r['html_url']})")
                sections.append("\n".join(lines))

    if scope in ("all",):
        # Search CMS Coverage Database for NCDs
        ncds = await cms_coverage.search_ncds(topic)
        if ncds:
            lines = ["### CMS National Coverage Determinations\n"]
            for n in ncds[:5]:
                lines.append(f"- **NCD {n['ncd_id']}:** {n['title']}")
            sections.append("\n".join(lines))

    if not sections:
        return f"No coverage policies found for: {topic}"

    return f"# Coverage Policy: {topic}\n\n" + "\n\n".join(sections)
