"""
Free DNS MX Email Verification Engine
----------------------------------------
Verifies email deliverability heuristically by checking whether a domain has
valid MX records — no external paid API required. This confirms the domain
*can* receive mail; it does not confirm a specific mailbox exists (true SMTP
handshake verification is unreliable/blocked by most providers and is
intentionally out of scope for a free, ToS-safe tool).
"""
from __future__ import annotations
import asyncio
import logging
from typing import Dict, List

import dns.resolver
import dns.exception

from .models import VerifyResult

logger = logging.getLogger("verifier")

_CACHE: Dict[str, VerifyResult] = {}
_resolver = dns.resolver.Resolver()
_resolver.timeout = 5
_resolver.lifetime = 5


def _check_mx_sync(domain: str) -> VerifyResult:
    domain = domain.strip().lower().lstrip("@")
    try:
        answers = _resolver.resolve(domain, "MX")
        records = sorted(
            [str(r.exchange).rstrip(".") for r in answers],
            key=lambda x: x,
        )
        if records:
            return VerifyResult(domain=domain, mx_status="valid", mx_records=records)
        return VerifyResult(domain=domain, mx_status="invalid", mx_records=[])
    except dns.resolver.NXDOMAIN:
        return VerifyResult(domain=domain, mx_status="invalid", mx_records=[])
    except dns.resolver.NoAnswer:
        return VerifyResult(domain=domain, mx_status="invalid", mx_records=[])
    except dns.exception.Timeout:
        return VerifyResult(domain=domain, mx_status="error", mx_records=[])
    except Exception as e:
        logger.debug(f"MX check failed for {domain}: {e}")
        return VerifyResult(domain=domain, mx_status="error", mx_records=[])


async def check_mx(domain: str) -> VerifyResult:
    if domain in _CACHE:
        return _CACHE[domain]
    result = await asyncio.to_thread(_check_mx_sync, domain)
    _CACHE[domain] = result
    return result


async def check_mx_many(domains: List[str], concurrency: int = 10) -> List[VerifyResult]:
    unique_domains = sorted(set(d.strip().lower().lstrip("@") for d in domains if d.strip()))
    sem = asyncio.Semaphore(concurrency)

    async def _bounded(d: str) -> VerifyResult:
        async with sem:
            return await check_mx(d)

    return await asyncio.gather(*[_bounded(d) for d in unique_domains])
