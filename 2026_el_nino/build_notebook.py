# -*- coding: utf-8 -*-
"""Builds analysis.ipynb and executes it, so it opens with all charts in place.

The notebook only SHOWS what run.py computed (out/*.csv, out/*.png): its
numbers are exactly the ones that went onto the maps.
"""
from __future__ import annotations

import os

import nbformat as nbf
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

import config as C

NB = C.ROOT / "analysis.ipynb"


def md(t):
    return new_markdown_cell(t.strip("\n"))


def code(t):
    return new_code_cell(t.strip("\n"))


def table(section, src):
    return code(f"show(cmp_, {section!r}, {src!r})")


def img(name):
    return code(f'Image(filename="out/{name}")')


def cells():
    c = []
    c.append(md("""
# El Niño 2026/27: what to expect, and what the data say

A **strong, possibly record-breaking El Niño** is under way. The project has three parts:

1. **Forecast:** two impact maps, for winter 2026/27 (3–6 months ahead) and summer 2027 (9–12 months ahead).
2. **GDACS analysis:** **equal-size** groups of El Niño, Neutral and La Niña years, compared
   separately for monsoons, hurricanes, typhoons, Saffir-Simpson categories, heavy rain and droughts.
3. **Hazard maps on a long record:** one image per hazard (cyclones, major cyclones, drought,
   monsoon drought, heatwaves), each with three hex maps: theory, El Niño minus the Neutral benchmark
   and La Niña minus the Neutral benchmark. The hazards are classified directly from
   raw measurements: IBTrACS winds since 1980, GPCP rainfall since 1979 and GHCN-CAMS
   temperature since 1950. GDACS covers only 2000/2011/2018 onwards, which is too short for maps.
"""))
    c.append(code("""
import warnings; warnings.filterwarnings("ignore")
import pandas as pd
from IPython.display import Image, display
import config as C, enso
from data import read_index
from analysis import EN_VS_N, LN_VS_N, P_COL
pd.set_option("display.max_colwidth", 70, "display.width", 200)

cmp_ = pd.read_csv("out/comparison.csv")
roni = read_index("roni")

def show(df, section, source):
    sec = [section] if isinstance(section, str) else section
    t = df[df.section.isin(sec) & (df.source == source)]
    cols = ["measure", "period", "n per phase", "El Niño", C.NEUTRAL, "La Niña", EN_VS_N, LN_VS_N, P_COL]
    return (t[cols].set_index("measure").style.format(precision=2, na_rep="—")
            .background_gradient(subset=[EN_VS_N], cmap="RdBu_r", vmin=-100, vmax=100))

print("Latest RONI seasons (NOAA CPC):")
print(roni.tail(6)[["season", "year", "anom"]].to_string(index=False))
"""))
    c.append(md("""
### ENSO state

ENSO years run **June to May**. That window holds the whole Northern Hemisphere hurricane
and typhoon season, the Indian monsoon, the El Niño peak (Dec–Feb) and the Southern Hemisphere
cyclone season. The phase of each year comes from **RONI**, the Relative Oceanic Niño Index
that CPC has used since 2026. The CPC rule applies: at least 5 consecutive seasons beyond
±0.5°C, judged on the OND, NDJ and DJF seasons.
"""))
    c.append(img("0_enso_years.png"))

    # ------------------------------------------------------------------ 1
    c.append(md("""
---
## 1. Forecast: winter 2026/27 and summer 2027

**Winter (+3–6 months)** is the El Niño peak, so the canonical impacts for that season apply.
Confidence is high, because an event this strong almost always produces the signal.

**Summer 2027 (+9–12 months)** is the year after the peak. Of the 8 strong El Niños since 1950,
the following year brought La Niña 5 times, Neutral twice, and once El Niño continued.
The map therefore shows the impacts of a **decaying El Niño and a possible La Niña**, with lower confidence.

The numbers next to the cyclone basins are not typed in by hand. They come from part 2 and from
the composite of seasons that followed a strong El Niño.
"""))
    c.append(img("forecast_maps.png"))
    c.append(code("""
print("The year after a strong El Niño (peak RONI >= 1.5):")
display(enso.after_strong_el_nino(enso.enso_years()))
print("Cyclone seasons in the year after a strong El Niño vs the 1980–2025 mean (IBTrACS):")
display(pd.read_csv("out/after_strong_el_nino.csv"))
"""))

    # ------------------------------------------------------------------ 2
    c.append(md("""
---
## 2. GDACS analysis: El Niño vs normal circulation vs La Niña

**Rule:** three groups with **the same number of years** (n = size of the smallest phase within
the window in which GDACS has that event type). From the larger phases we take the clearest years:
El Niño and La Niña with the largest anomaly, Neutral with the smallest.
Each bar is the group mean; the dots are individual years.

`p` is a two-sided permutation test of El Niño vs La Niña over **all** years in the window.
A star ✱ marks p < 0.05.

| GDACS type | continuous since | notes |
|---|---|---|
| cyclones (TC) | Jul 2011, so the first full year is 2012/13 | 14 seasons, **n = 3 per phase** |
| floods (FL) | 2000 | three catalogues: DFO (to 2015), JRC (2016–18, fragmentary), GloFAS (from 2019, ~4× more events). 2016–18 are dropped; each phase gets the same number of DFO and GloFAS years; regions are counted as **% of all floods** in that year |
| droughts (DR) | Jun 2018 | only 8 years, one of them Neutral, so the comparison uses **months** with an active drought (ENSO phase 3 months earlier) |
"""))
    for title, f, sec, src in [
        ("### 2.1 Monsoons", "1_monsoons.png", "Monsoons", "GDACS"),
        ("### 2.2 Hurricanes", "2_hurricanes.png", "Hurricanes", "GDACS"),
        ("### 2.3 Typhoons and other cyclones", "3_typhoons_cyclones.png", ["Typhoons", "Cyclones"], "GDACS"),
        ("### 2.4 Meteorological categories (Saffir-Simpson)", "4_categories.png",
         "Categories (Saffir-Simpson)", "GDACS"),
    ]:
        c.append(md(title))
        c.append(img(f))
        c.append(table(sec, src))
    c.append(img("4b_category_mix_gdacs.png"))
    c.append(md("### 2.5 Heavy rain and floods"))
    c.append(img("5_heavy_rain.png"))
    c.append(table("Heavy rain", "GDACS"))
    c.append(md("### 2.6 Droughts"))
    c.append(img("6_droughts.png"))
    c.append(table("Droughts", "GDACS"))
    c.append(md("""
### 2.7 Long-record check (IBTrACS 1980–2025, n = 13 per phase)

GDACS gives only 3 cyclone seasons per phase, so the same test is repeated on 46 IBTrACS seasons,
with the same basin definition and the same wind scale (1-minute).
**ACE**, the accumulated cyclone energy of a season, is added as well.
"""))
    c.append(img("7_ibtracs_hurricanes.png"))
    c.append(img("8_ibtracs_typhoons_cyclones.png"))
    c.append(img("9_ibtracs_categories.png"))
    c.append(img("9b_category_mix_ibtracs.png"))
    c.append(table(["Hurricanes", "Typhoons", "Cyclones", "Categories (Saffir-Simpson)"], "IBTrACS"))

    # ------------------------------------------------------------------ 3
    c.append(md("""
---
## 3. Hazard maps on a long record

One image per hazard, three hex maps each: theory, El Niño minus Neutral, La Niña minus Neutral.
The Neutral benchmark is the zero line of maps 2–3, not a map of its own.
**Red = more of the hazard, green = less.** Hexagons are translucent so the continents show through.
A bold number with * marks a hexagon that differs from the Neutral benchmark at p < 0.10
(Welch t-test over the years of the two groups). Hazards are classified from raw measurements:

| hazard | data | classification |
|---|---|---|
| tropical cyclones | IBTrACS 6-hourly wind, 1980– | days with wind ≥ 34 kt in the hexagon |
| major cyclones | IBTrACS 6-hourly wind, 1980– | days with wind ≥ 96 kt (cat. 3–5) |
| drought | GPCP v2.3 monthly rain, 1979– | months with 6-month SPI ≤ −1.0 (non-parametric SPI) |
| monsoon drought | GPCP v2.3, monsoon domains | local-summer rainfall deficit, % below normal |
| heatwaves | GHCN-CAMS 2 m temperature, 1950– | months above the 90th percentile of the **detrended** anomaly |
"""))
    for f in ["hex_1_cyclones.png", "hex_2_major.png", "hex_3_drought.png", "hex_4_monsoon.png",
              "hex_5_heat.png"]:
        c.append(img(f))

    c.append(md("""
---
## Findings in numbers

The measures below have p < 0.1 or an El Niño vs Neutral change of at least 25%,
sorted by the strength of the signal.
"""))
    c.append(code("""
t = cmp_.copy()
t["|Δ|"] = t[EN_VS_N].abs()
t = t[(t[P_COL] < 0.1) | (t["|Δ|"] >= 25)]
t[["section", "measure", "source", EN_VS_N, LN_VS_N, P_COL]].sort_values(P_COL).round(2)
"""))
    c.append(md("""
### Limitations

* **Few years in GDACS.** 3 cyclone seasons per phase means the direction matters more than the
  exact percentages. IBTrACS (13 per phase) and the long-record hex maps serve as the check.
* **A GDACS event count is not a casualty count.** The alert level depends on exposed population,
  so the same wind over the ocean and over Manila gets a different alert colour.
* **Peru and Ecuador.** The data show fewer floods in El Niño years. But the great "coastal El Niño"
  floods of 2017 fall in the dropped catalogue transition (2016–18), and GDACS does not cover 1997/98.
* **The +12-month outlook** is a scenario, not a certainty. It depends on how fast the Pacific
  swings to La Niña.
* **Heatwaves** are monthly hot extremes (detrended), not daily heatwave days. They show where
  El Niño shifts the odds of a hot month.
"""))
    return c


def main():
    nb = new_notebook(cells=cells(), metadata={"kernelspec": {"name": "python3",
                                                              "display_name": "Python 3",
                                                              "language": "python"}})
    cwd = os.getcwd()
    os.chdir(C.ROOT)
    try:
        NotebookClient(nb, timeout=600, kernel_name="python3",
                       resources={"metadata": {"path": str(C.ROOT)}}).execute()
    finally:
        os.chdir(cwd)
    nbf.write(nb, NB)
    print(f"saved {NB.name}")


if __name__ == "__main__":
    main()
