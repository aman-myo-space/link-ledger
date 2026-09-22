import csv, json, os, glob

def parse(path):
    """Parse Clarity CSV export with quoted fields."""
    with open(path, encoding='utf-8-sig') as f:
        # Clarity's export is tab-delimited despite the .csv extension; the
        # default comma delimiter here made every row a single unsplit
        # field, so "Date range"/"Metric" never matched and every lookup
        # (including scroll depth) silently returned None.
        reader = csv.reader(f, delimiter='\t')
        out = {"sections": {}, "range": "N/A"}
        cur_metric = None
        
        for row in reader:
            # Skip empty rows
            if not row or not any(row):
                continue
            
            # Parse Date range
            if row[0] == "Date range" and len(row) > 1:
                out["range"] = row[1]
            
            # Parse Metric headers
            elif row[0] == "Metric" and len(row) > 1:
                cur_metric = row[1]
                out["sections"][cur_metric] = []
            
            # Parse metric data rows (first column is empty)
            elif row and row[0] == "" and cur_metric and len(row) > 1:
                out["sections"][cur_metric].append(row[1:])
    
    return out

# Find Clarity CSV files
clarity_files = sorted(glob.glob("data/clarity*.csv"), reverse=True)

if not clarity_files:
    print("⚠ No Clarity CSV files found. Using empty health.json.")
    d90, d3 = {"sections": {}, "range": "N/A"}, {"sections": {}, "range": "N/A"}
else:
    d90 = parse(clarity_files[0])
    d3 = parse(clarity_files[1]) if len(clarity_files) > 1 else {"sections": {}, "range": "N/A"}
    print(f"  Loaded: {os.path.basename(clarity_files[0])}")
    if len(clarity_files) > 1:
        print(f"  Loaded: {os.path.basename(clarity_files[1])}")

def g(d, sec, key, i=1):
    """Get metric value from sections."""
    for r in d["sections"].get(sec, []):
        if r and r[0].lower() == key.lower():
            return r[i] if len(r) > i else None
    return None

def pct(d, sec, key):
    """Get metric with percentage."""
    for r in d["sections"].get(sec, []):
        if r and r[0].lower() == key.lower():
            return {"n": r[1] if len(r) > 1 else "-", "p": r[2] if len(r) > 2 else ""}
    return {"n": "-", "p": ""}

health = {
    "ranges": {"long": d90["range"], "short": d3["range"]},
    "scroll": {"long": g(d90, "Scroll depth", "Average"), "short": g(d3, "Scroll depth", "Average")},
    "active": {"long": g(d90, "Active time spent", "Active time"), "short": g(d3, "Active time spent", "Active time")},
    "total_time": {"long": g(d90, "Active time spent", "Total time"), "short": g(d3, "Active time spent", "Total time")},
    "pps": {"long": g(d90, "Pages per session", "Average"), "short": g(d3, "Pages per session", "Average")},
    "sessions": {"long": g(d90, "Sessions", "Total sessions"), "short": g(d3, "Sessions", "Total sessions")},
    "bots": {"long": g(d90, "Sessions", "Bot sessions"), "short": g(d3, "Sessions", "Bot sessions")},
    "friction": [
        {"k": k, "long": pct(d90, "Insights", k), "short": pct(d3, "Insights", k)}
        for k in ["Rage clicks", "Dead click", "Quick back click", "Excessive scrolling"]
    ],
    "events": [],
    "errors": [],
    "perf": [],
    "referrers": [],
}

json.dump(health, open(".cache/health.json", "w"), indent=1)
if clarity_files:
    print(json.dumps({k: health[k] for k in ["scroll", "active", "pps", "sessions", "bots"]}, indent=1))
    print("friction", len(health["friction"]))
else:
    print("✓ Empty health.json written")
