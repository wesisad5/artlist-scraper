# HANDOFF — Artlist Catalog Scraper (next session)

## Current State (2026-09-26 04:20 UTC)

### What's working
- ✅ All 3 auth methods (Bearer JWT, flows session cookie, studio session cookie)
- ✅ All 9 scrapers (categories, music, sfx, footage, luts, templates, collections, flows, studio)
- ✅ AI tools scrape complete: 10 flow templates, 1 user flow, 5 node types, 1 studio spotlight project, 95 locations, 79 props
- ✅ Browser UI with CDN proxy (port 9000 via daemon)
- ✅ GHA weekly cron workflow
- ✅ Pipeline orchestration + audit
- ✅ Pagination cap (3000 items) handled via category-based pagination

### What's in progress
- 🔄 Catalog scrape running as daemon (PID 3154) — music at category 40/97, ~30K unique songs so far
  - Music should finish in ~30 more min
  - Then: sfx (~15 min), luts (~2 min), templates (~10 min), collections (~1 min)
  - Footage SKIPPED in current run (deferred to separate daemon)
- 🔄 UI daemon running (port 9000) — accessible via Z.ai preview `?XTransformPort=9000`

### What's NOT done
- ❌ Footage scrape (deferred — ~1-2 hours of API calls)
- ❌ Netlify blob storage setup (need NETLIFY_SITE_ID + NETLIFY_TOKEN from user)
- ❌ Studio shot.getShot investigation (returns NOT_FOUND standalone; works in batched call with project.getProject)
- ❌ Studio: only 1 spotlight project returned; may be more discoverable
- ❌ Audit run on final data
- ❌ Final push to remote

## Immediate next steps (in priority order)

### 1. Wait for catalog scrape to finish
```bash
tail -f /tmp/catalog_scrape.log
cat /home/sync/catalog_scrape.heartbeat
```
Daemon PID 3154. When done, `data/_meta/latest.json` will be updated with totals.

### 2. Start footage scrape as separate daemon
```bash
# After music/sfx/luts/templates/collections are done
python3 /home/z/my-project/scripts/daemon_catalog.py  # no --skip this time, but footage will be the only thing left
# OR more targeted:
python3 -c "
import sys; sys.path.insert(0, '/home/z/artlist-work/artlist-scraper')
from src.scrapers import footage
data = footage.scrape_footage(max_pages_per_filter=60)
import json; json.dump(data, open('/home/z/artlist-work/artlist-scraper/data/catalog/footage.json', 'w'), indent=2)
"
```

### 3. Run audit
```bash
cd /home/z/artlist-work/artlist-scraper && python3 -m src.cli audit > audit_report.json
cat audit_report.json
```

### 4. Test UI end-to-end
```bash
# UI daemon should still be running on port 9000
curl -s http://localhost:9000/api/catalog  # verify data loads
# Open in browser via Z.ai preview URL with ?XTransformPort=9000
```

### 5. Commit + push final data
```bash
cd /home/z/artlist-work/artlist-scraper
git add -A
git commit -m "Catalog scrape complete + audit"
git push origin main
```

## Key files / paths

### Project repo (push to remote for persistence)
- `/home/z/artlist-work/artlist-scraper/` — main project, pushes to github.com/elizabethadamspri/artlist-scraper
- `.env` — secrets (committed; GIT IS THE DISK)
- `src/` — Python scraper code
- `data/` — scraped JSON data (committed)
- `ui/` — browser UI (HTML/CSS/JS)
- `.github/workflows/weekly-refresh.yml` — GHA cron
- `PLAN.md` — long-horizon plan
- `.agents/SKILL.md` — meta context for sub-agents

### Helper scripts (in /home/z/my-project/scripts/)
- `daemon_catalog.py` — double-forked daemon for catalog scrape (survives bash toolcalls)
- `daemon_ui.py` — double-forked daemon for UI server (port 9000)
- `parse_hars.py` — HAR parser (extracts API endpoints + auth)
- `extract_auth.py` — extracts JWT + cookies from HARs
- `extract_queries.py` — extracts GraphQL/tRPC queries from HARs
- `smoke_test.py` — quick test of all scrapers (1 page each)

### Logs / state
- `/tmp/catalog_scrape.log` — catalog daemon log
- `/tmp/ui_server.log` — UI server log
- `/home/sync/catalog_scrape.heartbeat` — heartbeat from catalog daemon (proves it's alive across toolcalls)

### Secrets (extracted from HARs, in /home/z/artlist-work/secrets/)
- `JWT.txt` — Bearer JWT for search-api.artlist.io
- `COOKIES_BY_HOST.json` — per-host cookies (flows.artlist.io, studio.artlist.io)

## Key technical learnings (also in .agents/SKILL.md)

1. **Server caps pagination at 3000 items** (`page × take ≤ 3000`). Use category-based pagination for full coverage.
2. **Sort type enum**: only `STAFF_PICKS`, `NEWEST` are valid for music/sfx/templates (not RECENT/MOST_POPULAR/BEST_MATCH).
3. **Per-host cookies**: flows.artlist.io and studio.artlist.io have DIFFERENT `__Secure-session.artlist-prod.session-token` cookies. Both also need `cf_clearance`, `__cf_bm`. Studio also needs `__Host-session.artlist-prod.csrf-token`.
4. **GraphQL endpoint routing**: v1/graphql has SfxList, ClipList, Catalog, Luts, LutsByIds, RootCategories. v2/graphql has SongList, TemplatesList, TemplateRootCategories, templateSearchFilters. Wrong endpoint = "Cannot query field X" error.
5. **tRPC input format**: non-batch is `{"json":{...}}` (NO meta field); batch is `{"0":{"json":{...},"meta":{"values":["undefined"]}}}`. perPage capped at 50.
6. **api.artlist.io/v1/directory** needs `service-host: content.directories-api` header.
7. **CDN permlinks** (cms-public-artifacts.artlist.io) need Origin + Referer headers matching artlist.io. Browser can't set these (forbidden), so we proxy via /api/cdn-proxy.
8. **JWT expires in ~14 days**. Refresh by re-capturing HARs and running scripts/extract_auth.py.

## Known issues / TODOs for future sessions

1. **Studio shot.getShot** returns NOT_FOUND when called standalone. In the HAR, it works as part of a batched call with `project.getProject?id={projectId}`. Need to investigate if there's session state required, or if a different endpoint should be used.

2. **Studio spotlight projects**: only 1 returned (`Rooftop Chase`). The HAR showed 2 example URLs (`/example/9f92f096...` and `/example/a18466fe...`). Maybe there are more example projects accessible via a different endpoint (e.g. user projects? or a separate examples endpoint?).

3. **Netlify blob storage**: storage.py has the API implemented but untested. Need NETLIFY_SITE_ID + NETLIFY_TOKEN from user to enable mirroring of signed URLs (10-year expiry but still signed).

4. **Footage catalog size**: 857,760 clips total. With 3000-item cap per filter and 38 sub-categories, max coverage = 38 × 3000 = 114,000 (13% of total). To get more, would need finer-grained filters (e.g. combine category + orientation + duration).

5. **GHA workflow**: has a step to deploy UI to Netlify but it requires NETLIFY_SITE_ID. Without it, the workflow still runs the scrape but skips the deploy.

## Environment notes

- Z.ai sandbox: Debian 13, 2 vCPU, 4GB RAM, no swap
- GIT IS THE DISK: push to remote often (local disk not durable across sessions)
- The Git HEAD watchdog runs `git switch main` before every toolcall. Work on main inside /home/z/my-project/, or use /home/z/artlist-work/ (watchdog-free path).
- Double-forked daemons (daemon_catalog.py, daemon_ui.py) survive bash toolcall ends.
- Don't loop caddy commands (causes session lockout). Don't curl-loop internal ports 12600, 19001, 19005, 19006.
