# Artlist Catalog Scraper

Programmatic scraper for Artlist's asset catalog (music, SFX, footage, LUTs, video templates, collections) plus their AI creation tools (Studio AI and Flow/Canvas AI).

## Status
WIP — see PLAN.md for current status.

## Components
- `src/` — Python scrapers and pipeline orchestration
- `data/` — Scraped catalog data (JSON)
- `ui/` — Browser UI for visualization
- `.github/workflows/` — Weekly cron refresh
- `analysis/` — HAR analysis artifacts (API endpoint inventory)

## Setup
1. Copy `.env.example` to `.env` and fill in credentials.
2. `pip install -r requirements.txt`
3. `python -m src.cli catalog` — run full catalog scrape
4. `python -m src.cli serve` — start UI server

See PLAN.md and .agents/SKILL.md for detailed docs.
