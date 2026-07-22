"""
Lightweight SQLite persistence — zero-cost, file-based, no external DB service.
Stores scraped leads so the dashboard can filter/select across sessions.
"""
from __future__ import annotations
import sqlite3
import json
import os
from typing import List, Optional
from .models import Lead

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "leads.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            domain TEXT,
            emails TEXT,
            phones TEXT,
            addresses TEXT,
            social_links TEXT,
            company_name TEXT,
            mx_status TEXT,
            mx_checked_domain TEXT
        )
    """)
    conn.commit()
    conn.close()


def insert_leads(leads: List[Lead]) -> List[Lead]:
    conn = get_conn()
    cur = conn.cursor()
    for lead in leads:
        cur.execute(
            """INSERT INTO leads
               (source_url, domain, emails, phones, addresses, social_links,
                company_name, mx_status, mx_checked_domain)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lead.source_url, lead.domain,
                json.dumps(lead.emails), json.dumps(lead.phones),
                json.dumps(lead.addresses), json.dumps(lead.social_links),
                lead.company_name, lead.mx_status, lead.mx_checked_domain,
            ),
        )
        lead.id = cur.lastrowid
    conn.commit()
    conn.close()
    return leads


def update_mx_status(lead_id: int, domain: str, status: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE leads SET mx_status = ?, mx_checked_domain = ? WHERE id = ?",
        (status, domain, lead_id),
    )
    conn.commit()
    conn.close()


def get_all_leads() -> List[Lead]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    conn.close()
    leads = []
    for r in rows:
        leads.append(Lead(
            id=r["id"], source_url=r["source_url"], domain=r["domain"],
            emails=json.loads(r["emails"] or "[]"),
            phones=json.loads(r["phones"] or "[]"),
            addresses=json.loads(r["addresses"] or "[]"),
            social_links=json.loads(r["social_links"] or "[]"),
            company_name=r["company_name"], mx_status=r["mx_status"],
            mx_checked_domain=r["mx_checked_domain"],
        ))
    return leads


def clear_all_leads() -> None:
    conn = get_conn()
    conn.execute("DELETE FROM leads")
    conn.commit()
    conn.close()
