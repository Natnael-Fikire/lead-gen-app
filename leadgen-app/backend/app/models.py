"""
Pydantic models shared across the API.
"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


class XRayParams(BaseModel):
    industry: Optional[str] = ""
    role: Optional[str] = ""
    location: Optional[str] = ""
    email_domain: Optional[str] = ""   # e.g. "gmail.com" or "company.com"
    company: Optional[str] = ""
    include_linkedin: bool = True
    include_facebook: bool = True
    include_directories: bool = True


class XRayResult(BaseModel):
    engine: str          # "google" | "bing" | "ddg"
    target: str          # what it's aimed at, e.g. "LinkedIn profiles"
    query: str
    search_url: str      # clickable link the user can open manually


class ScrapeRequest(BaseModel):
    urls: List[str] = Field(default_factory=list)
    crawl_subpaths: bool = True   # also try /contact, /about, /team
    use_browser_fallback: bool = True  # fall back to Playwright if requests+BS4 finds nothing


class Lead(BaseModel):
    id: Optional[int] = None
    source_url: str
    domain: Optional[str] = None
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    addresses: List[str] = Field(default_factory=list)
    social_links: List[str] = Field(default_factory=list)
    company_name: Optional[str] = None
    mx_status: Optional[str] = None   # "valid" | "invalid" | "unchecked"
    mx_checked_domain: Optional[str] = None


class VerifyRequest(BaseModel):
    domains: List[str] = Field(default_factory=list)


class VerifyResult(BaseModel):
    domain: str
    mx_status: str        # "valid" | "invalid" | "error"
    mx_records: List[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    leads: List[Lead]
    filename: Optional[str] = "leads_export"
