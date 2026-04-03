# MCP Coverage Policy

An MCP server for searching federal regulations (eCFR), Federal Register rulemaking, and CMS coverage policies for insurance coverage arguments.

## Features

- **eCFR** — Full Code of Federal Regulations search (42 CFR Medicare/Medicaid, 29 CFR ERISA, 45 CFR ACA)
- **Federal Register** — Rules, proposed rules, notices from CMS, EBSA, HHS, DOL, IRS
- **CMS Coverage Database** — National Coverage Determinations (NCDs)
- **Comprehensive search** — cross-source policy lookup in one tool call
- **MCP protocol** endpoint for Claude.ai
- **REST API** with Swagger docs

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_cfr` | Search Code of Federal Regulations by keyword and title |
| `get_cfr_section` | Get full text of a specific CFR section |
| `search_federal_register` | Search for rules, proposed rules, notices |
| `get_federal_register_document` | Full details for a Federal Register document |
| `lookup_ncd` | Look up a National Coverage Determination |
| `coverage_policy_search` | Comprehensive cross-source policy search |

## Quick Start

### Connect via MCP (Claude.ai)

- **URL:** `https://coverage.wyldfyre.ai/mcp`
- **Authentication:** None required

### REST API

```bash
# Search CFR regulations
curl "https://coverage.wyldfyre.ai/cfr/search?q=network+adequacy&title=42"

# Search Federal Register
curl "https://coverage.wyldfyre.ai/federal-register/search?q=prior+authorization&agency=cms"

# Get specific FR document
curl "https://coverage.wyldfyre.ai/federal-register/2026-00487"
```

Swagger docs: https://coverage.wyldfyre.ai/docs

## Self-Hosting

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8120
python run_mcp.py  # separate process
```

## Data Sources

| Source | Auth | Coverage |
|--------|------|----------|
| [eCFR](https://www.ecfr.gov) | None | All federal regulations |
| [Federal Register](https://www.federalregister.gov) | None | All FR content since 1994 |
| [CMS Coverage DB](https://api.coverage.cms.gov) | None (NCDs) | NCDs, NCAs, LCDs |

## License

MIT
