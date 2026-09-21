"""Run the full Link Ledger pipeline in order: crawl, analyze, parse Clarity, build dashboard.

Each step is independent enough to run on its own, but the pipeline is
sequential: analyze.py needs crawl.py's output, build_html.py needs both
analyze.py's and parse_clarity.py's output. A failed step's own error
message says why; this runner just stops there rather than continuing
on top of missing input.
"""
import runpy
import sys

STEPS = ["crawl", "analyze", "parse_clarity", "build_html"]

for step in STEPS:
    print(f"\n=== {step}.py ===")
    try:
        runpy.run_module(step, run_name="__main__")
    except SystemExit as e:
        if e.code not in (None, 0):
            print(f"\nPipeline stopped: {step}.py failed (exit {e.code}).")
            sys.exit(e.code)
