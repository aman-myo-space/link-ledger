"""Run the full Link Ledger pipeline in order: crawl, analyze, parse Clarity, build dashboard."""
import runpy

STEPS = ["crawl", "analyze", "parse_clarity", "build_html"]

for step in STEPS:
    print(f"\n=== {step}.py ===")
    runpy.run_module(step, run_name="__main__")
