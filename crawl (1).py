import csv, json, re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; myoperator-content-audit)"}
BODY_SELECTORS = [".blog-content", "div.w-richtext", "main"]
SITEMAP = "https://myoperator.com/sitemap.xml"

def norm(u):
    u = urldefrag(u)[0]
    p = urlparse(u)
    if p.netloc.replace("www.", "") != "myoperator.com":
        return None
    return "https://myoperator.com" + (p.path.rstrip("/") or "/")

sm = requests.get(SITEMAP, headers=UA, timeout=30).text
sitemap_urls = {n for u in re.findall(r"<loc>(.*?)</loc>", sm) if (n := norm(u))}

# Several GSC rows can normalise to one URL (query-string variants), so
# aggregate rather than overwrite: a last-write-wins dict silently drops traffic.
agg = {}
for r in csv.DictReader(open("data/Pages.csv")):
    n = norm(r["Top pages"].strip())
    if not n:
        continue
    c, i = int(r["Clicks"]), int(r["Impressions"])
    a = agg.setdefault(n, {"clicks": 0, "impressions": 0, "pos_wt": 0.0})
    a["clicks"] += c
    a["impressions"] += i
    a["pos_wt"] += float(r["Position"]) * max(i, 1)
gsc = {n: {"clicks": a["clicks"], "impressions": a["impressions"],
           "ctr": (a["clicks"] / a["impressions"]) if a["impressions"] else 0.0,
           "position": round(a["pos_wt"] / max(a["impressions"], 1), 2)}
       for n, a in agg.items()}

targets = sorted(sitemap_urls | set(gsc))

def fetch(u):
    base = {"canon": u, **gsc.get(u, {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}),
            "in_sitemap": u in sitemap_urls, "in_gsc": u in gsc}
    try:
        r = requests.get(u, headers=UA, timeout=25)
        if r.status_code != 200:
            return {**base, "error": f"http {r.status_code}"}
        s = BeautifulSoup(r.text, "lxml")
        body = None
        for sel in BODY_SELECTORS:
            els = [e for e in s.select(sel) if len(e.get_text(strip=True)) > 200]
            if els:
                body = max(els, key=lambda e: len(e.get_text()))
                break
        if body is None:
            body = s.find("body")
        text = body.get_text(" ", strip=True)
        links, ext = [], 0
        for a in body.find_all("a", href=True):
            n = norm(a["href"])
            if n:
                links.append({"to": n, "anchor": a.get_text(strip=True)[:120]})
            elif a["href"].startswith("http"):
                ext += 1
        t = s.find("title")
        return {**base, "title": t.get_text(strip=True) if t else "",
                "words": len(text.split()), "h2s": [h.get_text(strip=True) for h in body.find_all("h2")],
                "outlinks": links, "external_out": ext, "text": text[:60000]}
    except Exception as e:
        return {**base, "error": str(e)[:120]}

with ThreadPoolExecutor(max_workers=14) as ex:
    out = list(ex.map(fetch, targets))

# Second pass: probe every link target that was never in the crawl universe.
# Without this, links to deleted pages vanish silently instead of being reported.
known = set(targets)
extra = sorted({l["to"] for p in out if "outlinks" in p for l in p["outlinks"]} - known)

def probe(u):
    try:
        r = requests.head(u, headers=UA, timeout=15, allow_redirects=True)
        if r.status_code >= 400:
            r = requests.get(u, headers=UA, timeout=20)
        return {"canon": u, "status": r.status_code,
                "final": norm(r.url) or r.url, "probed_only": True}
    except Exception as e:
        return {"canon": u, "status": 0, "error": str(e)[:80], "probed_only": True}

probes = []
if extra:
    with ThreadPoolExecutor(max_workers=14) as ex:
        probes = list(ex.map(probe, extra))
json.dump(probes, open(".cache/probes.json", "w"))
bad = [p for p in probes if p["status"] != 200]
print(f"probed {len(probes)} off-sitemap link targets | broken {len(bad)}")

json.dump(out, open(".cache/pages.json", "w"))
ok = [p for p in out if "error" not in p]
print(f"universe {len(targets)} (sitemap {len(sitemap_urls)}, gsc-only {len(set(gsc)-sitemap_urls)})")
print(f"fetched {len(ok)} | errors {len(out)-len(ok)}")
print(f"blogs {sum(1 for p in ok if '/blog/' in p['canon'])} | static {sum(1 for p in ok if '/blog/' not in p['canon'])}")
