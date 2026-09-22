"""Pull live Clarity data via the Data Export API and append it to
clarity/YYYY-MM-DD.json. Intended to run on a schedule (see
.github/workflows/clarity-pull.yml), up to 3x/day, well under the API's
10-requests-per-project-per-day cap.

Token comes from the CLARITY_TOKEN environment variable, never from a file.
"""
import datetime, json, os, sys
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "clarity")
os.makedirs(OUT_DIR, exist_ok=True)

TOKEN = os.environ.get("CLARITY_TOKEN")
if not TOKEN:
    print("ERROR: CLARITY_TOKEN environment variable not set. Not calling the API.")
    sys.exit(1)

URL = "https://www.clarity.ms/export-data/api/v1/project-live-insights"
PARAMS = {"numOfDays": 3, "dimension1": "URL"}
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

try:
    resp = requests.get(URL, headers=HEADERS, params=PARAMS, timeout=30)
except requests.exceptions.RequestException as e:
    print(f"ERROR: Clarity API request failed: {e}")
    sys.exit(1)

if resp.status_code == 429:
    print("ERROR: Clarity API rate limit hit (10 requests/project/day). Skipping this pull.")
    sys.exit(1)
if resp.status_code != 200:
    print(f"ERROR: Clarity API returned HTTP {resp.status_code}: {resp.text[:300]}")
    sys.exit(1)

data = resp.json()

# --- First-run verification (CLAUDE.md is explicit this must be checked,
# not assumed): does breaking down by URL actually return scroll depth per
# page? The public docs list dimensions and metrics separately with no
# worked URL example. This parsing is a best guess at Clarity's documented
# response shape (a list of {"metricName", "information": [...]} entries) --
# treat the printed output below as the ground truth on the first real run,
# and fix this block to match if the shape differs.
has_per_url_scroll = False
sample_urls = []
if isinstance(data, list):
    for row in data:
        if isinstance(row, dict) and row.get("metricName", "").lower() == "scrolldepth":
            for entry in row.get("information", []):
                if isinstance(entry, dict) and entry.get("URL"):
                    has_per_url_scroll = True
                    sample_urls.append(entry["URL"])
    print(f"response has {len(data)} metric block(s): {[r.get('metricName') for r in data if isinstance(r, dict)]}")
else:
    print("WARNING: response is not a list of metric blocks -- inspect the raw payload below.")

print(f"per-URL scroll depth present: {has_per_url_scroll}")
if sample_urls:
    print(f"sample URLs with scroll data ({len(sample_urls)} total): {sample_urls[:3]}")
if not has_per_url_scroll:
    print("Per CLAUDE.md: Clarity leg stays at site-aggregate level. Do not build a")
    print("per-blog Scroll tab until this actually returns URL-level data.")

today = datetime.date.today().isoformat()
out_path = os.path.join(OUT_DIR, f"{today}.json")
existing = json.load(open(out_path)) if os.path.exists(out_path) else []
existing.append({
    "pulled_at": datetime.datetime.utcnow().isoformat() + "Z",
    "has_per_url_scroll": has_per_url_scroll,
    "data": data,
})
json.dump(existing, open(out_path, "w"), indent=1)
print(f"appended pull to {out_path} ({len(existing)} pull(s) today)")
