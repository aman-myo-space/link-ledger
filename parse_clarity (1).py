import csv, json, re, io

def parse(path):
    raw = open(path, encoding="utf-8-sig").read()
    rows = list(csv.reader(io.StringIO(raw), delimiter='\t'))
    out, cur = {"sections": {}}, None
    for r in rows:
        r = [c.strip() for c in r]
        if not any(r):
            continue
        if r[0] == "Date range":
            out["range"] = r[1]
        elif r[0] == "Metric":
            cur = r[1]
            out["sections"][cur] = []
        elif cur and r[0] == "" and len(r) > 1 and r[1]:
            out["sections"][cur].append(r[1:])
    return out

d90 = parse("/mnt/user-data/uploads/Clarity_MyOperator_Dashboard_09-21-2026_04_49_PM.csv")
d3 = parse("/mnt/user-data/uploads/Clarity_MyOperator_Dashboard_09-21-2026_04_53_PM.csv")

def g(d, sec, key, i=1):
    for r in d["sections"].get(sec, []):
        if r[0].lower() == key.lower():
            return r[i]
    return None

def pct(d, sec, key):
    for r in d["sections"].get(sec, []):
        if r[0].lower() == key.lower():
            return {"n": r[1], "p": r[2] if len(r) > 2 else ""}
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
    "events": [
        {"k": r[0], "n": r[1], "p": r[2] if len(r) > 2 else ""}
        for r in d90["sections"].get("Smart events", [])
    ],
    "errors": [
        {"k": r[0], "n": r[1], "p": r[2] if len(r) > 2 else ""}
        for r in d90["sections"].get("JavaScript errors", []) if len(r) > 2 and r[1].isdigit()
    ],
    "perf": [[r[0], r[1]] for r in d90["sections"].get("Performance overview", [])],
    "referrers": [[r[0], r[1]] for r in d90["sections"].get("Referrer", [])],
}
json.dump(health, open("/home/claude/health.json", "w"), indent=1)
print(json.dumps({k: health[k] for k in ["scroll", "active", "pps", "sessions", "bots"]}, indent=1))
print("errors", len(health["errors"]), "| events", len(health["events"]), "| perf", health["perf"])
