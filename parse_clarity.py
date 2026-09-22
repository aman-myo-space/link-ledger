import csv, json, os, glob

def parse(path):
    """Parse Clarity CSV export with quoted fields and nested structure."""
    data = {}
    
    with open(path, encoding='utf-8-sig') as f:
        reader = csv.reader(f)
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
            "long": {"n": get_metric(d90, "Insights", "Rage clicks"), "p": None},
            "short": {"n": get_metric(d3, "Insights", "Rage clicks") if d3 else None, "p": None}
        },
        {
            "k": "Dead click",
            "long": {"n": get_metric(d90, "Insights", "Dead click"), "p": None},
            "short": {"n": get_metric(d3, "Insights", "Dead click") if d3 else None, "p": None}
        },
        {
            "k": "Quick back click",
            "long": {"n": get_metric(d90, "Insights", "Quick back click"), "p": None},
            "short": {"n": get_metric(d3, "Insights", "Quick back click") if d3 else None, "p": None}
        },
        {
            "k": "Excessive scrolling",
            "long": {"n": get_metric(d90, "Insights", "Excessive scrolling"), "p": None},
            "short": {"n": get_metric(d3, "Insights", "Excessive scrolling") if d3 else None, "p": None}
        }
    ],
    "events": [],
    "errors": [],
    "perf": [],
    "referrers": [],
}

json.dump(health, open(".cache/health.json", "w"), indent=1)

if clarity_files and d90:
    print(f"✓ Scroll depth: {health['scroll']['long']}%")
    print(f"✓ Sessions: {health['sessions']['long']}")
    print(f"✓ Pages per session: {health['pps']['long']}")
else:
    print("✓ Empty health.json written")
