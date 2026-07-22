"""
Multi-Channel Contact Scraper
------------------------------
Strategy (cheapest first, to stay zero-cost and fast):
  1. Try a plain `requests` GET + BeautifulSoup4 parse (fast, no browser).
  2. If that yields no contact info AND use_browser_fallback=True, fall back
     to a headless Playwright browser render (handles JS-rendered contact pages).

Crawls the homepage plus common contact-page subpaths.
"""
from __future__ import annotations
import asyncio
import logging
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .extractor import extract_contacts, domain_from_url
from .models import Lead

logger = logging.getLogger("scraper")

SUBPATHS = ["", "/contact", "/contact-us", "/contactus", "/about", "/about-us", "/team", "/our-team"]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 LeadGenBot/1.0"
    )
}
TIMEOUT = 12.0


def _normalize_base(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _fetch_static(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        resp = await client.get(url, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        if resp.status_code == 200 and resp.text:
            return resp.text
    except Exception as e:
        logger.debug(f"static fetch failed for {url}: {e}")
    return None


async def _fetch_with_browser(url: str) -> Optional[str]:
    """Lazy-imports Playwright so the app still runs if it isn't installed
    (browser fallback is optional)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright not installed; skipping browser fallback.")
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=HEADERS["User-Agent"])
            await page.goto(url, timeout=TIMEOUT * 1000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)  # let lazy JS content settle
            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        logger.debug(f"browser fetch failed for {url}: {e}")
        return None


def _visible_text_and_html(html: str) -> str:
    """Return cleaned visible text plus relevant hrefs (mailto:, tel:, social
    links). Deliberately does NOT include raw HTML/script/style content —
    minified JS, SVG path data, and asset hashes are full of digit runs that
    produce false-positive phone/email matches."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style/noscript entirely — they're not real page content
    # and are the main source of false-positive regex matches.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ")

    hrefs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            hrefs.append(href.replace("mailto:", ""))
        elif href.startswith("tel:"):
            hrefs.append(href.replace("tel:", ""))
        elif any(d in href for d in ("linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com")):
            hrefs.append(href)

    return f"{text} {' '.join(hrefs)}"


async def scrape_url(base_url: str, crawl_subpaths: bool = True,
                      use_browser_fallback: bool = True) -> Lead:
    base = _normalize_base(base_url)
    domain = domain_from_url(base) or base
    paths = SUBPATHS if crawl_subpaths else [""]

    combined_text = ""
    async with httpx.AsyncClient() as client:
        for path in paths:
            full_url = urljoin(base + "/", path.lstrip("/"))
            html = await _fetch_static(client, full_url)
            if not html and use_browser_fallback:
                html = await _fetch_with_browser(full_url)
            if html:
                combined_text += " " + _visible_text_and_html(html)

    contacts = extract_contacts(combined_text)

    return Lead(
        source_url=base,
        domain=domain,
        emails=contacts["emails"],
        phones=contacts["phones"],
        addresses=contacts["addresses"],
        social_links=contacts["social_links"],
        mx_status="unchecked",
    )


async def scrape_many(urls: List[str], crawl_subpaths: bool = True,
                       use_browser_fallback: bool = True, concurrency: int = 5) -> List[Lead]:
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(u: str) -> Lead:
        async with sem:
            return await scrape_url(u, crawl_subpaths, use_browser_fallback)

    return await asyncio.gather(*[_bounded(u) for u in urls])


# ---------------------------------------------------------------------------
# OPTIONAL: DuckDuckGo HTML fallback for X-Ray queries when no browser search
# is performed manually. Use sparingly — this scrapes DDG's HTML results page
# (no API key required) but is unofficial and rate-limited. Provided as a
# convenience for small volumes only.
# ---------------------------------------------------------------------------
async def ddg_search_urls(query: str, max_results: int = 10) -> List[str]:
    url = "https://duckduckgo.com/html/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params={"q": query}, headers=HEADERS, timeout=TIMEOUT)
            soup = BeautifulSoup(resp.text, "html.parser")
            links = []
            for a in soup.select("a.result__a"):
                href = a.get("href")
                if href:
                    links.append(href)
                if len(links) >= max_results:
                    break
            return links
        except Exception as e:
            logger.warning(f"DDG search failed: {e}")
            return []
