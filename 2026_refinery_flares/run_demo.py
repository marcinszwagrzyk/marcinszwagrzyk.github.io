"""Quick demo run of the notebook pipeline (reduced scope) -> saves demo_output.png.
Same logic as refinery_flares.ipynb, limited to 2 greenfield refineries so it finishes fast.
"""
import os, io, time
from datetime import date, timedelta
import requests
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point

FIRMS_MAP_KEY = "2b1c34df0e49ece7703e69e48ab89256"
NAME_COL = "name"
BUFFER_M = 4000
START = date(2016, 1, 1)
END = date.today()
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

SAMPLE = [
    ("RAPID Pengerang (MY)", 1.3800, 104.1600, 2019),
    ("Nghi Son (VN)",       19.3337, 105.7881, 2018),
]
ref = gpd.GeoDataFrame(
    {NAME_COL: [s[0] for s in SAMPLE], "start_year": [s[3] for s in SAMPLE]},
    geometry=[Point(s[2], s[1]) for s in SAMPLE], crs=4326)
ref_buf = ref.to_crs(3857).copy()
ref_buf["geometry"] = ref_buf.geometry.buffer(BUFFER_M)
ref_buf = ref_buf.to_crs(4326)

FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/{bbox}/{days}/{start}"

def firms_chunk(src, bbox, start, tag, days=5):
    fn = os.path.join(CACHE_DIR, f"{tag}__{src}__{start}.csv".replace("/", "-").replace(" ", "_"))
    if os.path.exists(fn):
        try:
            return pd.read_csv(fn)
        except Exception:
            return pd.DataFrame()
    url = FIRMS_URL.format(key=FIRMS_MAP_KEY, src=src, bbox=bbox, days=days, start=start)
    r = requests.get(url, timeout=120); r.raise_for_status()
    txt = r.text.strip()
    first = txt.split("\n", 1)[0] if txt else ""
    if "," not in first:
        if "invalid" in txt.lower() or "error" in txt.lower():
            raise RuntimeError(txt[:200])
        df = pd.DataFrame()
    else:
        df = pd.read_csv(io.StringIO(txt))
    df.to_csv(fn, index=False)
    return df

def firms_download(sources, bbox, start, end, tag, days=5, pause=0.1):
    frames = []
    for src in sources:
        d = start
        while d <= end:
            try:
                df = firms_chunk(src, bbox, d.isoformat(), tag, days)
            except Exception as e:
                print(f"  ! {tag} {src} {d}: {e}", flush=True); df = pd.DataFrame()
            if len(df):
                df["source"] = src
                frames.append(df)
            d += timedelta(days=days)
            time.sleep(pause)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

src_sp = ["VIIRS_SNPP_SP"]
src_nrt = ["VIIRS_SNPP_NRT"]
nrt_start = END - timedelta(days=60)

all_fires = []
for _, row in ref_buf.iterrows():
    name = row[NAME_COL]
    minx, miny, maxx, maxy = row.geometry.bounds
    bbox = f"{minx:.4f},{miny:.4f},{maxx:.4f},{maxy:.4f}"
    print(f"== {name}  bbox={bbox}", flush=True)
    a = firms_download(src_sp, bbox, START, nrt_start - timedelta(days=1), tag=name)
    b = firms_download(src_nrt, bbox, nrt_start, END, tag=name)
    df = pd.concat([x for x in (a, b) if len(x)], ignore_index=True) if (len(a) or len(b)) else pd.DataFrame()
    print(f"   -> {len(df)} raw detections in bbox", flush=True)
    if len(df):
        df[NAME_COL] = name
        all_fires.append(df)

fires = pd.concat(all_fires, ignore_index=True)
fires["acq_date"] = pd.to_datetime(fires["acq_date"])
fpts = gpd.GeoDataFrame(fires, geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs=4326)
fpts = fpts.drop(columns=[NAME_COL], errors="ignore")
hits = gpd.sjoin(fpts, ref_buf[[NAME_COL, "start_year", "geometry"]],
                 how="inner", predicate="within").rename(columns={NAME_COL: "refinery"})
print("inside buffers:", len(hits), flush=True)

hits["month"] = hits["acq_date"].values.astype("datetime64[M]")
monthly = hits.groupby(["refinery", "month"]).size().reset_index(name="detections")

refs = sorted(monthly["refinery"].unique())
fig, axes = plt.subplots(len(refs), 1, figsize=(12, 2.6 * len(refs)), sharex=True)
import numpy as np
axes = np.atleast_1d(axes)
for ax, name in zip(axes, refs):
    g = monthly[monthly.refinery == name]
    ax.bar(g["month"], g["detections"], width=18, color="orangered")
    sy = int(ref.loc[ref[NAME_COL] == name, "start_year"].iloc[0])
    ax.axvline(pd.Timestamp(sy, 1, 1), color="navy", ls="--", lw=1)
    ax.text(pd.Timestamp(sy, 1, 1), ax.get_ylim()[1] * 0.8, f"  start {sy}", color="navy", fontsize=8)
    ax.set_title(name, fontsize=9, loc="left"); ax.set_ylabel("det./mo")
    ax.set_xlim(pd.Timestamp(START), pd.Timestamp(END))
axes[-1].set_xlabel("year")
fig.suptitle("VIIRS active-fire detections at refineries — monthly (DEMO)", y=1.0)
plt.tight_layout(); plt.savefig("demo_output.png", dpi=110, bbox_inches="tight")
print("\nSUMMARY:", flush=True)
print(hits.groupby("refinery").agg(first=("acq_date", "min"), total=("acq_date", "size"),
                                   fire_days=("acq_date", "nunique")).to_string(), flush=True)
print("saved demo_output.png", flush=True)
