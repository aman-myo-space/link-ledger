import json, csv, collections, numpy as np
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from buckets import classify, PARENT_COLOUR, PARENT_ORDER

# --- Load blogs from Webflow CSV export (via blogs.json) ---
print("Loading blogs from data/blogs.json...")
blogs_data = json.load(open("data/blogs.json"))
blogs_list = blogs_data["blogs"]
print(f"  {len(blogs_list)} published blogs loaded")

# --- Load GSC data (clicks, impressions, CTR, position) ---
print("Loading GSC metrics from data/Pages.csv...")
gsc = {}
with open("data/Pages.csv", newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')  # Tab-delimited
    for row in reader:
        url = row.get('Top pages', '').strip()
        if url and '/blog/' in url:
            ctr_str = row.get('CTR', '0').rstrip('%').strip()
            gsc[url] = {
                'clicks': int(row.get('Clicks', 0) or 0),
                'impressions': int(row.get('Impressions', 0) or 0),
                'ctr': float(ctr_str or 0) / 100,
                'position': float(row.get('Position', 0) or 0),
                'in_gsc': True,
            }
print(f"  {len(gsc)} GSC URLs matched")

# --- Convert blogs.json to pages dict (mimic crawled format) ---
ok = []
for b in blogs_list:
    page = {
        'canon': b['url'],
        'title': b['title'],
        'h2s': b['h2_headings'],
        'text': ' '.join(b['h2_headings']),  # Minimal text for TF-IDF
        'outlinks': [{'to': link, 'anchor': ''} for link in b['internal_links']],  # No anchors in CSV export
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

dead = set()  # No dead URLs yet (no probes)

for p in ok:
    src, is_blog = p['canon'], True  # All are blogs
    seen = set()
    for l in p['outlinks']:
        t = l['to']
        # Convert path to full URL if needed
        if t.startswith('/'):
            t = f"https://myoperator.com{t}"
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
       'dead': [], 'broken_targets': [],
       'totals': {'blogs': len(blogs), 'static': 0, 'edges': len(edges),
                  'orphans': sum(1 for n in nodes if n['inbound'] == 0),
                  'orphans_blogonly': sum(1 for n in nodes if n['inbound_blog'] == 0),
                  'clicks': sum(n['clicks'] for n in nodes),
                  'dead_urls': 0, 'broken_links': 0,
                  'broken_link_instances': 0}}

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
