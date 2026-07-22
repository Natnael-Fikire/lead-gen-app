"""
Interactive Lead-Gen Dashboard (Streamlit)
---------------------------------------------
Wires the FastAPI backend (X-Ray, scraper, verifier, exporter) into a
real-time, filterable dashboard with one-click Excel / CSV export.

Run:
    streamlit run streamlit_app.py

Requires the backend running at BACKEND_URL (default http://localhost:8000).
"""
import os
import requests
import pandas as pd
import streamlit as st

BACKEND_URL = os.environ.get("LEADGEN_BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Open Lead-Gen Engine", layout="wide", page_icon="📇")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "leads" not in st.session_state:
    st.session_state.leads = []
if "xray_results" not in st.session_state:
    st.session_state.xray_results = []

st.title("📇 Open Lead-Gen & Contact Extraction Engine")
st.caption("Free & open-source: X-Ray search builder → scraper → regex parser → DNS MX verification → Excel/CSV export")

tab_search, tab_scrape, tab_dashboard = st.tabs(
    ["🔍 1. X-Ray Search Builder", "🕷️ 2. Scrape & Extract", "📊 3. Dashboard & Export"]
)

# ---------------------------------------------------------------------------
# TAB 1 — X-Ray Search Generator
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Build precision Boolean search strings")
    col1, col2 = st.columns(2)
    with col1:
        industry = st.text_input("Industry", placeholder="e.g. SaaS, Manufacturing")
        role = st.text_input("Role / Title", placeholder="e.g. VP of Sales")
        location = st.text_input("Location", placeholder="e.g. Austin, TX")
    with col2:
        company = st.text_input("Company (optional)", placeholder="e.g. Acme Corp")
        email_domain = st.text_input("Target Email Domain", placeholder="e.g. gmail.com or company.com")
        st.write("")
        include_linkedin = st.checkbox("Include LinkedIn X-Ray", value=True)
        include_facebook = st.checkbox("Include Facebook X-Ray", value=True)
        include_directories = st.checkbox("Include company/directory search", value=True)

    if st.button("Generate X-Ray Queries", type="primary"):
        payload = {
            "industry": industry, "role": role, "location": location,
            "company": company, "email_domain": email_domain,
            "include_linkedin": include_linkedin,
            "include_facebook": include_facebook,
            "include_directories": include_directories,
        }
        try:
            resp = requests.post(f"{BACKEND_URL}/api/xray", json=payload, timeout=10)
            resp.raise_for_status()
            st.session_state.xray_results = resp.json()["queries"]
        except Exception as e:
            st.error(f"Failed to reach backend: {e}")

    if st.session_state.xray_results:
        st.markdown("##### Generated queries — open in browser, copy result URLs into the Scrape tab")
        for q in st.session_state.xray_results:
            with st.container(border=True):
                st.markdown(f"**Target:** {q['target']}  ·  **Engine:** {q['engine']}")
                st.code(q["query"], language="text")
                st.markdown(f"[Open search ↗]({q['search_url']})")

# ---------------------------------------------------------------------------
# TAB 2 — Scrape & Extract
# ---------------------------------------------------------------------------
with tab_scrape:
    st.subheader("Paste target URLs (company sites, LinkedIn results, directory listings)")
    st.caption("One URL per line. The scraper will crawl the homepage plus /contact, /about, and /team automatically.")
    urls_text = st.text_area("Target URLs", height=150, placeholder="https://example.com\nhttps://anothercompany.com")
    col_a, col_b = st.columns(2)
    with col_a:
        crawl_subpaths = st.checkbox("Crawl /contact, /about, /team subpaths", value=True)
    with col_b:
        use_browser = st.checkbox("Use headless browser fallback (Playwright, slower but handles JS pages)", value=True)

    if st.button("Scrape & Extract Contacts", type="primary"):
        urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
        if not urls:
            st.warning("Add at least one URL first.")
        else:
            with st.spinner(f"Scraping {len(urls)} site(s)... this can take a moment per site."):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/api/scrape",
                        json={"urls": urls, "crawl_subpaths": crawl_subpaths, "use_browser_fallback": use_browser},
                        timeout=180,
                    )
                    resp.raise_for_status()
                    new_leads = resp.json()["leads"]
                    st.success(f"Scraped {len(new_leads)} lead(s). Head to the Dashboard tab to review, verify, and export.")
                except Exception as e:
                    st.error(f"Scrape failed: {e}")

# ---------------------------------------------------------------------------
# TAB 3 — Dashboard, Filtering, Verification, Export
# ---------------------------------------------------------------------------
with tab_dashboard:
    st.subheader("Lead Dashboard")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 Refresh Leads"):
            pass  # triggers rerun + refetch below
    with col2:
        if st.button("✅ Verify All Emails (MX)"):
            with st.spinner("Running DNS MX lookups..."):
                try:
                    resp = requests.post(f"{BACKEND_URL}/api/verify-leads", timeout=60)
                    resp.raise_for_status()
                    st.success(f"Verified {resp.json()['updated']} lead(s).")
                except Exception as e:
                    st.error(f"Verification failed: {e}")
    with col3:
        if st.button("🗑️ Clear All Leads"):
            try:
                requests.delete(f"{BACKEND_URL}/api/leads", timeout=10)
                st.success("Cleared.")
            except Exception as e:
                st.error(f"Failed to clear: {e}")

    # Always fetch fresh from backend (source of truth is SQLite)
    try:
        resp = requests.get(f"{BACKEND_URL}/api/leads", timeout=10)
        resp.raise_for_status()
        leads = resp.json()["leads"]
    except Exception as e:
        leads = []
        st.error(f"Could not load leads from backend: {e}")

    if not leads:
        st.info("No leads yet. Scrape some URLs in the previous tab first.")
    else:
        df = pd.DataFrame(leads)
        df_display = df.copy()
        for col in ["emails", "phones", "addresses", "social_links"]:
            df_display[col] = df_display[col].apply(lambda x: "; ".join(x) if isinstance(x, list) else x)

        # --- Filters ---
        st.markdown("##### Filters")
        f1, f2 = st.columns(2)
        with f1:
            status_filter = st.multiselect(
                "MX Status", options=sorted(df_display["mx_status"].dropna().unique().tolist()),
                default=None,
            )
        with f2:
            domain_search = st.text_input("Filter by domain contains", "")

        filtered = df_display.copy()
        if status_filter:
            filtered = filtered[filtered["mx_status"].isin(status_filter)]
        if domain_search:
            filtered = filtered[filtered["domain"].str.contains(domain_search, case=False, na=False)]

        st.markdown(f"##### {len(filtered)} lead(s)")
        st.dataframe(
            filtered[["company_name", "source_url", "domain", "emails", "phones", "addresses", "social_links", "mx_status"]],
            use_container_width=True,
            height=400,
        )

        # --- Manual row selection for export ---
        st.markdown("##### Select leads to export (default: all filtered rows)")
        selected_ids = st.multiselect(
            "Lead IDs to include in export",
            options=filtered["id"].tolist(),
            default=filtered["id"].tolist(),
        )
        export_rows = [l for l in leads if l["id"] in selected_ids]

        exp1, exp2, exp3 = st.columns([1, 1, 2])
        with exp1:
            if st.button("📥 Export to Excel (.xlsx)", type="primary"):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/api/export/xlsx",
                        json={"leads": export_rows, "filename": "leads_export"},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    st.download_button(
                        "⬇️ Download leads_export.xlsx", data=resp.content,
                        file_name="leads_export.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                except Exception as e:
                    st.error(f"Export failed: {e}")
        with exp2:
            if st.button("📥 Export to CSV"):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/api/export/csv",
                        json={"leads": export_rows, "filename": "leads_export"},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    st.download_button(
                        "⬇️ Download leads_export.csv", data=resp.content,
                        file_name="leads_export.csv", mime="text/csv",
                    )
                except Exception as e:
                    st.error(f"Export failed: {e}")
