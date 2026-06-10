"""Render time-series graphs for ALL refineries FROM CACHE ONLY (no downloads).
Uses whatever FIRMS chunks + Black Marble tiles are already cached, so graphs appear
immediately and independently of the slow download batch.
-> images/<refinery>.png  +  images/all_refineries.png
Usage: python run_graphs.py
"""
import os, re, glob
from datetime import date, timedelta
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point

START, END = date(2016, 1, 1), date.today()   # 10-year analysis window
BM_MONTHLY_START = date(2022, 1, 1)           # hybrid: yearly VNP46A4 before, monthly VNP46A3 from here
CACHE_DIR, IMG_DIR = "cache", "images"
os.makedirs(IMG_DIR, exist_ok=True)
slug = lambda s: re.sub(r"[^0-9A-Za-z]+", "_", str(s)).strip("_")

# name, lat, lon, construction, production, buffer_m
SAMPLE = [
    ("HPCL Barmer / HRRL (IN)",            25.9436,  72.2037, "2018-01", "2026-01", 3000),
    ("IOCL Panipat (IN)",                  29.4812,  76.8783, "1996-01", "1998-07", 1800),
    ("Thai Oil Sri Racha (TH)",            13.1125, 100.9045, "1961-01", "1964-01", 2100),
    ("Dangote / OK LNG site (NG)",          6.4516,   4.0054, "2016-01", "2024-01", 3000),
    ("Pulau Muara Besar / Hengyi (BN)",     5.0040, 115.1030, "2017-01", "2019-11", 3000),
    ("Pemex Olmeca / Dos Bocas (MX)",      18.4228, -93.1956, "2019-08", "2024-10", 3000),
]

def firms_monthly(name, lon, lat, buffer_m=3000):
    tag = name.replace("/", "-").replace(" ", "_")
    frames = []
    for f in glob.glob(os.path.join(CACHE_DIR, f"{tag}__*.csv")):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if len(df) and "latitude" in df.columns:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["month", "detections"])
    fires = pd.concat(frames, ignore_index=True)
    fires["acq_date"] = pd.to_datetime(fires["acq_date"], errors="coerce")
    fp = gpd.GeoDataFrame(fires, geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs=4326)
    buf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs=4326).to_crs(3857).buffer(buffer_m).to_crs(4326).iloc[0]
    h = fp[fp.within(buf)].copy()
    if not len(h):
        return pd.DataFrame(columns=["month", "detections"])
    h["month"] = h["acq_date"].values.astype("datetime64[M]")
    return h.groupby("month").size().reset_index(name="detections")

def bm_cached(lon, lat, buffer_m=3000):
    """Read Black Marble values from already-downloaded tiles only (no network)."""
    try:
        import h5py
    except Exception:
        return pd.DataFrame(columns=["date", "radiance"])
    H, V = int((lon + 180) // 10), int((90 - lat) // 10)
    half = max(1, round(buffer_m / 463))
    rows = []
    files = (glob.glob(os.path.join(CACHE_DIR, "blackmarble", f"VNP46A4.*h{H:02d}v{V:02d}.h5"))
             + glob.glob(os.path.join(CACHE_DIR, "blackmarble", f"VNP46A3.*h{H:02d}v{V:02d}.h5")))
    for fn in sorted(files):
        if os.path.getsize(fn) < 1_000_000:
            continue
        prod = os.path.basename(fn).split(".")[0]
        tok = os.path.basename(fn).split(".")[1]          # YYYYDDD
        try:
            d = date(int(tok[:4]), 1, 1) + timedelta(days=int(tok[4:]) - 1)
        except Exception:
            continue
        if (prod == "VNP46A4" and d.year >= BM_MONTHLY_START.year) or (prod == "VNP46A3" and d < BM_MONTHLY_START):
            continue                                       # yearly only <2022, monthly only >=2022 (no overlap)
        try:
            with h5py.File(fn, "r") as f:
                grids = f["HDFEOS/GRIDS"]; grp = grids[list(grids.keys())[0]]["Data Fields"]
                lyr = next((k for k in ("Gap_Filled_DNB_BRDF-Corrected_NTL", "NearNadir_Composite_Snow_Free",
                                        "AllAngle_Composite_Snow_Free") if k in grp), None)
                ds = grp[lyr]; n = ds.shape[0]; res = 10.0 / n
                col = int((lon - (-180 + H * 10)) / res); rp = int(((90 - V * 10) - lat) / res)
                win = ds[max(0, rp-half):rp+half+1, max(0, col-half):col+half+1].astype("float64")
                sf = float(np.atleast_1d(ds.attrs.get("scale_factor", 1.0))[0])
                fv = float(np.atleast_1d(ds.attrs.get("_FillValue", 65535))[0])
                win[win == fv] = np.nan
                rows.append((pd.Timestamp(d), np.nanmean(win) * sf))
        except Exception:
            continue
    return pd.DataFrame(rows, columns=["date", "radiance"])

def panel(ax, name, m, bm, cons, prod):
    if len(m):
        ax.bar(m["month"], m["detections"], width=18, color="orangered")
    ax.set_ylabel("FIRMS det./mo", color="orangered", fontsize=8); ax.tick_params(axis="y", labelcolor="orangered", labelsize=8)
    ax.set_xlim(pd.Timestamp(START), pd.Timestamp(END))
    if len(bm):
        ax2 = ax.twinx(); b = bm.sort_values("date")
        ax2.plot(b["date"], b["radiance"], color="purple", lw=1.4, marker="o", ms=3)
        ax2.set_ylabel("NTL radiance", color="purple", fontsize=8); ax2.tick_params(axis="y", labelcolor="purple", labelsize=8)
    ytop = ax.get_ylim()[1] or 1; lo, hi = pd.Timestamp(START), pd.Timestamp(END)
    for x, color, ls, lab in [(cons, "grey", ":", "constr."), (prod, "green", "--", "prod.")]:
        if pd.notna(x) and lo <= x <= hi:
            ax.axvline(x, color=color, ls=ls, lw=1.4)
            ax.text(x, ytop*0.97, " " + lab, color=color, rotation=90, va="top", fontsize=7)
    ax.set_title(f"{name}", fontsize=9, loc="left")

fig, axes = plt.subplots(len(SAMPLE), 1, figsize=(13, 2.7*len(SAMPLE)), sharex=True)
firms_rows, bm_rows = [], []
for ax, (name, lat, lon, cs, ps, buf) in zip(np.atleast_1d(axes), SAMPLE):
    m = firms_monthly(name, lon, lat, buf); bm = bm_cached(lon, lat, buf)
    cons, prod = pd.Timestamp(cs), pd.Timestamp(ps)
    panel(ax, name, m, bm, cons, prod)
    if len(m): firms_rows.append(m.assign(refinery=name)[["refinery", "month", "detections"]])
    if len(bm): bm_rows.append(bm.assign(refinery=name)[["refinery", "date", "radiance"]])
    f1, a1 = plt.subplots(figsize=(13, 4.2)); panel(a1, name, m, bm, cons, prod)
    f1.suptitle(f"{name} — FIRMS active fire (bars) + Black Marble night-lights (line)", fontsize=11)
    f1.tight_layout(); f1.savefig(os.path.join(IMG_DIR, slug(name) + ".png"), dpi=120, bbox_inches="tight"); plt.close(f1)
    print(f"  {name:38s} FIRMS det={int(m['detections'].sum()) if len(m) else 0:5d}  BM pts={len(bm)}")
np.atleast_1d(axes)[-1].set_xlabel("year")
fig.suptitle("Refineries — FIRMS active fire (bars) + Black Marble night-lights (line)", y=1.002, fontsize=12)
fig.tight_layout(); fig.savefig(os.path.join(IMG_DIR, "all_refineries.png"), dpi=120, bbox_inches="tight")

# Authoritative CSVs (from cache, all refineries) — overwrites run_all's partial output.
os.makedirs(DATA_DIR := "data", exist_ok=True)
firms_df = pd.concat(firms_rows, ignore_index=True) if firms_rows else pd.DataFrame(columns=["refinery", "month", "detections"])
bm_df = pd.concat(bm_rows, ignore_index=True) if bm_rows else pd.DataFrame(columns=["refinery", "date", "radiance"])
firms_df.to_csv(os.path.join(DATA_DIR, "firms_monthly_all.csv"), index=False)
bm_df.to_csv(os.path.join(DATA_DIR, "blackmarble_all.csv"), index=False)
long = pd.concat([
    firms_df.rename(columns={"month": "date", "detections": "value"}).assign(series="firms_detections_monthly"),
    bm_df.rename(columns={"radiance": "value"}).assign(series="blackmarble_ntl_hybrid"),
], ignore_index=True)[["refinery", "date", "series", "value"]]
long.to_csv(os.path.join(DATA_DIR, "timeseries_long_all.csv"), index=False)
print(f"saved graphs + CSVs (FIRMS {firms_df['refinery'].nunique()} ref, BM {bm_df['refinery'].nunique()} ref)")
