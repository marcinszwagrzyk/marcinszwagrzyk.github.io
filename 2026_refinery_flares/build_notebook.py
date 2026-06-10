"""Generate refinery_flares.ipynb — GPKG-driven, FIRMS active fire (always) +
Black Marble night lights (optional, graceful fallback), time-series graphs + satellite maps.
Run:  C:/Users/marci/anaconda3/python.exe build_notebook.py
"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip("\n")))
co = lambda s: cells.append(nbf.v4.new_code_cell(s.strip("\n")))

md(r"""
# Refinery flaring — FIRMS active fire (+ optional Black Marble night lights)

**GPKG-driven.** Refineries are read from a GeoPackage (`REFINERIES_GPKG`); for each one
the notebook builds, from **2012 → today**:

1. **NASA FIRMS** active-fire detections (VIIRS 375 m) — the **primary** signal (always runs).
2. **NASA Black Marble** night-lights radiance (VNP46A4 yearly / A3 monthly) — **optional**:
   if there is no Earthdata token, the LAADS app isn't authorized, or anything else fails,
   the notebook **prints a note and proceeds with FIRMS only**.

Outputs:
- **time-series graphs** (FIRMS bars + Black Marble line, with construction/production markers)
  → `images/<refinery>.png` and `images/all_refineries.png`
- **satellite maps** with FIRMS points over Esri World Imagery → `images/maps/<refinery>.png`
- **CSVs** → `data/firms_monthly_all.csv`, `data/blackmarble_all.csv`, `data/timeseries_long_all.csv`
""")

co(r'''
import os, io, re, time, glob
from datetime import date, timedelta
import numpy as np, pandas as pd, geopandas as gpd, requests
import matplotlib.pyplot as plt
from shapely.geometry import Point

# ----------------------------- CONFIG -----------------------------
FIRMS_MAP_KEY = "2b1c34df0e49ece7703e69e48ab89256"          # NASA FIRMS key

# Refineries come from this GPKG. If it does not exist it is created from REFINERIES below.
REFINERIES_GPKG  = "data/refineries_2026.gpkg"
REFINERIES_LAYER = None
NAME_COL         = "name"                                    # name column in the GPKG

# Black Marble is OPTIONAL. Empty token / failure -> FIRMS only.
BLACKMARBLE_TOKEN = ""
BM_COLLECTION = "5200"           # Black Marble collection
BM_MONTHLY_START = date(2022, 1, 1)   # hybrid: yearly VNP46A4 before this, monthly VNP46A3 from here

START, END = date(2016, 1, 1), date.today()   # 10-year analysis window (FIRMS + Black Marble)
BM_START   = date(2016, 1, 1)
BUFFER_M   = 3000                # metres around each feature to sample / map
USE_VIIRS, USE_MODIS = True, False

CACHE_DIR, IMG_DIR, DATA_DIR, MAP_DIR = "cache", "images", "data", "images/maps"
for d in (CACHE_DIR, IMG_DIR, DATA_DIR, MAP_DIR, os.path.join(CACHE_DIR, "blackmarble")):
    os.makedirs(d, exist_ok=True)
slug = lambda s: re.sub(r"[^0-9A-Za-z]+", "_", str(s)).strip("_")
print("GPKG:", REFINERIES_GPKG, "|", START, "->", END, "| Black Marble:", "ON" if BLACKMARBLE_TOKEN else "OFF")
''')

md(r"""
## 1. Refineries (from GPKG)
Read refinery features from `REFINERIES_GPKG`. If the file is missing it is **created**
from the built-in table below (points + `construction` / `production` / `note`). Bring your
own GPKG (points *or* polygons) with a `name` column — optional `construction` /
`production` (or `start_year`) columns drive the date markers.
""")

co(r'''
# Built-in table used only to bootstrap the GPKG if it does not exist yet.
REFINERIES = [
    # name, lat, lon, construction, production, note
    ("HPCL Barmer / HRRL (IN)",            25.9436,  72.2037, "2018-01", "2026-01", "greenfield; pre-commissioning ~2026"),
    ("IOCL Panipat (IN)",                  29.4731,  76.8783, "1996-01", "1998-07", "legacy; commissioned Jul 1998"),
    ("Thai Oil Sri Racha (TH)",            13.1125, 100.9045, "1961-01", "1964-01", "legacy; CFP expansion 2018-2025"),
    ("Dangote / OK LNG site (NG)",          6.4314,   4.0054, "2016-01", "2024-01", "greenfield; petrol from 2024-09"),
    ("Pulau Muara Besar / Hengyi (BN)",     4.9920, 115.0480, "2017-01", "2019-11", "greenfield; phase 1 online 2019-11"),
    ("Pemex Olmeca / Dos Bocas (MX)",      18.4228, -93.1956, "2019-08", "2024-10", "greenfield; ramping since late 2024"),
]

def _ts(x):
    try:
        return pd.NaT if x is None or (isinstance(x, float) and np.isnan(x)) else pd.Timestamp(x)
    except Exception:
        return pd.NaT

if not os.path.exists(REFINERIES_GPKG):
    boot = gpd.GeoDataFrame(
        {NAME_COL:       [r[0] for r in REFINERIES],
         "construction": [r[3] for r in REFINERIES],
         "production":   [r[4] for r in REFINERIES],
         "note":         [r[5] for r in REFINERIES]},
        geometry=[Point(r[2], r[1]) for r in REFINERIES], crs=4326)
    boot.to_file(REFINERIES_GPKG, driver="GPKG")
    print("created", REFINERIES_GPKG)

def load_refineries():
    g = gpd.read_file(REFINERIES_GPKG, layer=REFINERIES_LAYER).to_crs(4326)
    if NAME_COL not in g.columns:
        cand = [c for c in g.columns if c.lower() == NAME_COL.lower()]
        g = g.rename(columns={cand[0]: NAME_COL}) if cand else g.assign(
            **{NAME_COL: [f"refinery_{i}" for i in range(len(g))]})
    g[NAME_COL] = g[NAME_COL].astype(str)
    for c in ("construction", "production"):
        g[c] = g[c].map(_ts) if c in g.columns else pd.NaT
    if g["production"].isna().all() and "start_year" in g.columns:
        g["production"] = g["start_year"].map(_ts)
    keep = [NAME_COL, "construction", "production"] + (["note"] if "note" in g.columns else [])
    return g[keep + ["geometry"]].reset_index(drop=True)

ref = load_refineries()
ref_buf = ref.to_crs(3857).copy(); ref_buf["geometry"] = ref_buf.geometry.buffer(BUFFER_M); ref_buf = ref_buf.to_crs(4326)
print(ref[[NAME_COL, "construction", "production"]].to_string(index=False))
ax = ref.plot(figsize=(11, 4), color="red", markersize=25); ax.set_title("Refineries"); plt.show()
''')

md(r"""
## 2. FIRMS download helpers
Area endpoint (max 5 days / request), cached per chunk. The FIRMS key allows **5000
transactions / 10 min** — when throttled the helper waits and retries (lossless).
""")

co(r'''
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/{bbox}/{days}/{start}"
SRC_MIN = {"MODIS_SP": date(2000,11,1), "MODIS_NRT": date(2000,11,1),
           "VIIRS_SNPP_SP": date(2012,1,20), "VIIRS_SNPP_NRT": date(2012,1,20),
           "VIIRS_NOAA20_SP": date(2018,1,1), "VIIRS_NOAA20_NRT": date(2018,1,1)}

def firms_chunk(name, src, bbox, start, days=5):
    fn = os.path.join(CACHE_DIR, f"{name}__{src}__{start}.csv".replace("/", "-").replace(" ", "_"))
    if os.path.exists(fn):
        try: return pd.read_csv(fn)
        except Exception: return pd.DataFrame()
    url = FIRMS_URL.format(key=FIRMS_MAP_KEY, src=src, bbox=bbox, days=days, start=start)
    for _ in range(30):                                   # wait out the 5000/10min window
        r = requests.get(url, timeout=120)
        if r.status_code in (400, 429, 503):
            time.sleep(60); continue
        r.raise_for_status(); break
    else:
        raise RuntimeError("FIRMS throttled after retries")
    txt = r.text.strip(); first = txt.split("\n", 1)[0] if txt else ""
    df = pd.read_csv(io.StringIO(txt)) if "," in first else pd.DataFrame()
    df.to_csv(fn, index=False); return df

def firms_download(name, sources, bbox, start, end, days=5, pause=0.03):
    frames = []
    for src in sources:
        d = max(start, SRC_MIN.get(src, start))
        while d <= end:
            try:
                df = firms_chunk(name, src, bbox, d.isoformat(), days)
            except Exception as e:
                print(f"  ! {name} {src} {d}: {e}"); df = pd.DataFrame()
            if len(df): df["source"] = src; frames.append(df)
            d += timedelta(days=days); time.sleep(pause)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
''')

md(r"""
## 3. Download active fire per refinery
First run is slow (2012→now × all sites, plus FIRMS rate-limit waits); cached afterwards.
""")

co(r'''
sources_sp  = (["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"] if USE_VIIRS else []) + (["MODIS_SP"] if USE_MODIS else [])
sources_nrt = (["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"] if USE_VIIRS else []) + (["MODIS_NRT"] if USE_MODIS else [])
nrt0 = END - timedelta(days=60)

all_fires = []
for _, row in ref_buf.iterrows():
    name = row[NAME_COL]
    minx, miny, maxx, maxy = row.geometry.bounds
    bbox = f"{minx:.4f},{miny:.4f},{maxx:.4f},{maxy:.4f}"
    print(f"== {name}  bbox={bbox}")
    a = firms_download(name, sources_sp,  bbox, START, nrt0 - timedelta(days=1))
    b = firms_download(name, sources_nrt, bbox, nrt0, END)
    df = pd.concat([x for x in (a, b) if len(x)], ignore_index=True) if (len(a) or len(b)) else pd.DataFrame()
    print(f"   -> {len(df)} raw detections")
    if len(df): df[NAME_COL] = name; all_fires.append(df)

fires = pd.concat(all_fires, ignore_index=True) if all_fires else pd.DataFrame()
print("TOTAL raw detections:", len(fires))
''')

md(r"""
## 4. Keep detections inside the buffers + monthly series
""")

co(r'''
fires["acq_date"] = pd.to_datetime(fires["acq_date"])
fpts = gpd.GeoDataFrame(fires.drop(columns=[NAME_COL], errors="ignore"),
                        geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs=4326)
hits = gpd.sjoin(fpts, ref_buf[[NAME_COL, "geometry"]], how="inner",
                 predicate="within").rename(columns={NAME_COL: "refinery"})
hits["month"] = hits["acq_date"].values.astype("datetime64[M]")
firms_monthly = hits.groupby(["refinery", "month"]).size().reset_index(name="detections")

summary = (hits.groupby("refinery")
              .agg(first_detection=("acq_date", "min"), last_detection=("acq_date", "max"),
                   total=("acq_date", "size"), fire_days=("acq_date", "nunique")).reset_index())
print(len(hits), "detections inside buffers")
summary
''')

md(r"""
## 5. Black Marble night lights — **optional**
Needs a NASA Earthdata token in `BLACKMARBLE_TOKEN` **and** a one-time authorization of the
"LAADS Web" app (log in at <https://ladsweb.modaps.eosdis.nasa.gov/> → approve). If the token
is empty, the app isn't authorized (download returns an HTML login page), or anything else
fails, this cell **prints a note and leaves Black Marble empty** — the rest of the notebook
runs on FIRMS only.

We do **not** use the `blackmarblepy` package (it calls LAADS's retired `/api/v1/files` API,
HTTP 404). Instead we list the archive (`/archive/allData/5200/{product}/{year}/{doy}.json`),
download the tile `h{H}v{V}` covering each site with the bearer token, and read the
BRDF-corrected NTL layer with `h5py` (mean radiance in a `BUFFER_M` window).
""")

co(r'''
def _bm_value(path, lon, lat, half):
    import h5py
    with h5py.File(path, "r") as f:
        grids = f["HDFEOS/GRIDS"]; grp = grids[list(grids.keys())[0]]["Data Fields"]
        lyr = next((k for k in ("Gap_Filled_DNB_BRDF-Corrected_NTL", "NearNadir_Composite_Snow_Free",
                                "AllAngle_Composite_Snow_Free") if k in grp), None)
        ds = grp[lyr]; n = ds.shape[0]; res = 10.0 / n
        H, V = int((lon + 180) // 10), int((90 - lat) // 10)
        col = int((lon - (-180 + H * 10)) / res); rp = int(((90 - V * 10) - lat) / res)
        win = ds[max(0, rp-half):rp+half+1, max(0, col-half):col+half+1].astype("float64")
        sf = float(np.atleast_1d(ds.attrs.get("scale_factor", 1.0))[0])
        fv = float(np.atleast_1d(ds.attrs.get("_FillValue", 65535))[0])
        win[win == fv] = np.nan
        return np.nanmean(win) * sf

def fetch_black_marble(ref_gdf):
    cols = ["refinery", "date", "radiance"]
    if not BLACKMARBLE_TOKEN:
        print("No BLACKMARBLE_ -> FIRMS only."); return pd.DataFrame(columns=cols)
    try:
        import h5py  # noqa
    except Exception as e:
        print("h5py missing -> FIRMS only:", e); return pd.DataFrame(columns=cols)
    hdr = {"Authorization": "Bearer " + BLACKMARBLE_TOKEN}
    bmdir = os.path.join(CACHE_DIR, "blackmarble")
    half = max(1, round(BUFFER_M / 463))
    # Hybrid: yearly VNP46A4 before BM_MONTHLY_START, monthly VNP46A3 from then on.
    targets = ([("VNP46A4", date(y, 1, 1)) for y in range(BM_START.year, BM_MONTHLY_START.year)]
               + [("VNP46A3", d.date()) for d in pd.date_range(BM_MONTHLY_START, END, freq="MS")])
    pts = ref_gdf.copy(); pts["geometry"] = pts.geometry.centroid
    rows = []
    for _, row in pts.iterrows():
        name = row[NAME_COL]; lon, lat = row.geometry.x, row.geometry.y
        H, V = int((lon + 180) // 10), int((90 - lat) // 10); got = 0
        for prod, d in targets:
            doy = d.timetuple().tm_yday
            fn = os.path.join(bmdir, f"{prod}.{d.year}{doy:03d}.h{H:02d}v{V:02d}.h5")
            try:
                if not (os.path.exists(fn) and os.path.getsize(fn) > 1_000_000):
                    lst = requests.get(f"https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/{BM_COLLECTION}/{prod}/{d.year}/{doy:03d}.json", headers=hdr, timeout=120)
                    if lst.status_code != 200: continue
                    hit = next((it for it in lst.json().get("content", []) if f"h{H:02d}v{V:02d}" in it["name"]), None)
                    if not hit: continue
                    rr = requests.get(hit["downloadsLink"], headers=hdr, timeout=900)
                    if "text/html" in rr.headers.get("content-type", ""):
                        print("  ! Black Marble blocked -> authorize 'LAADS Web' once (section 5). Proceeding FIRMS only.")
                        return pd.DataFrame(rows, columns=cols)
                    open(fn, "wb").write(rr.content)
                rows.append((name, pd.Timestamp(d), float(_bm_value(fn, lon, lat, half)))); got += 1
            except Exception as e:
                print(f"  ! BM {name} {d}: {e}")
        print(f"  Black Marble {name}: {got}/{len(targets)} (yearly<{BM_MONTHLY_START.year}, monthly>=)")
    return pd.DataFrame(rows, columns=cols)

try:
    bm_monthly = fetch_black_marble(ref_buf)
except Exception as e:
    print("Black Marble unavailable -> FIRMS only:", e)
    bm_monthly = pd.DataFrame(columns=["refinery", "date", "radiance"])
print("Black Marble rows:", len(bm_monthly))
bm_monthly.head()
''')

md(r"""
## 6. Time-series graphs
FIRMS detections/month (orange bars) + Black Marble radiance (purple line, if available),
with construction (grey dotted) and production (green dashed) markers.
""")

co(r'''
def panel(ax, name):
    g = firms_monthly[firms_monthly.refinery == name]
    ax.bar(g["month"], g["detections"], width=18, color="orangered")
    ax.set_ylabel("FIRMS det./mo", color="orangered", fontsize=8); ax.tick_params(axis="y", labelcolor="orangered", labelsize=8)
    ax.set_xlim(pd.Timestamp(START), pd.Timestamp(END))
    b = bm_monthly[bm_monthly.refinery == name].sort_values("date") if len(bm_monthly) else bm_monthly
    if len(b):
        ax2 = ax.twinx()
        ax2.plot(b["date"], b["radiance"], color="purple", lw=1.4, marker="o", ms=3)
        ax2.set_ylabel("NTL radiance", color="purple", fontsize=8); ax2.tick_params(axis="y", labelcolor="purple", labelsize=8)
    info = ref[ref[NAME_COL] == name].iloc[0]; ytop = ax.get_ylim()[1] or 1
    lo, hi = pd.Timestamp(START), pd.Timestamp(END)
    for col, color, ls, lab in [("construction", "grey", ":", "constr."), ("production", "green", "--", "prod.")]:
        x = info.get(col, pd.NaT)
        if pd.notna(x) and lo <= x <= hi:
            ax.axvline(x, color=color, ls=ls, lw=1.4)
            ax.text(x, ytop * 0.97, " " + lab, color=color, rotation=90, va="top", fontsize=7)
    ax.set_title(name, fontsize=9, loc="left")

names = list(ref[NAME_COL])
fig, axes = plt.subplots(len(names), 1, figsize=(13, 2.7 * len(names)), sharex=True)
for ax, name in zip(np.atleast_1d(axes), names):
    panel(ax, name)
    f1, a1 = plt.subplots(figsize=(13, 4.2)); panel(a1, name)
    f1.suptitle(f"{name} — FIRMS active fire (bars) + Black Marble night-lights (line)", fontsize=11)
    f1.tight_layout(); f1.savefig(os.path.join(IMG_DIR, slug(name) + ".png"), dpi=120, bbox_inches="tight"); plt.close(f1)
np.atleast_1d(axes)[-1].set_xlabel("year")
fig.suptitle("Refineries — FIRMS active fire (bars) + Black Marble night-lights (line)", y=1.002, fontsize=12)
fig.tight_layout(); fig.savefig(os.path.join(IMG_DIR, "all_refineries.png"), dpi=120, bbox_inches="tight"); plt.show()
''')

md(r"""
## 7. Satellite maps with FIRMS points
Each refinery on **Esri World Imagery** with its detections coloured by year (needs
`contextily` + internet for the basemap tiles).
""")

co(r'''
import contextily as cx
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
SAT = cx.providers.Esri.WorldImagery

def make_map(name):
    sub = hits[hits.refinery == name]
    rb = ref_buf[ref_buf[NAME_COL] == name].to_crs(3857)
    rc = ref[ref[NAME_COL] == name].to_crs(3857)
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    rb.boundary.plot(ax=ax, color="cyan", lw=1.4, ls="--")
    rc.plot(ax=ax, color="red", marker="*", markersize=160, edgecolor="white", zorder=5)
    if len(sub):
        h = sub.to_crs(3857); yrs = h["acq_date"].dt.year.values
        frp = pd.to_numeric(h.get("frp", pd.Series(np.ones(len(h)))), errors="coerce").fillna(1).values
        norm = Normalize(vmin=np.nanmin(yrs), vmax=np.nanmax(yrs))
        ax.scatter(h.geometry.x, h.geometry.y, c=yrs, cmap="autumn_r", norm=norm,
                   s=8 + 4*np.sqrt(np.clip(frp, 0, None)), alpha=0.9, edgecolor="k", linewidth=0.2, zorder=4)
        sm = ScalarMappable(norm=norm, cmap="autumn_r"); sm.set_array([])
        fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.01).set_label("detection year")
    minx, miny, maxx, maxy = rb.total_bounds; m = (maxx - minx) * 0.10
    ax.set_xlim(minx - m, maxx + m); ax.set_ylim(miny - m, maxy + m)
    try:
        cx.add_basemap(ax, source=SAT, crs=3857, attribution_size=5)
    except Exception as e:
        print("  ! basemap", name, e)
    ax.set_axis_off(); ax.set_title(f"{name}\nFIRMS detections (n={len(sub)}) on Esri World Imagery", fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(MAP_DIR, slug(name) + ".png"), dpi=130, bbox_inches="tight"); plt.close(fig)
    print(f"  map {name}: {len(sub)} pts")

for name in names:
    make_map(name)
print("maps saved to", MAP_DIR)
''')

co(r'''
# ---- Save CSVs + detections GPKG ----
firms_monthly.to_csv(os.path.join(DATA_DIR, "firms_monthly_all.csv"), index=False)
if len(bm_monthly): bm_monthly.to_csv(os.path.join(DATA_DIR, "blackmarble_all.csv"), index=False)
long = pd.concat([
    firms_monthly.rename(columns={"month": "date", "detections": "value"}).assign(series="firms_detections_monthly"),
    bm_monthly.rename(columns={"radiance": "value"}).assign(series="blackmarble_ntl_hybrid"),
], ignore_index=True)[["refinery", "date", "series", "value"]]
long.to_csv(os.path.join(DATA_DIR, "timeseries_long_all.csv"), index=False)
hits.drop(columns="index_right", errors="ignore").to_file(os.path.join(DATA_DIR, "firms_detections.gpkg"), driver="GPKG")
summary.to_csv(os.path.join(DATA_DIR, "summary.csv"), index=False)
print("saved data/*.csv, data/firms_detections.gpkg, images/ + images/maps/")
''')

md(r"""
## Reading the results
- **Greenfield** sites (Dangote, Pulau Muara Besar, Olmeca): Black Marble radiance should
  ramp up to the **production** marker — a clean commissioning signal even when active fire
  (FIRMS) stays low (modern flare-gas recovery).
- **Not-yet-operational** (HPCL Barmer, Pengerang biorefinery): construction lights may rise
  but little/no flaring yet — the absence is the finding.
- **Legacy** (Thai Oil, Petrobrazi): continuous flaring; look for step-changes at expansions.
- Centre points + buffer catch neighbours in dense zones — supply a **GPKG of true outlines**
  for clean attribution.
""")

nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                  "language_info": {"name": "python"}}
with open("refinery_flares.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print("wrote refinery_flares.ipynb with", len(cells), "cells")
