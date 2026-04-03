"""Coverage Policy MCP Server — FastAPI application."""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .services import ecfr, federal_register, cms_coverage

app = FastAPI(
    title="Coverage Policy MCP Server",
    description="Search federal regulations (eCFR), Federal Register rulemaking, "
                "and CMS coverage policies for insurance coverage arguments.",
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok", "sources": ["ecfr", "federal_register", "cms_coverage_database"]}


@app.get("/")
def root():
    return {
        "name": "Coverage Policy MCP Server",
        "version": "1.0.0",
        "docs": "/docs",
        "mcp": "https://coverage.wyldfyre.ai/mcp",
    }


@app.get("/cfr/search")
async def cfr_search(q: str = Query(...), title: str = Query(""), limit: int = Query(10, ge=1, le=20)):
    return await ecfr.search_regulations(q, title, limit)


@app.get("/federal-register/search")
async def fr_search(
    q: str = Query(...),
    agency: str = Query(""),
    type: str = Query(""),
    limit: int = Query(10, ge=1, le=20),
):
    return await federal_register.search_documents(q, agency, type, limit)


@app.get("/federal-register/{document_number}")
async def fr_document(document_number: str):
    result = await federal_register.get_document(document_number)
    return result or {"error": "Not found"}


@app.get("/ncd/{ncd_id}")
async def ncd_detail(ncd_id: str):
    result = await cms_coverage.get_ncd(ncd_id)
    return result or {"error": "NCD not found"}
