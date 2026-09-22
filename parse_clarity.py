import csv, json, os, glob

def parse(path):
    """Parse Clarity CSV export with quoted fields and nested structure."""
    data = {}
    
    with open(path, encoding='utf-8-sig') as f:
        # Clarity's export is tab-delimited despite the .csv extension.
        # Without delimiter='\t' every row parses as one unsplit field,
        # "Project name"/"Date range"/"Metric" never match, and every
        # value in health.json comes back None -> "no data" on the
        # dashboard. This exact bug has been reintroduced twice already
        # by full-file rewrites of this parser; see the assertion below.
        reader = csv.reader(f, delimiter='\t')
        cur_metric = None
        
        for row in reader:
            if not row or not any(c.strip() for c in row):
                continue
            
            # Parse metadata
            if row[0] == "Project name":
                data["project"] = row[1] if len(row) > 1 else "N/A"
            elif row[0] == "Date range":
                data["range"] = row[1] if len(row) > 1 else "N/A"
            
            # Parse metric headers
            elif row[0] == "Metric" and len(row) > 1:
                cur_metric = row[1]
                data[cur_metric] = []
            
            # Parse metric rows (first column empty, data in following columns)
            elif cur_metric and row[0] == "" and len(row) > 1:
                data[cur_metric].append({
                    "name": row[1],
                    "value": row[2] if len(row) > 2 else None,
                    "pct": row[3] if len(row) > 3 else None
                })
    
    return data

# Find Clarity CSV files
clarity_files = sorted(glob.glob("data/clarity*.csv"), reverse=True)

if not clarity_files:
    print("⚠ No Clarity CSV files found. Using empty health.json.")
    d90, d3 = {}, {}
else:
    d90 = parse(clarity_files[0])
    d3 = parse(clarity_files[1]) if len(clarity_files) > 1 else {}
    print(f"  Loaded: {os.path.basename(clarity_files[0])}")
    if len(clarity_files) > 1:
        print(f"  Loaded: {os.path.basename(clarity_files[1])}")

def get_metric(data, metric_name, field_name):
    """Get metric value by metric name and field name."""
    if metric_name not in data:
        return None
    for item in data[metric_name]:
        if item["name"] == field_name:
            return item["value"]
    return None

def get_pct(data, metric_name, field_name):
    """Get metric row's pct field (e.g. "5.23%" for an Insights row like
    Dead click). parse() already captures this into every row -- it was
    just never read back out, so friction rows always showed "p": None."""
    if metric_name not in data:
        return None
    for item in data[metric_name]:
        if item["name"] == field_name:
            return item.get("pct")
    return None

# Build health output
health = {
    "ranges": {
        "long": d90.get("range", "N/A"),
        "short": d3.get("range", "N/A") if d3 else "N/A"
    },
    "scroll": {
        "long": get_metric(d90, "Scroll depth", "Average"),
        "short": get_metric(d3, "Scroll depth", "Average") if d3 else None
    },
    "active": {
        "long": get_metric(d90, "Active time spent", "Active time"),
        "short": get_metric(d3, "Active time spent", "Active time") if d3 else None
    },
    "total_time": {
        "long": get_metric(d90, "Active time spent", "Total time"),
        "short": get_metric(d3, "Active time spent", "Total time") if d3 else None
    },
    "pps": {
        "long": get_metric(d90, "Pages per session", "Average"),
        "short": get_metric(d3, "Pages per session", "Average") if d3 else None
    },
    "sessions": {
        "long": get_metric(d90, "Sessions", "Total sessions"),
        "short": get_metric(d3, "Sessions", "Total sessions") if d3 else None
    },
    "bots": {
        "long": get_metric(d90, "Sessions", "Bot sessions"),
        "short": get_metric(d3, "Sessions", "Bot sessions") if d3 else None
    },
    "friction": [
        {
            "k": "Rage clicks",
            "long": {"n": get_metric(d90, "Insights", "Rage clicks"), "p": get_pct(d90, "Insights", "Rage clicks")},
            "short": {"n": get_metric(d3, "Insights", "Rage clicks") if d3 else None, "p": get_pct(d3, "Insights", "Rage clicks") if d3 else None}
        },
        {
            "k": "Dead click",
            "long": {"n": get_metric(d90, "Insights", "Dead click"), "p": get_pct(d90, "Insights", "Dead click")},
            "short": {"n": get_metric(d3, "Insights", "Dead click") if d3 else None, "p": get_pct(d3, "Insights", "Dead click") if d3 else None}
        },
        {
            "k": "Quick back click",
            "long": {"n": get_metric(d90, "Insights", "Quick back click"), "p": get_pct(d90, "Insights", "Quick back click")},
            "short": {"n": get_metric(d3, "Insights", "Quick back click") if d3 else None, "p": get_pct(d3, "Insights", "Quick back click") if d3 else None}
        },
        {
            "k": "Excessive scrolling",
            "long": {"n": get_metric(d90, "Insights", "Excessive scrolling"), "p": get_pct(d90, "Insights", "Excessive scrolling")},
            "short": {"n": get_metric(d3, "Insights", "Excessive scrolling") if d3 else None, "p": get_pct(d3, "Insights", "Excessive scrolling") if d3 else None}
        }
    ],
    "events": [],
    "errors": [],
    "perf": [],
    "referrers": [],
}

if clarity_files:
    # Files were found on disk, so every metric below should be a real
    # value, not None — including the case where the parser silently
    # extracted *nothing* (d90 == {}), which is just as broken as
    # extracting Nones and must not be mistaken for the legitimate
    # "no files found" case below. This is almost always a delimiter
    # bug: Clarity's export is tab-delimited despite the .csv extension.
    # Stop here instead of writing (or worse, reporting success on) a
    # broken health.json.
    critical = [health["scroll"]["long"], health["sessions"]["long"], health["pps"]["long"]]
    if not d90 or all(v is None for v in critical):
        print("✗ ERROR: Clarity CSV(s) found but every metric parsed as None.")
        print(f"  Checked: {os.path.basename(clarity_files[0])}")
        print("  parse() must use csv.reader(f, delimiter='\\t'), not the")
        print("  comma default, or every row parses as one unsplit field.")
        raise SystemExit(1)
    print(f"✓ Scroll depth: {health['scroll']['long']}%")
    print(f"✓ Sessions: {health['sessions']['long']}")
    print(f"✓ Pages per session: {health['pps']['long']}")
else:
    print("✓ Empty health.json written")

json.dump(health, open(".cache/health.json", "w"), indent=1)
