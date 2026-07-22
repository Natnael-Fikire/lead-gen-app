"""
Multi-Channel Contact Extraction Engine
-----------------------------------------
Pure-regex parsing of raw page text/HTML into structured contact fields:
emails, phone numbers (international + national formats), physical
addresses (US-style heuristic), and social profile URLs.
"""
from __future__ import annotations
import re
from typing import List
from urllib.parse import urlparse

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9][a-zA-Z0-9._%+\-]*@[a-zA-Z0-9][a-zA-Z0-9.\-]*\.[a-zA-Z]{2,}"
)

# Matches +1 (555) 123-4567 / 555-123-4567 / +44 20 7946 0958 / 0044 20... etc.
PHONE_RE = re.compile(
    r"(?<!\w)"                                # not preceded by a word/digit char
    r"(?:(?:\+|00)\d{1,3}[\s.\-]?)?"          # optional country code
    r"(?:\(\d{2,4}\)[\s.\-]?)?"               # optional area code in parens
    r"\d{3,4}[\s.\-]\d{3,4}(?:[\s.\-]\d{2,4})?"  # digit groups joined by a REQUIRED separator
    r"(?!\w)"                                 # not followed by a word/digit char
)

# Heuristic US-style street address: "123 Main St, Springfield, IL 62704"
ADDRESS_RE = re.compile(
    r"\d{1,6}[ \t]+[A-Za-z0-9.'\- ]{2,40}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct|Suite|Ste)\.?"
    r"[,][ \t]*[A-Za-z ]{2,30},?[ \t]+[A-Z]{2}[ \t]+\d{5}(?:-\d{4})?",
    re.IGNORECASE,
)

SOCIAL_DOMAINS = (
    "linkedin.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "youtube.com",
)
SOCIAL_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:" + "|".join(d.replace(".", r"\.") for d in SOCIAL_DOMAINS) + r")/[^\s\"'<>]+",
    re.IGNORECASE,
)

# Junk/spam-blocker emails and obvious file extensions to exclude
EMAIL_EXCLUDE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


def clean_emails(raw: List[str]) -> List[str]:
    seen, out = set(), []
    for e in raw:
        e = e.strip().strip(".,;:").lower()
        if any(e.endswith(suf) for suf in EMAIL_EXCLUDE_SUFFIXES):
            continue
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def clean_phones(raw: List[str]) -> List[str]:
    seen, out = set(), []
    for p in raw:
        digits = re.sub(r"\D", "", p)
        if len(digits) < 7 or len(digits) > 15:
            continue
        norm = p.strip()
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def extract_contacts(text: str) -> dict:
    """Run all regex extractors against a blob of page text/HTML and return
    a dict of deduplicated, cleaned matches."""
    emails = clean_emails(EMAIL_RE.findall(text))
    phones = clean_phones(PHONE_RE.findall(text))
    addresses = dedupe([m.strip() for m in ADDRESS_RE.findall(text)])
    socials = dedupe(SOCIAL_URL_RE.findall(text))
    return {
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "social_links": socials,
    }


def domain_from_email(email: str) -> str | None:
    if "@" not in email:
        return None
    return email.split("@")[-1].lower()


def domain_from_url(url: str) -> str | None:
    try:
        netloc = urlparse(url).netloc or urlparse("http://" + url).netloc
        return netloc.lower().lstrip("www.")
    except Exception:
        return None
