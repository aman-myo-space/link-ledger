#!/usr/bin/env python3
"""
Link Ledger pipeline: Webflow CSV export → analysis → Clarity metrics → HTML dashboard

Workflow:
1. data/blogs.json (from Webflow CSV export, already in repo)
2. data/Pages.csv (from Google Search Console)
3. data/clarity-90d.csv & data/clarity-3d.csv (from Microsoft Clarity)

Output: site/index.html (GitHub Pages dashboard)

Note: crawl.py and webflow_pull.py are deprecated. Use 'link-ledger' scheduled task
to export blogs.json quarterly from Webflow CMS.
"""

import subprocess, sys, os

print("=" * 60)
print("Link Ledger: Blog Audit Pipeline")
print("=" * 60)

# Ensure cache dir exists
os.makedirs(".cache", exist_ok=True)

# Step 1: Analyze blogs + GSC data
print("\n[1/3] Analyzing blogs, internal links, and topic clusters...")
result = subprocess.run([sys.executable, "analyze.py"], cwd=".")
if result.returncode != 0:
    print("❌ analyze.py failed")
    sys.exit(1)

# Step 2: Parse Clarity reader behaviour
print("\n[2/3] Parsing Microsoft Clarity scroll depth & friction data...")
result = subprocess.run([sys.executable, "parse_clarity.py"], cwd=".")
if result.returncode != 0:
    print("❌ parse_clarity.py failed")
    sys.exit(1)

# Step 3: Build HTML dashboard
print("\n[3/3] Building HTML dashboard...")
result = subprocess.run([sys.executable, "build_html.py"], cwd=".")
if result.returncode != 0:
    print("❌ build_html.py failed")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ Pipeline complete!")
print("  Dashboard: site/index.html")
print("  Snapshot:  .cache/snapshot.json")
print("  Health:    .cache/health.json")
print("=" * 60)
