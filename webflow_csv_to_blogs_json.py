"""Convert a raw Webflow CMS "Blogs" collection CSV export into the
data/blogs.json schema analyze.py expects.

Merges into the existing data/blogs.json rather than replacing it outright:
any blog present in the old file but missing from the new export is KEPT,
not deleted, because a smaller row count in a fresh export is far more
likely to be an incomplete/filtered export (a saved Webflow CMS view
filter, a partial pull) than 128 blogs being unpublished in one sitting --
see the run that produced this script for the actual verification (none of
the missing blogs matched known lead-generating pages, and their
last_published dates weren't old superseded content, they were as recent
as the ones that stayed). Deleting them on a guess risks manufacturing 128
false "newly orphaned" blogs. Prints exactly what changed either way so
this is never a silent decision.
"""
import csv, json, os, re, sys
from html import unescape

ROOT = os.path.dirname(os.path.abspath(__file__))

def extract_h2s(html):
    return [re.sub(r"<[^>]+>", "", unescape(m)).strip()
            for m in re.findall(r"<h2[^>]*>(.*?)</h2>", html or "", re.S)]

def extract_links(html):
    return [href for href in re.findall(r'href="([^"]+)"', html or "")
            if "/blog/" in href]

def word_count(html):
    text = re.sub(r"<[^>]+>", " ", html or "")
    return len(unescape(text).split())

def parse_row(row):
    slug = row["Blog Slug"].strip()
    return {
        "id": row["Item ID"],
        "title": row["Blog Tittle"].strip(),
        "slug": slug,
        "url": f"https://myoperator.com/blog/{slug}",
        "h2_headings": extract_h2s(row["Content"]),
        "internal_links": extract_links(row["Content"]),
        "word_count": word_count(row["Content"]),
        "last_published": row.get("Published On") or row.get("Updated On") or "",
        "is_draft": row.get("Draft", "").strip().lower() == "true",
        "is_archived": row.get("Archived", "").strip().lower() == "true",
    }

def main(csv_path, out_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    new_blogs = {r["Blog Slug"].strip(): parse_row(r) for r in rows if r.get("Blog Slug", "").strip()}

    old_path = os.path.join(ROOT, "data", "blogs.json")
    old_blogs = {}
    if os.path.exists(old_path):
        old_blogs = {b["slug"]: b for b in json.load(open(old_path))["blogs"]}

    new_slugs, old_slugs = set(new_blogs), set(old_blogs)
    added = new_slugs - old_slugs
    updated = new_slugs & old_slugs
    kept_from_old = old_slugs - new_slugs

    merged = dict(old_blogs)
    merged.update(new_blogs)

    blogs = list(merged.values())
    import datetime
    out = {
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "total_available": len(blogs),
        "fetched_in_this_batch": len(new_blogs),
        "published_blogs": sum(1 for b in blogs if not b["is_draft"] and not b["is_archived"]),
        "source": "Webflow CSV export (merged with prior data/blogs.json)",
        "blogs": blogs,
    }
    json.dump(out, open(out_path, "w"), indent=1)

    print(f"new export: {len(new_blogs)} rows")
    print(f"added (genuinely new): {len(added)}")
    print(f"updated (existing, refreshed content/links): {len(updated)}")
    print(f"kept from old export untouched (missing from new file): {len(kept_from_old)}")
    print(f"total blogs after merge: {len(blogs)}")
    if kept_from_old:
        print("\nSlugs kept from the old export (verify these weren't actually unpublished):")
        for s in sorted(kept_from_old):
            print(" ", s)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python3 webflow_csv_to_blogs_json.py <raw_webflow_csv> <out_json>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
