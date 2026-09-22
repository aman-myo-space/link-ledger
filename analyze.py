import glob, json, os, csv, collections, numpy as np
from datetime import datetime
from urllib.parse import urlparse, urldefrag
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from buckets import classify, PARENT_COLOUR, PARENT_ORDER


def norm(u):
    """Canonicalise a URL/path the same way for blog URLs and link targets:
    scheme-agnostic, no fragment, no trailing slash. Without this, a link
    written as http:// (rather than https://) or with a trailing slash
    never matches a known blog's canon URL, so it gets miscounted as a
    broken/static link instead of a real internal edge."""
    if u.startswith('/'):
        u = f"https://myoperator.com{u}"
    u = urldefrag(u)[0]
    p = urlparse(u)
    if p.netloc.replace('www.', '') != 'myoperator.com':
        return None
    return "https://myoperator.com" + (p.path.rstrip('/') or '/')


# --- Load blogs from Webflow CSV export (via blogs.json) ---
print("Loading blogs from data/blogs.json...")
blogs_data = json.load(open("data/blogs.json"))
blogs_list = blogs_data["blogs"]
print(f"  {len(blogs_list)} published blogs loaded")

# --- Load GSC data (clicks, impressions, CTR, position) ---
# Several rows can normalise to the same blog URL (trailing slash, UTM query
# string variants -- confirmed on the real data: complete-guide-for-toll-
# free-number has an 895-click row and a 0-click "/...-number/" duplicate).
# A last-write-wins dict silently zeroes out real traffic whenever the
# duplicate happens to be read after the real row. Aggregate instead: sum
# clicks and impressions, weight position by impressions. This is CLAUDE.md
# bug #3, already documented as fixed once -- reintroduced when analyze.py
# was rewritten for the Webflow migration.
print("Loading GSC metrics from data/Pages.csv...")
agg = {}
with open("data/Pages.csv", newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')  # Tab-delimited
    for row in reader:
        url = norm(row.get('Top pages', '').strip())
        if not url or '/blog/' not in url:
            continue
        c = int(row.get('Clicks', 0) or 0)
        i = int(row.get('Impressions', 0) or 0)
        pos = float(row.get('Position', 0) or 0)
        a = agg.setdefault(url, {'clicks': 0, 'impressions': 0, 'pos_wt': 0.0})
        a['clicks'] += c
        a['impressions'] += i
        a['pos_wt'] += pos * max(i, 1)
gsc = {url: {
    'clicks': a['clicks'], 'impressions': a['impressions'],
    'ctr': (a['clicks'] / a['impressions']) if a['impressions'] else 0.0,
    'position': round(a['pos_wt'] / max(a['impressions'], 1), 2),
    'in_gsc': True,
} for url, a in agg.items()}
print(f"  {len(gsc)} GSC URLs matched")

# --- Load per-blog scroll depth from Clarity pulls, newest first ---
# The API's dimension1=URL breakdown fragments one blog across several
# UTM-tagged URL variants, each with its own averageScrollDepth. Join each
# variant's Url 1:1 to the Traffic block's totalSessionCount and take a
# session-weighted average per blog (falling back to a plain mean if every
# variant shows 0 sessions, which happens often at this traffic volume).
#
# Real limitation, not cosmetic: every metric block in the response is
# capped at exactly 1000 rows with no pagination cursor, so only a subset
# of blogs show up in any single pull (confirmed: ~360 of 578 on the first
# real pull). Calling the API more often the same day does not get past
# this -- it's the same rolling 3-day window returning the same top rows,
# not a paginated quota. What does help: the window shifts and different
# long-tail URLs surface as separate pulls accumulate in clarity/, so a
# blog missing from today's pull may appear in yesterday's. We fall back
# through older pulls (newest first) for any blog still missing, and tag
# every value with the pull date actually used so a stale backfilled
# number is never mistaken for today's. A blog with no value in ANY pull
# on record is "no data", never "0%".
def scroll_from_pull(pull_data):
    """(canon URL -> session-weighted average scroll depth) for one pull's data.

    Verified against the real 2026-09-22 pull: wherever a ScrollDepth entry's
    exact URL also has a Traffic row we can check, averageScrollDepth == 100
    corresponds to totalSessionCount == 1 every single time (6/6 checked).
    A single-session average is degenerate by construction (one visitor
    either hit the bottom or didn't), not a real reading of typical
    behaviour -- this is what caused values here to disagree with Clarity's
    own dashboard, which almost certainly applies its own minimum-sample
    floor before displaying a number.
    Fix is targeted, not a blanket confidence filter: requiring positive
    Traffic corroboration for *every* entry collapses coverage from 360 to
    53 blogs, because ScrollDepth's and Traffic's top-1000 rows are capped
    independently and barely overlap -- most entries simply have no
    Traffic row to check, which is not itself evidence of a bad reading.
    So only the proven failure mode is excluded: an exact 100 with fewer
    than 3 corroborated sessions. Everything else is kept as before.
    """
    scroll_block = next((b["information"] for b in pull_data if b.get("metricName") == "ScrollDepth"), [])
    traffic_by_raw_url = {e["Url"]: e for e in next((b["information"] for b in pull_data if b.get("metricName") == "Traffic"), []) if e.get("Url")}

    weighted = collections.defaultdict(lambda: [0.0, 0])  # canon -> [session-weighted sum, total sessions]
    unweighted = collections.defaultdict(list)  # canon -> [averageScrollDepth, ...] for the zero-session fallback
    for e in scroll_block:
        raw_url = e.get("Url")
        depth = e.get("averageScrollDepth")
        canon = norm(raw_url) if raw_url else None
        if not canon or "/blog/" not in canon or depth is None:
            continue
        sessions = traffic_by_raw_url.get(raw_url, {}).get("totalSessionCount", 0) or 0
        if depth == 100 and sessions < 3:
            continue  # proven single-session artifact pattern -- discard, don't average in
        unweighted[canon].append(depth)
        if sessions > 0:
            weighted[canon][0] += depth * sessions
            weighted[canon][1] += sessions

    result = {}
    for canon, values in unweighted.items():
        if canon in weighted and weighted[canon][1] > 0:
            result[canon] = round(weighted[canon][0] / weighted[canon][1], 1)
        else:
            result[canon] = round(sum(values) / len(values), 1)
    return result


scroll_by_url = {}  # canon -> {"scroll": float, "as_of": "YYYY-MM-DD"}
clarity_files = sorted(glob.glob("clarity/*.json"), reverse=True)  # newest first
for path in clarity_files:
    pull_date = os.path.basename(path).removesuffix(".json")
    pulls = json.load(open(path))
    if not pulls:
        continue
    for canon, scroll in scroll_from_pull(pulls[-1]["data"]).items():
        if canon not in scroll_by_url:
            scroll_by_url[canon] = {"scroll": scroll, "as_of": pull_date}

if clarity_files:
    latest_date = os.path.basename(clarity_files[0]).removesuffix(".json")
    stale = sum(1 for v in scroll_by_url.values() if v["as_of"] != latest_date)
    print(f"  Loaded {len(clarity_files)} pull(s): scroll depth for {len(scroll_by_url)} blogs"
          + (f" ({stale} backfilled from an older pull)" if stale else ""))
else:
    print("  No clarity/*.json pulls found -- Scroll tab will show no data for every blog.")

# --- Convert blogs.json to pages dict (mimic crawled format) ---
ok = []
for b in blogs_list:
    page = {
        'canon': norm(b['url']),
        'title': b['title'],
        'h2s': b['h2_headings'],
        'text': ' '.join(b['h2_headings']),  # Minimal text for TF-IDF
        'outlinks': [{'to': t, 'anchor': ''} for link in b['internal_links'] if (t := norm(link))],
        'words': b['word_count'],
        'in_gsc': False,
        'in_sitemap': True,  # Assume all Webflow CMS items are in sitemap
    }
    # Join with GSC metrics
    if page['canon'] in gsc:
        page.update(gsc[page['canon']])
    else:
        page.update({'clicks': 0, 'impressions': 0, 'ctr': 0.0, 'position': 0.0, 'in_gsc': False})
    
    ok.append(page)

print(f"  {len(ok)} total pages (all blogs)")

# --- Link graph analysis ---
blogs = ok  # All are blogs in this dataset
bidx = {p['canon']: i for i, p in enumerate(blogs)}

in_blog, in_static = collections.defaultdict(set), collections.defaultdict(set)
edges = []
out_blog, out_static, out_dead = collections.Counter(), collections.Counter(), collections.Counter()

# There's no live crawl in this pipeline any more (content comes from the
# Webflow export), so we can't HTTP-probe a link target to see if it 404s.
# A previous version of this inferred "broken" from absence in
# data/blogs.json (any /blog/ link not in the published set). Verified
# against the live site and reverted: most of those flagged links were
# actually live -- data/blogs.json's export is not a complete or current
# enough source of truth for "does this page exist" despite its own
# exported_at/total_available metadata claiming full coverage (578/578).
# Rather than keep reporting false positives as fact, this stays empty
# until there's a reliable way to check (a live crawl, or a verified-
# complete Webflow page list) -- see the Broken links / 404s tabs removed
# from build_html.py for the same reason.
known_blog_urls = set(bidx)
broken_targets = []
dead = set()

for p in ok:
    src, is_blog = p['canon'], True  # All are blogs
    seen = set()
    for l in p['outlinks']:
        t = l['to']
        if t == src or t in seen:
            continue
        seen.add(t)
        if t in dead:
            out_dead[src] += 1
        if t in bidx:
            in_blog[t].add(src)
            edges.append({'source': src, 'target': t, 'anchor': l.get('anchor', '')})
            out_blog[src] += 1
        elif t not in dead:
            out_static[src] += 1

# Same detection method as broken_targets above (absence from
# data/blogs.json), same false-positive problem, same reason it's empty
# rather than wrong: a GSC URL not in the published set is not reliable
# evidence the page is actually gone.
dead_ranking = []

print(f"  {len(edges)} blog-to-blog internal links found")

# --- TF-IDF & topic clustering ---
print("Running TF-IDF & topic clustering...")
docs = [(p['title'] + ' ') * 3 + ' '.join(p['h2s']) * 2 + ' ' + p['text'][:8000] for p in blogs]
vec = TfidfVectorizer(stop_words='english', max_features=6000, ngram_range=(1, 2), min_df=3, max_df=0.5)
X = vec.fit_transform(docs)

buckets = [classify(p['title'], p['canon'].split('/blog/')[-1], p['h2s']) for p in blogs]
subs = sorted({(b[0], b[1], b[2]) for b in buckets},
              key=lambda x: (PARENT_ORDER.index(x[0]), x[1]))
sub_id = {(p, s_): i for i, (p, s_, _) in enumerate(subs)}
labels = np.array([sub_id[(b[0], b[1])] for b in buckets])
cname = {i: f"{p} / {s_}" for i, (p, s_, _) in enumerate(subs)}

print(f"  {len(subs)} topic clusters identified")

# --- Unlinked topical neighbours ---
print("Finding unlinked topical neighbours...")
sim = cosine_similarity(X)
np.fill_diagonal(sim, 0)
linked = {(e['source'], e['target']) for e in edges}
pairs, seen = [], set()
for i in range(len(blogs)):
    for j in np.argsort(sim[i])[::-1][:6]:
        if sim[i][j] < 0.18:
            continue
        a, b = blogs[i]['canon'], blogs[j]['canon']
        if (a, b) in linked or (b, a) in linked:
            continue
        pairs.append({'from': a, 'to': b, 'sim': round(float(sim[i][j]), 3),
                      'from_clicks': blogs[i]['clicks'], 'to_clicks': blogs[j]['clicks'],
                      'to_inbound': len(in_blog[b]) + len(in_static[b])})
uniq = []
for p in sorted(pairs, key=lambda x: (-x['from_clicks'], x['to_inbound'])):
    k = tuple(sorted([p['from'], p['to']]))
    if k in seen:
        continue
    seen.add(k)
    uniq.append(p)

print(f"  {len(uniq)} unlinked topic pairs found")

# --- Build nodes ---
nodes = []
for i, p in enumerate(blogs):
    u = p['canon']
    nodes.append({
        'id': u, 'slug': u.split('/blog/')[-1], 'title': p['title'][:110],
        'clicks': p['clicks'], 'impr': p['impressions'],
        'ctr': round(p['ctr'] * 100, 2), 'pos': round(p['position'], 1),
        'words': p['words'], 'h2': len(p['h2s']),
        'inbound': len(in_blog[u]) + len(in_static[u]),
        'inbound_blog': len(in_blog[u]), 'inbound_static': len(in_static[u]),
        'outbound_blog': out_blog[u], 'outbound_static': out_static[u],
        'dead_links': out_dead[u], 'in_gsc': p['in_gsc'], 'in_sitemap': p['in_sitemap'],
        'cluster': int(labels[i]), 'cluster_name': cname[int(labels[i])],
        'parent': buckets[i][0], 'sub': buckets[i][1], 'colour': buckets[i][2],
        'scroll': scroll_by_url.get(u, {}).get('scroll'),
        'scroll_as_of': scroll_by_url.get(u, {}).get('as_of'),
    })

# --- Cluster summaries ---
cl = []
for c in range(len(subs)):
    mem = [n for n in nodes if n['cluster'] == c]
    internal = sum(1 for e in edges if labels[bidx[e['source']]] == c and labels[bidx[e['target']]] == c)
    cl.append({'id': c, 'name': cname[c], 'parent': subs[c][0], 'sub': subs[c][1], 'colour': subs[c][2], 'pages': len(mem),
               'clicks': sum(m['clicks'] for m in mem), 'impr': sum(m['impr'] for m in mem),
               'internal_links': internal, 'density': round(internal / max(len(mem), 1), 2),
               'orphans': sum(1 for m in mem if m['inbound'] == 0)})

# --- Parent summaries ---
parents = []
for pn in PARENT_ORDER:
    mem = [n for n in nodes if n['parent'] == pn]
    if not mem:
        continue
    ids = {n['id'] for n in mem}
    internal = sum(1 for e in edges if e['source'] in ids and e['target'] in ids)
    parents.append({'name': pn, 'colour': PARENT_COLOUR[pn], 'pages': len(mem),
                    'clicks': sum(m['clicks'] for m in mem), 'impr': sum(m['impr'] for m in mem),
                    'internal_links': internal, 'density': round(internal / len(mem), 2),
                    'orphans': sum(1 for m in mem if m['inbound'] == 0)})

# --- Output snapshot ---
out = {'generated': datetime.now().isoformat(), 'parents': parents, 'nodes': nodes, 'edges': edges,
       'clusters': sorted(cl, key=lambda x: (PARENT_ORDER.index(x['parent']), -x['clicks'])), 'pairs': uniq[:250],
       'dead': dead_ranking, 'broken_targets': broken_targets,
       'totals': {'blogs': len(blogs), 'static': 0, 'edges': len(edges),
                  'orphans': sum(1 for n in nodes if n['inbound'] == 0),
                  'orphans_blogonly': sum(1 for n in nodes if n['inbound_blog'] == 0),
                  'clicks': sum(n['clicks'] for n in nodes),
                  'dead_urls': len(dead_ranking), 'broken_links': len(broken_targets),
                  'broken_link_instances': sum(out_dead.values()),
                  'scroll_coverage': sum(1 for n in nodes if n['scroll'] is not None)}}

json.dump(out, open('.cache/snapshot.json', 'w'))

# --- Print summary ---
t = out['totals']
print(f"\nblogs {t['blogs']} | blog-to-blog links {t['edges']}")
print(f"ORPHANS (no inbound from anywhere) {t['orphans']} | no inbound from blogs {t['orphans_blogonly']}")
print(f"\n{'bucket':30} {'pages':>5} {'clicks':>7} {'links':>6} {'dens':>5} {'orph':>5}")
for p in out['parents']:
    print(f"{p['name'].upper():30} {p['pages']:5} {p['clicks']:7} {p['internal_links']:6} {p['density']:5} {p['orphans']:5}")
    for c in out['clusters']:
        if c['parent'] == p['name']:
            print(f"  {c['sub'][:26]:28} {c['pages']:5} {c['clicks']:7} {c['internal_links']:6} {c['density']:5} {c['orphans']:5}")

print(f"\n✓ snapshot.json written to .cache/")
