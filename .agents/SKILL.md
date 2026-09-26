# .agents/SKILL.md — Meta-context for artlist-scraper agents

> Load at session start when working on this project. Contains hard-won knowledge
> from the initial build that isn't obvious from reading the code.

## Project: artlist-scraper
Scrapes artlist.io's asset catalog (music, SFX, footage, LUTs, video templates, collections) plus their AI tools (Studio AI + Flow/Canvas AI). Output is JSON in `data/`, viewed via browser UI in `ui/`. Weekly cron refresh via GHA.

## Critical environment facts (Z.ai sandbox)
- **GIT IS THE DISK.** Local disk is NOT durable across sessions. Commit + push every micro step.
- The bash toolcall wrapper kills all child processes at toolcall end. To run long scrapes, use the **double-fork daemon pattern** at `/home/z/my-project/scripts/daemon_catalog.py`. Verified: PID 2556 survived 35+ minutes across many toolcalls.
- Don't use `caddy run/start/stop/reload` in bash — they trigger irreversible session lockout. `caddy version` is safe.
- Don't loop-curl internal ports 12600, 19001, 19005, 19006.
- The Git HEAD watchdog runs `git switch main` before every toolcall. Stay on `main` inside `/home/z/my-project/`; do parallel work in `/tmp/my-project/worktrees/<name>`.
- For persistent work outside the watchdog path, use `/home/z/artlist-work/` (this is where I cloned the actual scraper repo).

## Artlist auth (3 mechanisms)
1. **Bearer JWT** (PS256, ~14-day expiry) for `search-api.artlist.io` and `api.artlist.io`. Extracted from HAR `authorization: Bearer eyJ...` header.
2. **Session cookie** (`__Secure-session.artlist-prod.session-token`) for `flows.artlist.io/api/trpc/*` and `studio.artlist.io/api/trpc/*`. This is an A256GCM-encrypted JWT (different per host!).
3. **Cloudflare bypass cookies** required alongside session: `cf_clearance`, `__cf_bm` (per-host). Plus `userSession`, `artlist_visitor_id`, `ajs_user_id` (common). Studio also needs `__Host-session.artlist-prod.csrf-token`.

## Artlist GraphQL endpoint routing (IMPORTANT)
Two GraphQL endpoints with DIFFERENT query sets:
- `/v1/graphql`: SfxList, ClipList, Catalog, Luts, LutsByIds, RootCategories, searchTermsAutosuggestions
- `/v2/graphql`: SongList, TemplatesList, TemplateRootCategories, templateSearchFilters

Wrong endpoint = "Cannot query field X on type Query" error. See `src/graphql.py` for which queries go where.

## tRPC input format (IMPORTANT)
- Non-batch GET: `?input={"json":{...}}` (NO `meta` field)
- Batch GET: `?batch=1&input={"0":{"json":{...},"meta":{"values":["undefined"]}},"1":{...}}`
- perPage capped at 50 by API (not 100)
- Always send `x-trpc-source: nextjs-react` header

## api.artlist.io/v1/directory gotcha
Requires `service-host: content.directories-api` header (in addition to Bearer JWT). Without it → HTTP 400.

## Asset type enum values
- For `RootCategories(assetType)`: only `music`, `sfx`, `footage`, `template` work (plugin/software/luts all rejected)
- For `searchTermsAutosuggestions(assetType)`: only `MUSIC`, `FOOTAGE` work (SFX, LUT, TEMPLATE rejected)

## CDN permlink vs signed
- **Permlink** (no expiry): `cms-public-artifacts.artlist.io/{base64-or-/content/...}`, `*.imgix.net`. Just store the URL.
- **Signed** (~10yr expiry): `cms-toolkit-artifacts.artlist.io`, `cms-artifacts.artlist.io`. Has `Expires=...&Signature=...`. Mirror to Netlify blob if user provides creds.
- **Proxy**: `artlist-studio-proxy.imgix.net/{encoded_signed_url}`. Extract target via `urllib.parse.unquote(path.lstrip('/'))`.

## CDN fetch gotcha
`cms-public-artifacts.artlist.io/{base64}` URLs 302-redirect to `/content/...` path. **The redirect requires `Origin` + `Referer` headers matching `https://artlist.io`** — without them you get 403. See `src/auth.py:cdn_headers()`.

## Footage catalog is HUGE
- `totalExact: 857,760` clips. With take=50, that's 17,000 pages for "all".
- Strategy: paginate "all" first (catches 5K-10K most popular), then per-sub-category with `filterCategories=[cat_id]` to catch the rest.
- ~50 sub-categories × ~340 pages avg = ~17,000 reqs total. At 5 RPS = ~1 hour.
- Music (35,512 songs) is much smaller: 711 pages × 4 sorts = ~2,800 reqs = ~10 min.

## Studio shot.getShot mystery
- `shot.getShot?id={shotId}` returns NOT_FOUND when called standalone
- Same call works when batched with `project.getProject?id={projectId}` (HAR evidence)
- Possibly requires server-side session state from a prior project.getProject call
- Workaround: `project.getSpotlightProjects` already returns rich project metadata (id, name, type, previewImageUrl, shotCount, characters[], shotId). For deeper shot data, would need to investigate batched call pattern.

## Pagination patterns
- Music: returns `totalResults` — stop when collected >= 95% of total
- SFX: no totalResults returned — stop when 3 pages in a row have no new items
- Footage: returns `totalExact` — stop per-filter when collected >= 95% of that filter's total
- LUTs: no total — stop when empty page
- Templates: no total — stop when empty page or fewer-than-take returned

## Sort options to maximize coverage
- Music SongList: `STAFF_PICKS`, `RECENT`, `MOST_POPULAR`, `BEST_MATCH` (dedupe by songId across sorts)
- SFX SfxList: `STAFF_PICKS`, `RECENT`, `MOST_POPULAR` (dedupe by songId)
- Templates: `STAFF_PICKS`, `RECENT`, `MOST_POPULAR`, `BEST_MATCH` (dedupe by id)

## Quick reference commands
```bash
# Test auth
cd /home/z/artlist-work/artlist-scraper && python3 -m src.cli test-auth

# Run catalog scrape (foreground, blocks)
python3 -m src.cli catalog --skip footage

# Run catalog scrape (daemon, survives bash toolcalls)
python3 /home/z/my-project/scripts/daemon_catalog.py --skip footage
tail -f /tmp/catalog_scrape.log
cat /home/sync/catalog_scrape.heartbeat

# Run AI scrape (fast, ~25s)
python3 -m src.cli ai

# Run audit
python3 -m src.cli audit

# Serve UI
python3 -m src.cli serve --port 8000

# Push to remote
cd /home/z/artlist-work/artlist-scraper && git add -A && git commit -m "..." && git push
```

## JWT refresh procedure (every ~14 days)
1. User logs into artlist.io in browser, captures HAR for artlist.io + flows.artlist.io + studio.artlist.io
2. Place HARs in `/home/z/artlist-work/hars/` (as `*.har` files)
3. Run `python3 /home/z/my-project/scripts/extract_auth.py` — produces `/home/z/artlist-work/secrets/{JWT.txt,COOKIES_BY_HOST.json}`
4. Run the .env builder:
   ```python
   python3 -c "
   import json
   cookies = json.load(open('/home/z/artlist-work/secrets/COOKIES_BY_HOST.json'))
   jwt = open('/home/z/artlist-work/secrets/JWT.txt').read().strip()
   flows = cookies.get('flows.artlist.io', {})
   studio = cookies.get('studio.artlist.io', {})
   env = f'''ARTLIST_JWT={jwt}
   ARTLIST_FLOWS_SESSION_TOKEN={flows.get(\"__Secure-session.artlist-prod.session-token\", \"\")}
   ARTLIST_FLOWS_CF_CLEARANCE={flows.get(\"cf_clearance\", \"\")}
   ARTLIST_FLOWS_CF_BM={flows.get(\"__cf_bm\", \"\")}
   ARTLIST_STUDIO_SESSION_TOKEN={studio.get(\"__Secure-session.artlist-prod.session-token\", \"\")}
   ARTLIST_STUDIO_CF_CLEARANCE={studio.get(\"cf_clearance\", \"\")}
   ARTLIST_STUDIO_CF_BM={studio.get(\"__cf_bm\", \"\")}
   ARTLIST_STUDIO_CSRF_TOKEN={studio.get(\"__Host-session.artlist-prod.csrf-token\", \"\")}
   '''
   print(env)
   " > /home/z/artlist-work/artlist-scraper/.env
   ```
5. Also update GitHub Actions secrets: `ARTLIST_JWT`, `ARTLIST_FLOWS_SESSION_TOKEN`, etc.
