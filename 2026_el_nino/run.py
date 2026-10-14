# -*- coding: utf-8 -*-
"""The whole pipeline: data -> analysis -> charts -> maps -> notebook.

    python run.py              # from cache (downloads only what is missing)
    python run.py --refresh    # refresh the current GDACS year, ENSO indices and gridded data
"""
from __future__ import annotations

import sys

import analysis
import build_notebook
import config as C
import data
import forecast
import hexmaps
import plots

# (sections, source, title, output file)
SECTIONS = [
    (["Monsoons"], "GDACS", "1 · Monsoons — floods in the monsoon season (% of all GDACS floods)", "1_monsoons"),
    (["Hurricanes"], "GDACS", "2 · Hurricanes (Atlantic + East Pacific) — GDACS", "2_hurricanes"),
    (["Typhoons", "Cyclones"], "GDACS", "3 · Typhoons (West Pacific) and other cyclones — GDACS", "3_typhoons_cyclones"),
    (["Categories (Saffir-Simpson)"], "GDACS", "4 · Meteorological categories (Saffir-Simpson) — GDACS", "4_categories"),
    (["Heavy rain"], "GDACS", "5 · Heavy rain and floods — GDACS", "5_heavy_rain"),
    (["Droughts"], "GDACS", "6 · Droughts — GDACS (months with an active drought)", "6_droughts"),
    (["Hurricanes"], "IBTrACS", "Long-record check: hurricanes — IBTrACS 1980–2025", "7_ibtracs_hurricanes"),
    (["Typhoons", "Cyclones"], "IBTrACS", "Long-record check: typhoons and cyclones — IBTrACS 1980–2025", "8_ibtracs_typhoons_cyclones"),
    (["Categories (Saffir-Simpson)"], "IBTrACS", "Long-record check: categories — IBTrACS 1980–2025", "9_ibtracs_categories"),
]


def main(refresh=False):
    print("=== data")
    data.main(refresh=refresh)
    print("=== analysis")
    years, g, ib, tab, cmp_, dm = analysis.run()
    yearly = tab.copy()
    yearly.columns = [f"{s} | {l} | {src}" for s, l, src in tab.columns]
    print("=== charts")
    plots.enso_timeline(years, C.OUT / "0_enso_years.png")
    for secs, src, title, name in SECTIONS:
        rows = cmp_[cmp_.section.isin(secs) & (cmp_.source == src)]
        plots.section_figure(yearly, rows, title, C.OUT / f"{name}.png",
                             ncols=5 if secs[0].startswith("Categories") else 4)
    plots.categories_figure(g[g.type == "TC"], years, "GDACS", C.OUT / "4b_category_mix_gdacs.png")
    plots.categories_figure(ib, years, "IBTrACS", C.OUT / "9b_category_mix_ibtracs.png")
    print("=== forecast maps")
    forecast.make(cmp_, ib, years, C.OUT / "forecast_maps.png")
    print("=== hex maps")
    hexmaps.main(years)
    print("=== notebook")
    build_notebook.main()
    print("done:", sorted(p.name for p in C.OUT.glob("*.png")))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
