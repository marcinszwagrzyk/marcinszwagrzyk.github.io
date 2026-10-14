# El Niño 2026/27: impacts forecast and GDACS evidence

A **strong, possibly record-breaking El Niño** is under way (NOAA CPC El Niño Advisory, Oct 2026:
RONI JAS 2026 = +1.69, ONI +2.16; IRI: El Niño 100% likely through Feb–Apr 2027, Niño3.4 likely above +2.5°C).
This project asks what that means for the next 12 months, and checks the textbook answer against data.

Three parts:

1. **Forecast:** two maps side by side, winter 2026/27 (3–6 months ahead) and summer 2027 (9–12 months ahead).
2. **GDACS phase comparison:** equal-size groups of El Niño, Neutral and La Niña years, compared for
   monsoons, hurricanes, typhoons, Saffir-Simpson categories, heavy rain and droughts.
   IBTrACS (1980–2025) provides a long-record check for the cyclones.
3. **Hazard hex maps on a long record:** one image per hazard (cyclones, major cyclones, drought,
   monsoon drought, heatwaves), each with three stacked maps:
   - theory,
   - El Niño minus the Neutral benchmark,
   - La Niña minus the Neutral benchmark.

   Red means more of the hazard and green means less. The hazards are classified from raw
   measurements: IBTrACS winds, GPCP rainfall and GHCN-CAMS temperature.

Everything is in **`analysis.ipynb`**, an executed notebook that opens with all figures.

## Run

```bash
python run.py              # download what is missing, analyse, draw, build the notebook
python run.py --refresh    # also refresh the current GDACS year, ENSO indices and gridded data
```

Interpreter used: `C:\Users\marci\anaconda3\python.exe` (Python 3.13).
Requires `pandas`, `numpy`, `scipy`, `geopandas`, `shapely`, `matplotlib`, `h5py`, `requests`,
`nbformat` and `nbclient`; cartopy is not needed. The first run downloads about 350 MB into `data/`
(not in git).

## Data

| source | what | period |
|---|---|---|
| [NOAA CPC RONI / ONI](https://www.cpc.ncep.noaa.gov/data/indices/) | ENSO phase of every year | 1950– |
| [GDACS event API](https://www.gdacs.org/) | tropical cyclones, floods, droughts | TC 2011–, FL 2000–, DR 2018– |
| [IBTrACS v04r01](https://www.ncei.noaa.gov/products/international-best-track-archive) | 6-hourly cyclone tracks and winds | 1980– |
| [GPCP v2.3](https://psl.noaa.gov/data/gridded/data.gpcp.html) | monthly precipitation, 2.5° | 1979– |
| [GHCN-CAMS](https://psl.noaa.gov/data/gridded/data.ghcncams.html) | monthly land 2 m temperature, 0.5° | 1948– |
| Natural Earth 110m | country borders, land mask | — |
| CPC / IRI bulletins (Sep–Oct 2026) | current ENSO state and outlook (typed in, with date) | — |

## Method in brief

* **ENSO year = June to May.** It holds the whole NH hurricane/typhoon season, the Indian monsoon,
  the El Niño peak and the SH cyclone season. The phase follows the CPC rule (≥ 5 consecutive
  seasons beyond ±0.5°C), judged on OND/NDJ/DJF of **RONI**.
* **Equal groups.** n = the size of the smallest phase within the data window. From the larger
  phases we take the clearest years: the largest |anomaly| for El Niño and La Niña, the smallest
  for Neutral.
* **GDACS quirks handled explicitly:**
  - Cyclones only start in July 2011, so 2012/13 is the first full year (n = 3 per phase).
  - Floods come from three catalogues: DFO, JRC and GloFAS, and GloFAS has ~4× more events.
    The 2016–18 transition is dropped, and every phase gets the same number of DFO and GloFAS years.
    Regions are counted as % of all floods in a year.
  - Droughts only start in 2018 (8 years, a single Neutral one), so the drought comparison uses
    **months** with an active drought, with the ENSO phase taken 3 months earlier.
* **Tests:**
  - Phase comparison: a two-sided permutation test, El Niño vs La Niña, over all years.
  - Hex maps: a Welch t-test per hexagon, with p < 0.10 shown as a bold number with *.
* **Hex-map classification:**

  | hazard | measure |
  |---|---|
  | cyclones | days with ≥ 34 kt wind |
  | major cyclones | days with ≥ 96 kt wind (cat. 3–5) |
  | drought | months with a non-parametric 6-month SPI ≤ −1 |
  | monsoon drought | local-summer rainfall deficit in the Wang & Ding monsoon domains |
  | heatwaves | months above the 90th percentile of the **detrended** temperature anomaly, so that global warming does not pose as an ENSO signal |

## Main findings

**Cyclones (IBTrACS, 13 seasons per phase).** El Niño vs Neutral:

| basin | El Niño | La Niña | p |
|---|---|---|---|
| Atlantic | −19% storms, −28% ACE | +24% storms, cat. 4–5 ×2.9 | < 0.01 |
| East/Central Pacific | cat. 4–5 +94%, ACE +51% | — | ≤ 0.01 |
| West Pacific | cat. 4–5 +19%; genesis shifts east (hex map) | ACE −41% | < 0.01 |
| Southern Hemisphere | cat. 4–5 +34%; activity shifts east towards French Polynesia | — | 0.09 |

* **GDACS (only 3 seasons per phase)** shows the same direction. East Pacific: +35% storms and
  ×3.8 cat. 4–5 storms (p = 0.01).

**Monsoons and rain (GDACS).**

* **Monsoon floods.** El Niño: India −15%, West Africa −34%, Australia–Indonesia −28%.
  La Niña: India +34%.
* **Winter floods in the southern US and Mexico.** El Niño +72%, La Niña −78% (p = 0.03).
* **East African short rains.** El Niño +40%.
* **Peru/Ecuador floods: fewer in El Niño years, against theory.** This is a data artefact: the 2017
  "coastal El Niño" floods fall in the dropped 2016–18 catalogue gap, and GDACS misses 1997/98.

**Droughts and heat.**

* **Droughts (GDACS months).**
  - Australia/Indonesia/W Pacific: active droughts +43% in El Niño and almost none in La Niña.
  - Worldwide: +18% in El Niño, −21% in La Niña.
* **Drought on the long record (GPCP hex map).** El Niño brings more dry months over:
  - Indonesia,
  - Australia,
  - southern Africa,
  - northern South America.
* **Monsoon drought.** The Indian and Indonesian-Australian monsoons show significant deficits.
* **Heatwaves (GHCN-CAMS, 23 years per phase).** El Niño adds about one extra hot month per year
  across the tropics: the Amazon, Africa, South and SE Asia, and northern Australia. The effect is
  significant in 57 hexagons.

**The year after (summer 2027).** Of 8 strong El Niños since 1950, the next year brought:

| next year | count |
|---|---|
| La Niña | 5 |
| Neutral | 2 |
| El Niño | 1 |

In the five post-strong-El Niño seasons since 1980, the Atlantic averaged −17%, but the spread
was large: 1983 and 1992 were quiet, while 1998, 2010 and 2016 were active. So summer 2027 is
shown as a scenario.

## Files

| path | contents |
|---|---|
| `analysis.ipynb` | executed notebook with all figures and tables |
| `out/forecast_maps.png` | part 1: the two forecast maps |
| `out/0_*.png … 9b_*.png` | part 2: ENSO timeline, GDACS and IBTrACS phase comparisons |
| `out/hex_*.png` | part 3: one 3-map hex image per hazard (`hex_*_values.csv`: values per year × hexagon) |
| `out/comparison.csv` | every measure: groups, means, % vs Neutral, p-value |
| `out/yearly.csv`, `out/droughts_monthly.csv` | the raw yearly / monthly values behind each bar |
| `out/enso_years.csv`, `out/after_strong_el_nino.csv` | ENSO classification, post-El Niño composite |
| `out/gdacs_events.csv`, `out/ibtracs_storms.csv` | event tables after basin/category classification |

| module | role |
|---|---|
| `config.py` | paths, sources, regions, thresholds |
| `data.py` | downloads with cache (CPC, GDACS, IBTrACS, GPCP, GHCN-CAMS, Natural Earth) |
| `enso.py` | ENSO year classification, equal groups, post-El Niño analogues |
| `events.py` | GDACS/IBTrACS → basin, Saffir-Simpson category, ENSO year |
| `analysis.py` | phase comparison and tests (part 2) |
| `climate.py` | hazard classification from raw grids and tracks (part 3) |
| `basemap.py` | Natural Earth projection (pyproj, no cartopy), merged land mass, hexagon grid |
| `plots.py`, `forecast.py`, `hexmaps.py` | figures |
| `run.py`, `build_notebook.py` | whole pipeline and the notebook |
