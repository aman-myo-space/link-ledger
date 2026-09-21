#!/usr/bin/env python3
import subprocess
import sys
import os

os.makedirs(".cache", exist_ok=True)
os.makedirs("snapshots", exist_ok=True)
os.makedirs("site", exist_ok=True)

print("=== crawl.py ===")
result = subprocess.run([sys.executable, "crawl.py"], cwd=".")
if result.returncode != 0:
    print("Warning: crawl failed (expected if no network access)")

print("\n=== analyze.py ===")
result = subprocess.run([sys.executable, "analyze.py"], cwd=".")
if result.returncode != 0:
    print("Error: analyze failed")
    sys.exit(1)

print("\n=== parse_clarity.py ===")
result = subprocess.run([sys.executable, "parse_clarity.py"], cwd=".")
if result.returncode != 0:
    print("Error: parse_clarity failed")
    sys.exit(1)

print("\n=== build_html.py ===")
result = subprocess.run([sys.executable, "build_html.py"], cwd=".")
if result.returncode != 0:
    print("Error: build_html failed")
    sys.exit(1)

print("\n✓ Pipeline complete")
