# -*- coding: utf-8 -*-
"""Whole pipeline in order. Downloads are cached, so a rerun only recomputes."""
import subprocess
import sys

STEPS = [
    ["download.py"],        # DEMs, S1 geometry, S1 + S2 quarterly composites
    ["analysis.py"],        # first pass: footprint (needed by the test), uncalibrated heights
    ["sensitivity.py"],     # injection test → calibration
    ["analysis.py"],        # calibrated heights
    ["plots.py"],
    ["viewer.py"],
    ["notebook.py"],
]

if __name__ == "__main__":
    for step in STEPS:
        print("==>", *step, flush=True)
        subprocess.run([sys.executable, *step], check=True)
