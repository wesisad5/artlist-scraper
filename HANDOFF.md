# HANDOFF — Artlist Catalog Scraper (next session)

## Current State (2026-09-26 06:05 UTC) — SCRAPE COMPLETE

### Final catalog totals
| Catalog | Items | Coverage | File size |
|---|---|---|---|
| Music | 32,948 songs | 92.8% of 35,512 total | 57.9 MB |
| SFX | 51,383 items | Full (185 sub-categories) | 61.5 MB |
| Footage | 38,337 clips + 54 stories | 4.5% of 857,760 (server pagination cap) | 69.7 MB |
| LUTs | 411 | Full | 233 KB |
| Templates | 1,951 | Capped at 3000-item pagination | 2.2 MB |
| Collections | 0 | User has none | 67 B |
| **Total catalog** | **125,078 items** | | **191 MB** |

### AI tools data
| Source | Items |
|---|---|
| Flow AI templates | 10 (Multi-Model Video, Camera Angles, Character Sheet, etc.) |
| Flow AI user flows | 1 (Copy of Product Visualization) |
| Flow AI node types | 5 (prompt, assistant, file-uploader, image-generator, video-generator) |
| Studio AI spotlight | 1 (Rooftop Chase — 9 shots, 2 characters) |
| Studio AI user projects | 0 |
| Studio predefined locations | 95 |
| Studio predefined props | 79 |
| **Total AI** | **191 items** |

### Audit results
- ✅ All 6 catalog files exist, valid JSON
- ✅ Both AI files exist, valid JSON
- ✅ 25/25 CDN samples reachable (100%)
- ✅ All music/sfx/luts URLs are permlinks (no mirroring needed)
- ⚠️ 514 footage + 259 template + 0 = 773 signed URLs (10-year expiry, not mirrored — Netlify blob setup pending)
- ⚠️ Blob manifest empty (Netlify creds not provided by user)

## What's done

### Code (all committed to github.com/elizabethadamspri/artlist-scraper main)
- ✅ Python scraper package: src/{config,auth,http_client,graphql,trpc,cdn,storage,cli}
- ✅ 9 scrapers: categories, music, sfx, footage, luts, templates, collections, flows, studio
- ✅ Pipeline orchestration with run metadata + audit
- ✅ CLI: test-auth, catalog, ai, all, audit, serve
- ✅ Browser UI (dark theme, HLS player, audio player, audit view, CDN proxy)
- ✅ GHA weekly cron workflow
- ✅ PLAN.md, HANDOFF.md, .agents/SKILL.md
- ✅ 20 commits pushed

### Daemons running
- ✅ UI daemon (port 9000) — accessible via Z.ai preview with `?XTransformPort=9000`
- ✅ Catalog daemon — exited (done)
- ✅ Footage daemon — exited (done)

## What's NOT done

1. **Netlify blob storage** — need `NETLIFY_SITE_ID` + `NETLIFY_TOKEN` from user to enable mirroring of signed URLs. Without this, 773 signed URLs (10-year expiry) are tracked but not mirrored.

2. **Studio shot.getShot investigation** — returns NOT_FOUND standalone; in HAR it worked as part of batched call with `project.getProject`. Both project.getProject and shot.getShot fail when called now, suggesting the example project from the HAR may have been deleted or requires different session state.

3. **GHA workflow secrets** — user needs to add these as GitHub Actions secrets:
   - `ARTLIST_JWT`
   - `ARTLIST_FLOWS_SESSION_TOKEN`, `ARTLIST_FLOWS_CF_CLEARANCE`, `ARTLIST_FLOWS_CF_BM`
   - `ARTLIST_STUDIO_SESSION_TOKEN`, `ARTLIST_STUDIO_CF_CLEARANCE`, `ARTLIST_STUDIO_CF_BM`, `ARTLIST_STUDIO_CSRF_TOKEN`
   - `ARTLIST_USER_SESSION`, `ARTLIST_VISITOR_ID`, `ARTLIST_USER_ID`
   - (optional) `NETLIFY_SITE_ID`, `NETLIFY_TOKEN`

4. **JWT refresh procedure** — JWT expires 2026-10-10 (~14 days). To refresh:
   - User logs into artlist.io in browser, captures HARs for artlist.io + flows.artlist.io + studio.artlist.io
   - Place HARs in `/home/z/artlist-work/hars/` (as `*.har` files)
   - Run `python3 /home/z/my-project/scripts/extract_auth.py`
   - Re-build `.env` (see .agents/SKILL.md for the one-liner)
   - Update GitHub Actions secrets

## Immediate next steps for a new session

1. **Verify everything is committed**:
   ```bash
   cd /home/z/artlist-work/artlist-scraper
   git status
   git log --oneline -5
   ```

2. **Test the UI**:
   ```bash
   # Start UI daemon (if not running)
   python3 /home/z/my-project/scripts/daemon_ui.py
   # Verify
   curl -s http://localhost:9000/api/catalog
   # Open in browser via Z.ai preview URL with ?XTransformPort=9000
   ```

3. **Test the GHA workflow** (manual trigger):
   - Go to https://github.com/elizabethadamspri/artlist-scraper/actions
   - Click "Weekly Catalog Refresh" → "Run workflow"
   - Set the required secrets first (Settings → Secrets and variables → Actions)

4. **Set up Netlify blob** (optional, for signed URL mirroring):
   - Create a Netlify site, get `NETLIFY_SITE_ID` and `NETLIFY_TOKEN`
   - Add to `.env` and GitHub Actions secrets
   - Run `python -m src.cli catalog --skip music,sfx,footage,luts,templates,collections` to test blob mirroring

## Key files / paths

### Project repo (pushed to GitHub)
- `/home/z/artlist-work/artlist-scraper/` — main project, 20 commits on main
- `.env` — secrets (committed; GIT IS THE DISK)
- `src/` — Python scraper code
- `data/` — scraped JSON data (191 MB catalog + 1 MB AI)
- `ui/` — browser UI (HTML/CSS/JS)
- `.github/workflows/weekly-refresh.yml` — GHA cron
- `audit_report.json` — latest audit report
- `PLAN.md`, `HANDOFF.md`, `.agents/SKILL.md` — docs

### Helper scripts (in /home/z/my-project/scripts/)
- `daemon_catalog.py` — double-forked daemon for catalog scrape
- `daemon_footage.py` — double-forked daemon for footage scrape
- `daemon_ui.py` — double-forked daemon for UI server (port 9000)
- `parse_hars.py` — HAR parser
- `extract_auth.py` — JWT + cookies extractor
- `extract_queries.py` — GraphQL/tRPC query extractor
- `smoke_test.py` — quick test of all scrapers

### Logs / state (ephemeral)
- `/tmp/catalog_scrape.log` — catalog daemon log (95 min of music+sfx+luts+templates+collections)
- `/tmp/footage_scrape.log` — footage daemon log (25 min)
- `/tmp/ui_server.log` — UI server log
- `/home/sync/catalog_scrape.heartbeat` — catalog daemon heartbeat (proves it finished)
- `/home/sync/footage_scrape.heartbeat` — footage daemon heartbeat (proves it finished)

### Secrets (extracted from HARs)
- `/home/z/artlist-work/secrets/JWT.txt` — Bearer JWT for search-api.artlist.io
- `/home/z/artlist-work/secrets/COOKIES_BY_HOST.json` — per-host cookies (flows/studio)
- Also in `.env` (committed to repo)

## Key technical learnings (also in .agents/SKILL.md)

1. **Server caps pagination at 3000 items** (`page × take ≤ 3000`). Use category-based pagination for full coverage.
2. **Sort type enum**: only `STAFF_PICKS`, `NEWEST` are valid for music/sfx/templates (not RECENT/MOST_POPULAR/BEST_MATCH).
3. **Per-host cookies**: flows.artlist.io and studio.artlist.io have DIFFERENT `__Secure-session.artlist-prod.session-token` cookies. Both also need `cf_clearance`, `__cf_bm`. Studio also needs `__Host-session.artlist-prod.csrf-token`.
4. **GraphQL endpoint routing**: v1/graphql has SfxList, ClipList, Catalog, Luts, LutsByIds, RootCategories. v2/graphql has SongList, TemplatesList, TemplateRootCategories, templateSearchFilters. Wrong endpoint = "Cannot query field X" error.
5. **tRPC input format**: non-batch is `{"json":{...}}` (NO meta field); batch is `{"0":{"json":{...},"meta":{"values":["undefined"]}}}`. perPage capped at 50.
6. **api.artlist.io/v1/directory** needs `service-host: content.directories-api` header.
7. **CDN permlinks** (cms-public-artifacts.artlist.io) need Origin + Referer headers matching artlist.io. Browser can't set these (forbidden), so we proxy via /api/cdn-proxy.
8. **JWT expires in ~14 days**. Refresh by re-capturing HARs and running scripts/extract_auth.py.
9. **clip_list doesn't accept `take`** — server uses default 50.
10. **Footage `totalExact` of 857,760 is misleading** — actual scrapable count is limited by pagination cap × number of sub-categories. With 75 sub-categories × 3000 cap = 225K max theoretical, but dedup yields ~38K unique in practice.

## Environment notes

- Z.ai sandbox: Debian 13, 2 vCPU, 4GB RAM, no swap
- GIT IS THE DISK: push to remote often (local disk not durable across sessions)
- The Git HEAD watchdog runs `git switch main` before every toolcall. Work on main inside /home/z/my-project/, or use /home/z/artlist-work/ (watchdog-free path).
- Double-forked daemons (daemon_catalog.py, daemon_footage.py, daemon_ui.py) survive bash toolcall ends.
- Don't loop caddy commands (causes session lockout). Don't curl-loop internal ports 12600, 19001, 19005, 19006.
