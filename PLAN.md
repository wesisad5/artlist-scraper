# PLAN — Artlist Catalog Scraper

## Mission
Programmatically build out Artlist's full asset catalog (music, SFX, footage, LUTs, video templates, collections) plus their AI creation tools (Studio AI + Flow/Canvas AI), with weekly cron refresh and browser UI for visualization.

## Status (2026-09-26 06:05 UTC) — SCRAPE COMPLETE

### Done
- [x] HAR analysis (10 files, 2609 API calls, 11 GraphQL ops, 31 tRPC ops)
- [x] Auth: Bearer JWT for search-api.artlist.io + per-host session cookies for flows/studio tRPC
- [x] Scraper framework: config, auth, http_client (with retry + rate limit), graphql, trpc, cdn classifier, storage (Netlify blob)
- [x] 9 catalog/AI scrapers
- [x] Pipeline orchestration with run metadata
- [x] E2E audit pipeline (25/25 CDN samples reachable)
- [x] CLI entry point
- [x] Browser UI (tabs, HLS player, audio player, audit view, CDN proxy)
- [x] GHA weekly cron workflow
- [x] AI tools scrape complete (10 flow templates, 1 user flow, 5 node types, 1 studio spotlight, 95 locations, 79 props)
- [x] Catalog scrape complete: 125,078 items total
  - Music: 32,948 (92.8% of 35,512)
  - SFX: 51,383 (full via 185 sub-categories)
  - Footage: 38,337 clips + 54 stories (4.5% of 857,760 — pagination cap limited)
  - LUTs: 411 (full)
  - Templates: 1,951 (capped)
  - Collections: 0 (user has none)
- [x] 20 commits pushed to github.com/elizabethadamspri/artlist-scraper main

### Pending (need user input or future work)
- [ ] Netlify blob storage setup (need NETLIFY_SITE_ID + NETLIFY_TOKEN from user) — for mirroring 773 signed URLs
- [ ] GHA workflow secrets (user needs to add to GitHub Actions settings)
- [ ] JWT refresh procedure (every ~14 days, JWT expires 2026-10-10)
- [ ] Studio shot.getShot investigation (returns NOT_FOUND standalone)
- [ ] Footage catalog deeper pagination (currently 4.5% — would need finer filters like category + orientation + duration to get more)

## Architecture

### Code layout
```
artlist-scraper/
├── src/
│   ├── config.py          # env loading, constants, asset type IDs
│   ├── auth.py            # per-host header/cookie builders
│   ├── http_client.py     # urllib-based HTTP with retry + rate limit
│   ├── graphql.py         # 11 GraphQL queries (SongList, SfxList, ClipList, Catalog, Luts, TemplatesList, RootCategories, etc.)
│   ├── trpc.py            # tRPC client for flows + studio (high-level helpers)
│   ├── cdn.py             # URL classifier (permlink / signed / proxy)
│   ├── storage.py         # Netlify blob manifest + mirror
│   ├── scrapers/          # 9 per-catalog scrapers
│   ├── pipelines/         # catalog.py (orchestration) + audit.py
│   └── cli.py             # CLI: test-auth, catalog, ai, all, audit, serve
├── data/                  # JSON output (191 MB, committed to repo)
│   ├── catalog/           # music, sfx, footage, luts, templates, collections, categories, search_terms
│   ├── ai/                # flows, studio
│   └── _meta/             # run metadata
├── ui/                    # Browser UI (HTML/CSS/JS)
├── .github/workflows/     # weekly cron GHA
├── analysis/              # HAR analysis artifacts
└── .env                   # secrets (committed since GIT IS THE DISK)
```

### Key API endpoints discovered

| Endpoint | Auth | Notes |
|---|---|---|
| `search-api.artlist.io/v1/graphql` | Bearer JWT | SfxList, ClipList, Catalog, Luts, LutsByIds, RootCategories, searchTermsAutosuggestions |
| `search-api.artlist.io/v2/graphql` | Bearer JWT | SongList, TemplatesList, TemplateRootCategories, templateSearchFilters |
| `api.artlist.io/v1/directory` | Bearer JWT + `service-host: content.directories-api` header | Collections |
| `flows.artlist.io/api/trpc/*` | flows session cookie | template.list, flow.list, flow.get, flow.outputs, catalog.getNodeCatalog, assets.resolveUrl, node.getUiConfig |
| `studio.artlist.io/api/trpc/*` | studio session cookie (DIFFERENT from flows) | project.getSpotlightProjects, project.getProjects, shot.getShot, shot.getShotFrames, location.getPredefinedLocations, prop.getPredefinedProps, models.getModelGroupFeatures |

### CDN URL classification
- **Permlink** (no expiry): `cms-public-artifacts.artlist.io/{base64 or /content/...}`, `*.imgix.net`. Just store the URL.
- **Signed** (~10yr expiry): `cms-toolkit-artifacts.artlist.io`, `cms-artifacts.artlist.io`, `template-private.imgix.net`. Has `Expires=...&Signature=...`. Mirror to Netlify blob if user provides creds.
- **Proxy**: `artlist-studio-proxy.imgix.net/{encoded_url}` (wraps signed URLs).

### Auth refresh
JWT expires in ~14 days. To refresh:
1. Open browser, log into artlist.io
2. Capture HAR for artlist.io + flows.artlist.io + studio.artlist.io
3. Run `python3 scripts/extract_auth.py` (after placing HARs in /home/z/artlist-work/hars/)
4. Update `.env` and GitHub Actions secrets

## Future Work

### P0 (immediate — for production use)
- User adds GitHub Actions secrets
- User sets up Netlify site (optional, for blob mirroring)
- User triggers GHA workflow manually to verify

### P1 (next iteration)
- Investigate studio shot.getShot batched-call requirement
- Add subscription-tier-aware filtering (only fetch assets user can actually download)
- Add differential scraping (only fetch new items since last run)
- Add per-asset detail pages (fetch full asset metadata, not just search results)

### P2 (long horizon)
- Set up Studio flow / shot creation flow (POST endpoints) for programmatic AI generation
- Add footage catalog deeper pagination (combine category + orientation + duration filters)
- Add Netlify Functions for server-side UI (instead of Python http.server)
- Add user authentication to the UI (for private catalog browsing)
