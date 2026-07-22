"""
FastAPI Backend — Lead Generation & Contact Extraction Engine
----------------------------------------------------------------
Endpoints:
    POST /api/xray            -> generate boolean X-Ray search strings
    POST /api/scrape           -> crawl URLs, extract contacts, persist leads
    POST /api/verify           -> DNS MX verification for domains
    POST /api/verify-leads     -> verify + update MX status for stored leads
    GET  /api/leads             -> fetch all stored leads
    DELETE /api/leads          -> clear all stored leads
    POST /api/export/xlsx      -> download styled .xlsx workbook
    POST /api/export/csv       -> download .csv
    GET  /api/health
"""
from __future__ import annotations
from typing import List
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io

from .models import (
    XRayParams, ScrapeRequest, VerifyRequest, ExportRequest, Lead,
)
from .xray import generate_xray_queries
from .scraper import scrape_many
from .verifier import check_mx_many
from .exporter import build_xlsx, build_csv
from .extractor import domain_from_url
from . import db

app = FastAPI(title="Open Lead-Gen Engine", version="1.0.0")

# Allow the Streamlit / Next.js frontend (any localhost port) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this to your frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    db.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/xray")
def xray(params: XRayParams):
    results = generate_xray_queries(params)
    return {"queries": [r.model_dump() for r in results]}


@app.post("/api/scrape")
async def scrape(req: ScrapeRequest):
    if not req.urls:
        raise HTTPException(status_code=400, detail="Provide at least one URL to scrape.")
    leads: List[Lead] = await scrape_many(
        req.urls,
        crawl_subpaths=req.crawl_subpaths,
        use_browser_fallback=req.use_browser_fallback,
    )
    leads = db.insert_leads(leads)
    return {"leads": [l.model_dump() for l in leads]}


@app.post("/api/verify")
async def verify(req: VerifyRequest):
    if not req.domains:
        raise HTTPException(status_code=400, detail="Provide at least one domain.")
    results = await check_mx_many(req.domains)
    return {"results": [r.model_dump() for r in results]}


@app.post("/api/verify-leads")
async def verify_leads():
    """Verify MX records for every domain across stored leads and persist status."""
    leads = db.get_all_leads()
    if not leads:
        return {"updated": 0}

    domain_to_leads = defaultdict(list)
    for lead in leads:
        domain = lead.domain or domain_from_url(lead.source_url)
        if domain:
            domain_to_leads[domain].append(lead)

    results = await check_mx_many(list(domain_to_leads.keys()))
    status_by_domain = {r.domain: r.mx_status for r in results}

    updated = 0
    for domain, group in domain_to_leads.items():
        status = status_by_domain.get(domain, "error")
        for lead in group:
            db.update_mx_status(lead.id, domain, status)
            updated += 1

    return {"updated": updated}


@app.get("/api/leads")
def get_leads():
    leads = db.get_all_leads()
    return {"leads": [l.model_dump() for l in leads]}


@app.delete("/api/leads")
def delete_leads():
    db.clear_all_leads()
    return {"status": "cleared"}


@app.post("/api/export/xlsx")
def export_xlsx(req: ExportRequest):
    if not req.leads:
        raise HTTPException(status_code=400, detail="No leads provided for export.")
    xlsx_bytes = build_xlsx(req.leads)
    filename = f"{req.filename or 'leads_export'}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/csv")
def export_csv(req: ExportRequest):
    if not req.leads:
        raise HTTPException(status_code=400, detail="No leads provided for export.")
    csv_bytes = build_csv(req.leads)
    filename = f"{req.filename or 'leads_export'}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
