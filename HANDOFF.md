# HANDOFF — Artlist Catalog Scraper

## Current State (2026-10-20 09:18 UTC)

### Migration Complete
- **Old GH account (elizabethadamspri)**: CLOSED
- **New GH home**: github.com/wesisad5/artlist-scraper (PAT in .env as GH_PAT)
- **GitLab mirror**: gitlab.com/ansgareutychisO/artlist-scraper (PAT in .env as GL_PAT)
- **Netlify site**: aigc-scrape-runner (id=39481ca6-1e9c-4714-b161-dc63b94cbe11, PAT in .env as NETLIFY_TOKEN)
- All 19 GHA secrets set on wesisad5/artlist-scraper
- Local remotes: origin=wesisad5, gitlab=ansgareutychisO

### GHA Issue (IMPORTANT)
- wesisad5 account CANNOT run GHA jobs — all runs across all repos fail with `startup_failure` since April 2026
- Last successful run: 2026-04-08 (wesisad5/planetarySim)
- Likely cause: account out of free-tier GHA minutes (2000 min/month)
- Workaround: run scrape locally in Z.ai sandbox as daemon; weekly refresh TBD

### Catalog Scrape In Progress (2026-10-20 09:15 UTC start)
Running locally as daemon (PID 2205) with combinatorial filtering fix:
- Music: 5046 unique in 3 min (vs 1563 in old scrape) — on track for full 35,512
- Expected total time: 2-5 hours
- Log: /tmp/full_catalog.log
- Heartbeat: /home/sync/full_catalog.heartbeat

### Combinatorial Filtering Fix (commit fe5c6b8)
Breaks the 3000-item pagination cap via:
- **Music**: 3 vocalTypes x 5 bpm ranges x (duration if needed) per category
- **Footage**: 2 orientations x 3 frame rates x 8 duration buckets per category
- **Templates**: 14 categories x 4 software x 3 resolutions
- **SFX**: 185 sub-categories (no subdivision needed — categories are small enough)
- Only subdivides when actually hitting the cap (>= 2950 items fetched)

### CLI Commands (new)
- `catalog` — Full scrape (all steps in one process)
- `catalog --resume` — Run next pending step (chunked execution)
- `step <name>` — Run single step
- `progress` — Show current progress
- `reset` — Reset progress.json
- `audit` — Run E2E audit
- `mirror-signed` — Mirror signed URLs to Netlify blob
- `test-auth` — Quick auth check
- `serve --port 8000` — Serve UI

### Storage
- **Code + catalog metadata**: GitHub (wesisad5) + GitLab mirror — 186 MB JSON
- **Asset files (previews/permlinks)**: NOT stored — URLs are permlinks (non-expiring), accessed on-demand via CDN proxy
- **Signed URLs**: Netlify blob storage (verified working) — for the ~773 signed URLs with 10-year expiry
- **Netlify blob namespace**: `artlist-scraper` on site `aigc-scrape-runner`

### Pending Work
1. **Scrape completion**: Wait for daemon PID 2205 to finish (2-5 hours), then commit + push
2. **Audit**: Run `python -m src.cli audit` after scrape completes
3. **Mirror signed URLs**: Run `python -m src.cli mirror-signed` to copy ~773 signed URLs to Netlify blob
4. **Weekly refresh**: GHA broken — need alternative (Netlify build-as-compute, external cron, or upgrade GH account)
5. **JWT refresh**: Expires 2026-10-10 (~14 days from capture) — re-capture HARs and update secrets

### Key Files
- `/home/z/my-project/artlist-scraper/` — main repo (wesisad5 GH + ansgareutychisO GitLab)
- `/home/z/my-project/scripts/daemon_full_catalog.py` — full scrape daemon
- `/home/z/my-project/scripts/daemon_scrape_step.py` — single-step daemon (for chunked execution)
- `/tmp/full_catalog.log` — scrape log
- `/home/sync/full_catalog.heartbeat` — daemon heartbeat
- `.env` — secrets (committed; GIT IS THE DISK)
- `.agents/SKILL.md` — meta context for sub-agents
- `PLAN.md` — long-horizon plan
