# Refinery flares from satellite active-fire data

Detect refinery flaring / fires from **NASA FIRMS** active-fire detections and plot a
per-refinery time series (2010 → today). Built to run on the **Microsoft Planetary
Computer** JupyterHub (or any local Python env with the geo stack).

## Phase 1 (this notebook) — NASA FIRMS only
- **VIIRS** 375 m active fire — *main focus* (S-NPP from 2012, NOAA-20 from 2018).
- **MODIS** 1 km active fire (2000+) — optional, fills the 2010–2012 gap / cross-check.
- Refinery extents: load from a **GPKG** (`REFINERIES_GPKG`) *or* use the built-in
  sample of a few refineries that **started operating between 2012 and 2022**, so the
  flaring signal visibly appears around their start year.

Later phases (not implemented yet): VIIRS **Black Marble** night lights and
Planetary-Computer raster products.

## Why FIRMS (and not the Planetary Computer STAC) for VIIRS
VIIRS active fire is **not** in the Planetary Computer STAC catalog, and VIIRS only
starts in **2012**. NASA FIRMS is the authoritative archive for point active-fire
detections and is ideal for attributing fires to a refinery polygon. The notebook still
runs fine on the MPC JupyterHub — it just pulls from the FIRMS API.

## Setup
```bash
pip install -r requirements.txt
```
The FIRMS API key is already set in the notebook (`FIRMS_MAP_KEY`). Get your own free
key at https://firms.modaps.eosdis.nasa.gov/api/area/ if needed.

## Run
Open `refinery_flares.ipynb` and run top to bottom. The first run downloads the archive
in 10-day chunks **per refinery** and caches every chunk under `cache/`, so re-runs are
instant. A full VIIRS pull for ~6 refineries takes roughly 10–20 min the first time.

## Using your own refineries (the intended workflow)
Set `REFINERIES_GPKG = "data/your_refineries.gpkg"` (and `NAME_COL`). The analysis is
then **restricted to those polygons** (`BUFFER_M` auto-set to 0 — strict in-polygon).
An optional `start_year` column draws a marker at each refinery's start-up.

**Why polygons matter:** many refineries sit in dense industrial zones (e.g. Jubail,
Yanbu) where neighbouring plants flare too — a loose point+buffer picks them up. Exact
GPKG outlines keep the detections to the refinery itself. Greenfield/isolated sites
(e.g. RAPID Pengerang) show a clean flaring switch-on at start-up; clustered ones don't.
