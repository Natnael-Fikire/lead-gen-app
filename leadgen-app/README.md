# Open Lead-Gen & Contact Extraction Engine

A free, open-source, zero-cost lead generation tool: build X-Ray Boolean search
strings, scrape public contact pages, extract emails/phones/addresses/socials
with regex, verify email domains via free DNS MX lookups, and export everything
to a polished Excel workbook or CSV.

No paid APIs required anywhere in the pipeline.

## Architecture

```
leadgen-app/
├── backend/            FastAPI app — search generation, scraping, verification, export
│   └── app/
│       ├── xray.py       Boolean search string builder (Google/Bing/DDG)
│       ├── scraper.py    httpx + BeautifulSoup4 crawler (Playwright fallback for JS pages)
│       ├── extractor.py  Regex engine: emails, phones, addresses, social links
│       ├── verifier.py   Async DNS MX record verification (dnspython)
│       ├── exporter.py   Pandas + openpyxl styled Excel/CSV export
│       ├── db.py         SQLite persistence (zero external DB cost)
│       └── main.py       FastAPI routes
└── frontend/
    └── streamlit_app.py  Interactive dashboard (search → scrape → verify → export)
```

## Setup

```bash
winget install Python.Python.3.12           #if using python version above 3.12
```

### 1. Backend

```bash
cd backend
py -3.12 -m venv venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium       # only needed if you use the browser fallback You can skip it at first
uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000` (interactive docs at `/docs`).

### 2. Frontend

In a second terminal:

```bash
cd frontend
py -3.12 -m venv venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`.

## How it's used

1. **X-Ray tab** — enter Industry / Role / Location / Email Domain. The app
   builds precision Boolean strings like:
   `site:linkedin.com/in "VP Sales" SaaS "Austin, TX"`
   and gives you a clickable link to run it on Google/Bing. There is no free
   programmatic Google/Bing search API, so this step is "click to search" —
   copy the result URLs into the next tab.
2. **Scrape tab** — paste those URLs (company sites, LinkedIn/Facebook result
   pages, directory listings). The app crawls the homepage plus `/contact`,
   `/about`, `/team` and regex-extracts emails, phones, addresses, and social
   links.
3. **Dashboard tab** — filter/select leads, run **DNS MX verification**
   (free — checks the domain can actually receive mail), then export to a
   styled `.xlsx` (dark header, zebra stripes, auto-fit columns, color-coded
   MX status) or plain `.csv`.

## Notes & honest limitations

- **MX verification confirms deliverability of the domain, not a specific
  mailbox.** True per-mailbox SMTP verification is blocked by most mail
  providers and isn't reliable — including it would just produce false
  confidence, so it's intentionally out of scope.
- **Regex-based phone/address extraction is a heuristic**, tuned for common
  US/international formats. It will miss unusual formats and occasionally
  misfire on edge cases — it's a first-pass filter, not a guarantee.
- **Respect target sites' `robots.txt` and Terms of Service.** This tool only
  crawls publicly accessible pages you point it at; it does not bypass
  authentication, CAPTCHAs, or paywalls, and you're responsible for using it
  in compliance with applicable law (e.g. GDPR/CCPA for stored contact data)
  and each site's terms.
- The optional DuckDuckGo HTML fallback in `scraper.py` (`ddg_search_urls`) is
  unofficial and rate-limited — use sparingly, and prefer the manual
  click-through search for volume.

## Next.js alternative

If you'd rather have a Next.js/React frontend instead of Streamlit, the FastAPI
backend already exposes clean JSON endpoints (`/api/xray`, `/api/scrape`,
`/api/verify-leads`, `/api/leads`, `/api/export/xlsx`, `/api/export/csv`) with
CORS enabled — you can build a Next.js dashboard against it with no backend
changes required. Ask and I can generate that scaffold too.
