# PLAN — Artlist Catalog Scraper

## Mission
Programmatically build out Artlist's full asset catalog (music, SFX, footage, LUTs, video templates, collections) plus their AI creation tools (Studio AI + Flow/Canvas AI), with weekly cron refresh and browser UI for visualization.

## Status (2026-09-26)

### Done
- [x] HAR analysis (10 files, 2609 API calls, 11 GraphQL ops, 31 tRPC ops)
- [x] Auth: Bearer JWT for search-api.artlist.io + per-host session cookies for flows/studio tRPC
- [x] Scraper framework: config, auth, http_client (with retry + rate limit), graphql, trpc, cdn classifier, storage (Netlify blob)
- [x] 9 catalog/AI scrapers
- [x] Pipeline orchestration with run metadata
- [x] E2E audit pipeline
- [x] CLI entry point
- [x] Browser UI (tabs, HLS player, audio player, audit view)
- [x] GHA weekly cron workflow
- [x] AI tools scrape complete (flows + studio, 10+1+5+95+79 items)

### In Progress
- [ ] Catalog scrape (music in progress, sfx/luts/templates/collections queued; footage deferred)
- [ ] Double-forked daemon keeps running across bash toolcalls (verified PID 2556 alive)

### Pending
- [ ] Footage scrape (~17,000 requests, ~1 hour) — defer to second daemon after music/sfx/etc done
- [ ] Netlify blob storage setup (need NETLIFY_SITE_ID + NETLIFY_TOKEN from user)
- [ ] Studio shot.getShot investigation (returns NOT_FOUND standalone but works in batched call)
- [ ] Studio: discover more example projects beyond `project.getSpotlightProjects` (only returns 1)
- [ ] Push everything to GitHub remote
- [ ] Test UI serving end-to-end
- [ ] Run audit after scrape completes
- [ ] Document setup in README

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
├── data/                  # JSON output (committed)
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
- **Permlink** (no expiry): `cms-public-artifacts.artlist.io/{base64 or /content/...}`, `*.imgix.net`
- **Signed** (10-year expiry): `cms-toolkit-artifacts.artlist.io`, `cms-artifacts.artlist.io` (Expires=..., Signature=...)
- **Proxy**: `artlist-studio-proxy.imgix.net/{encoded_url}` (wraps signed URLs)

### Auth refresh
JWT expires in ~14 days. To refresh:
1. Open browser, log into artlist.io
2. Capture HAR for artlist.io + flows.artlist.io + studio.artlist.io
3. Run `python3 scripts/extract_auth.py` (after placing HARs in /home/z/artlist-work/hars/)
4. Update `.env` and GitHub Actions secrets

## Future Work

### P0 (this session)
- Finish catalog scrape (music, sfx, luts, templates, collections)
- Start footage scrape as second daemon
- Run audit, verify data integrity
- Serve UI, verify it works end-to-end
- Push everything to remote

### P1 (next session)
- Investigate studio shot.getShot batched-call requirement
- Set up Netlify blob (after user provides creds) for mirroring signed URLs
- Add CDN proxy endpoint to UI server (for cms-public-artifacts URLs that need Origin/Referer)
- Investigate discovering more studio example projects

### P2 (long horizon)
- Add subscription-tier-aware filtering (only fetch assets user can actually download)
- Add differential scraping (only fetch new items since last run)
- Add per-asset detail pages (fetch full asset metadata, not just search results)
- Set up Studio flow / shot creation flow (POST endpoints) for programmatic AI generation
