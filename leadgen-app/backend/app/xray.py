"""
X-Ray Search Generator Engine
------------------------------
Builds precision Boolean search strings for Google / Bing / DuckDuckGo to find
public LinkedIn profiles, Facebook pages, and directory listings that match the
user's target criteria (industry, role, location, email domain).

NOTE: There is no free, ToS-compliant programmatic search API for Google or Bing.
This module only *constructs the query strings and clickable search URLs* — the
actual search is expected to be run by a human in a browser (or via the optional
DuckDuckGo HTML fallback in scraper.py, used sparingly).
"""
from __future__ import annotations
from urllib.parse import quote_plus
from typing import List
from .models import XRayParams, XRayResult


def _quote(term: str) -> str:
    term = term.strip()
    if not term:
        return ""
    return f'"{term}"' if " " in term else term


def _build_google_url(query: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}"


def _build_bing_url(query: str) -> str:
    return f"https://www.bing.com/search?q={quote_plus(query)}"


def _build_ddg_url(query: str) -> str:
    return f"https://duckduckgo.com/html/?q={quote_plus(query)}"


def generate_xray_queries(params: XRayParams) -> List[XRayResult]:
    results: List[XRayResult] = []

    industry = _quote(params.industry)
    role = _quote(params.role)
    location = _quote(params.location)
    company = _quote(params.company)
    email_domain = params.email_domain.strip().lstrip("@")

    base_terms = " ".join(t for t in [role, industry, location, company] if t)

    # --- LinkedIn profile X-Ray ---
    if params.include_linkedin:
        q = f'site:linkedin.com/in {base_terms}'.strip()
        results.append(XRayResult(
            engine="google", target="LinkedIn profiles",
            query=q, search_url=_build_google_url(q),
        ))
        results.append(XRayResult(
            engine="bing", target="LinkedIn profiles",
            query=q, search_url=_build_bing_url(q),
        ))

    # --- Facebook business page X-Ray ---
    if params.include_facebook:
        q = f'site:facebook.com {base_terms} (about OR contact)'.strip()
        results.append(XRayResult(
            engine="google", target="Facebook pages",
            query=q, search_url=_build_google_url(q),
        ))

    # --- Public directories / company sites ---
    if params.include_directories:
        q = f'{base_terms} ("contact us" OR "our team") -site:linkedin.com -site:facebook.com'.strip()
        results.append(XRayResult(
            engine="google", target="Company websites / directories",
            query=q, search_url=_build_google_url(q),
        ))

    # --- Email-domain targeted search ---
    if email_domain:
        q = f'{base_terms} "@{email_domain}"'.strip()
        results.append(XRayResult(
            engine="google", target=f"Emails @{email_domain}",
            query=q, search_url=_build_google_url(q),
        ))
        results.append(XRayResult(
            engine="ddg", target=f"Emails @{email_domain} (DuckDuckGo fallback)",
            query=q, search_url=_build_ddg_url(q),
        ))

    return results
