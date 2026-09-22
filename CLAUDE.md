# Link Ledger — Claude Code brief

## What this is

A monthly content audit for the MyOperator blog. It joins three data sources on URL slug and produces a ranked fix list plus a shareable dashboard.

Built as a reaction to an internal problem: SEO decisions were being made on search-side data only (impressions, CTR, position). Nobody could see internal link structure, and nobody could see what readers did after clicking. This covers both.

## Why Claude Code and not a chat tool

Two reasons, both about state:

1. **Snapshots and diffs.** Each run writes `snapshots/YYYY-MM-DD.json`. Run two onwards compares against the previous snapshot: orphans fixed, orphans newly created by this month's publishing, cluster traffic changes, cluster density changes. A chat tool starts from zero every time.
2. **Clarity's 3-day cap.** The Clarity Data Export API only returns the previous 1 to 3 days and allows 10 requests per project per day. Historical scroll data cannot be backfilled. The only way to build a behavioural history is to pull daily and accumulate. That requires a scheduled job.

## Data sources

| Source | Method | Gives |
|---|---|---|
| Live site HTML | `requests` over public URLs | Internal links, H2 structure, word count |
| Google Search Console | Manual CSV export, Pages report | Clicks, impressions, CTR, position |
| Microsoft Clarity | Data Export API | Scroll depth, friction signals, JS errors, Core Web Vitals |

No Webflow API token is needed. The first version used the Webflow MCP connector, but fetching published HTML directly gets identical content, costs nothing, and also covers static pages that the Webflow CMS API cannot bulk-read.

GSC UI export caps at 1,000 rows. Filter to pages containing `/blog` before exporting.

## Current pipeline

```
crawl.py        # fetch live HTML, extract body-scoped links + H2s → pages.json
analyze.py      # link graph, TF-IDF clustering, orphans, unlinked pairs → snapshot.json
parse_clarity.py# parse Clarity dashboard CSV exports → health.json
build_html.py   # render dashboard → link-ledger.html
add_health.py   # inject Health tab (should be merged into build_html.py)
```

Body extraction is scoped to `.blog-content` (falls back to `div.w-richtext`, then `main`). This matters: without scoping, nav and footer links flood the graph and every page looks connected.

## Baseline findings, 2026-09-21

- 575 blogs crawled from sitemap, 168 static pages
- 81 URLs return 404 while still earning impressions in GSC
- **166 broken internal link instances across 58 dead targets**, none of which appear in the sitemap or GSC
- 1,405 blog-to-blog internal links
- **229 orphans (40%)** — zero inbound internal links from anywhere on the site
- Across 168 static pages there is exactly **one** link into the blog: money pages and content archive are structurally disconnected
- Average scroll depth 33.2% over 90 days, 28.1% over the last 3 days
- Blog conversion is near zero: form submissions on 11 of 18,706 sessions. Dead clicks (5.23%) and quick-back clicks (4.69%) both exceed every conversion event
- A JavaScript error reading `banner.classList` on a null element accounts for ~50% of error sessions
- INP at 240ms, above Google's 200ms threshold
- 78 sessions referred from ChatGPT and Gemini combined

**The most useful finding:** the AI cluster (37 pages) has the highest internal link density on the site at 4.76 links per page, nearly double any other cluster, and among the lowest traffic. Internal linking is therefore not the constraint on AI page traffic. That rules out one hypothesis and redirects effort.

## Expected outputs

Every run should produce:

1. **Orphan list** — blogs with zero inbound links, sorted by impressions. This is the headline deliverable.
2. **Link opportunity queue** — pairs of blogs with high TF-IDF similarity and no link between them, prioritised by the source blog's clicks. This is the actionable work item.
3. **Cluster table** — pages, clicks, internal links, density, orphans per cluster. Density below 1.0 means the cluster is a set of unconnected pages.
4. **404 list** — dead URLs still accumulating impressions, for redirect.
5. **Health panel** — Clarity behavioural metrics, friction signals, JS errors, Core Web Vitals.
6. **Force graph** — nodes sized by GSC clicks, coloured by cluster. Cluster size reflects earned traffic, not word count. This distinction is deliberate: a cloud sized by content volume would just measure the publishing calendar.
7. **Diff against previous snapshot** — the thing that makes this a process rather than a report.

## Build tasks

### 1. Self-updating crawl — DONE
`crawl.py` reads from `https://myoperator.com/sitemap.xml`, unioned with any GSC URLs not in the sitemap. GSC supplies clicks and impressions, joined on normalised URL.

A second pass probes every link target that falls outside the crawl universe. **Do not remove this.** Without it, a link pointing at a deleted page is silently dropped and the source page appears to have no outbound links at all. That bug understated the corpus by 104 blogs and hid 166 broken links.

### 2. Snapshot diffing
`analyze.py` should write to `snapshots/YYYY-MM-DD.json` and, when an earlier snapshot exists, emit a diff covering: orphans resolved, orphans created, cluster click deltas, cluster density deltas, new 404s, resolved 404s.

### 3. Changes tab
`build_html.py` renders the diff as a tab. Merge `add_health.py` into `build_html.py` rather than keeping it as a post-processing step.

### 4. Clarity daily pull — DONE
`pull_clarity.py` calls:
```
GET https://www.clarity.ms/export-data/api/v1/project-live-insights
    ?numOfDays=3&dimension1=URL
Authorization: Bearer $CLARITY_TOKEN
```
Token is read from the `CLARITY_TOKEN` environment variable (a GitHub Actions
secret in production), never from a file. Each response is appended to
`clarity/YYYY-MM-DD.json`. Runs on `.github/workflows/clarity-pull.yml`, 3x/day
(~8h apart), well under the 10-requests-per-project-per-day cap.

**Not yet verified**: whether breaking down by `URL` actually returns scroll
depth per page. The docs list dimensions and metrics separately and do not
show a worked URL example. `pull_clarity.py` checks this on every run and
prints `per-URL scroll depth present: true/false` — read that line on the
first real run in the Action logs. If true, join it to the snapshot on slug
and add a Scroll tab flagging blogs with high impressions and low scroll
depth. If false, the Clarity leg stays at the site-aggregate level (as it is
today) and that limitation should be stated plainly rather than worked
around — do not build the per-blog join until this is confirmed.

## Bugs already found and fixed — do not reintroduce

1. **Crawl universe was the GSC CSV.** Blogs with no search data were invisible and links pointing at them were dropped. Fixed by crawling the sitemap. Understated the corpus by 104 blogs.
2. **Link targets outside the crawl set were dropped silently.** A page linking only to deleted pages showed "0 outbound links" instead of "2 broken links". Fixed by the probe pass in `crawl.py`. Surfaced 166 broken links.
3. **GSC rows were overwriting, not aggregating.** Multiple rows normalise to one URL (query-string variants); a last-write-wins dict dropped ~27% of total clicks. Fixed by summing clicks and impressions and weighting position by impressions.
4. **Classification matched on H2 headings.** CTA headings mention the brand, case studies and chat on nearly every post, so every rule matched everything. `buckets.py` matches title and slug only.
5. **Brand regex matched the domain.** `myoperator` appears in every URL. Slug must be the path only.

## Classification

`buckets.py` holds rule-based classification: five pillars (AI Agents, WhatsApp, Calling & Comms, Branded, Case Studies), each with sub-buckets sharing a hue family. Order matters, first match wins. This replaced TF-IDF clustering, which produced groupings nobody could act on.

Known gaps: the `CLIENTS` list needs more customer names added as case studies publish. "Business & workplace" is the catch-all and should be reviewed periodically for pillar content that landed there by default.

## Constraints and honest limits

- Clusters come from TF-IDF term similarity, not from Webflow category tags. Some groupings will look odd on inspection. Do not present them as the site's taxonomy.
- The orphan count considers links found in page body content only, scoped to `.blog-content`. Navigation, footer and category-listing links are excluded by design, since including them makes every page look connected.
- Any count that can be zero for two different reasons must distinguish them in the output. "0 outbound links" and "2 outbound links, both broken" are different findings.
- Clarity session counts between the 90-day and 3-day windows are not internally consistent (3 days shows 31% of the 90-day total). Treat session and bot counts as indicative. Rate-based metrics are comparable.
- Bot traffic is roughly 90% of blog sessions in Clarity. Worth checking whether it inflates any dashboard the team reports on.

## Conventions

- No em-dashes as connectives anywhere in generated output
- Numbers must come from the data, never estimated or filled in from memory
- If a data source fails or returns something unexpected, say so in the output rather than degrading silently
