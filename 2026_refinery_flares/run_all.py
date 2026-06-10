"""Run FIRMS active-fire + Black Marble night-lights for ALL refineries.
- per-refinery combined graph  -> images/<refinery>.png
- overview multi-panel figure  -> images/all_refineries.png
- combined CSVs                -> data/firms_monthly_all.csv,
                                  data/blackmarble_all.csv,
                                  data/timeseries_long_all.csv
Usage: python run_all.py
"""
import os, io, re, time
from datetime import date, timedelta
import numpy as np, pandas as pd, geopandas as gpd, requests
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point

FIRMS_MAP_KEY = "2b1c34df0e49ece7703e69e48ab89256"
BLACKMARBLE_TOKEN = open("build_notebook.py", encoding="utf-8").read().split('BLACKMARBLE_TOKEN = "', 1)[1].split('"', 1)[0]
BM_COLLECTION = "5200"                              # Black Marble collection
BM_MONTHLY_START = date(2022, 1, 1)                 # hybrid: yearly VNP46A4 before, monthly VNP46A3 from here
NAME_COL = "name"
START, END = date(2016, 1, 1), date.today()   # 10-year analysis window
BM_START = date(2016, 1, 1)
BUFFER_M = 3000
CACHE_DIR = "cache"; IMG_DIR = "images"; DATA_DIR = "data"
for d in (CACHE_DIR, IMG_DIR, DATA_DIR, os.path.join(CACHE_DIR, "blackmarble")):
    os.makedirs(d, exist_ok=True)

SAMPLE = [
    ("HPCL Barmer / HRRL (IN)",            25.9436,  72.2037, "2018-01", "2026-01"),
    ("IOCL Panipat (IN)",                  29.4731,  76.8783, "1996-01", "1998-07"),
    ("Thai Oil Sri Racha (TH)",            13.1125, 100.9045, "1961-01", "1964-01"),
    ("Dangote / OK LNG site (NG)",          6.4314,   4.0054, "2016-01", "2024-01"),
    ("Pulau Muara Besar / Hengyi (BN)",     4.9920, 115.0480, "2017-01", "2019-11"),
    ("Pemex Olmeca / Dos Bocas (MX)",      18.4228, -93.1956, "2019-08", "2024-10"),
]
slug = lambda s: re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_")

# ---------------- FIRMS ----------------
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/{bbox}/{days}/{start}"
SRC_MIN = {"VIIRS_SNPP_SP": date(2012, 1, 20), "VIIRS_SNPP_NRT": date(2012, 1, 20),
           "VIIRS_NOAA20_SP": date(2018, 1, 1), "VIIRS_NOAA20_NRT": date(2018, 1, 1)}

def firms_chunk(name, src, bbox, start, days=5):
    fn = os.path.join(CACHE_DIR, f"{name}__{src}__{start}.csv".replace("/", "-").replace(" ", "_"))
    if os.path.exists(fn):
        try: return pd.read_csv(fn)
        except Exception: return pd.DataFrame()
    url = FIRMS_URL.format(key=FIRMS_MAP_KEY, src=src, bbox=bbox, days=days, start=start)
    for _ in range(30):                                 # FIRMS limit 5000 / 10 min: wait out the window
        r = requests.get(url, timeout=120)
        if r.status_code in (400, 429, 503):
            print(f"    throttled @ {start} -> wait 60s", flush=True); time.sleep(60); continue
        r.raise_for_status(); break
    else:
        raise RuntimeError("throttled after retries")
    txt = r.text.strip(); first = txt.split("\n", 1)[0] if txt else ""
    df = pd.read_csv(io.StringIO(txt)) if "," in first else pd.DataFrame()
    df.to_csv(fn, index=False); return df

def firms_dl(name, sources, bbox, start, end):
    frames = []
    for src in sources:
        d = max(start, SRC_MIN.get(src, start))
        while d <= end:
            try:
                df = firms_chunk(name, src, bbox, d.isoformat())
            except Exception as e:
                print("  !", src, d, e); df = pd.DataFrame()
            if len(df): df["source"] = src; frames.append(df)
            d += timedelta(days=5); time.sleep(0.03)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# ---------------- Black Marble ----------------
def bm_series(lon, lat):
    import h5py
    hdr = {"Authorization": "Bearer " + BLACKMARBLE_TOKEN}
    H, V = int((lon + 180) // 10), int((90 - lat) // 10)
    half = max(1, round(BUFFER_M / 463))
    targets = ([("VNP46A4", date(y, 1, 1)) for y in range(BM_START.year, BM_MONTHLY_START.year)]
               + [("VNP46A3", d.date()) for d in pd.date_range(BM_MONTHLY_START, END, freq="MS")])
    bmdir = os.path.join(CACHE_DIR, "blackmarble"); rows = []
    for prod, d in targets:
        doy = d.timetuple().tm_yday
        fn = os.path.join(bmdir, f"{prod}.{d.year}{doy:03d}.h{H:02d}v{V:02d}.h5")
        if not (os.path.exists(fn) and os.path.getsize(fn) > 1_000_000):
            lst = requests.get(f"https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/{BM_COLLECTION}/{prod}/{d.year}/{doy:03d}.json", headers=hdr, timeout=120)
            if lst.status_code != 200: continue
            tile = f"h{H:02d}v{V:02d}"
            hit = next((it for it in lst.json().get("content", []) if tile in it["name"]), None)
            if not hit: continue
            rr = requests.get(hit["downloadsLink"], headers=hdr, timeout=900)
            if "text/html" in rr.headers.get("content-type", ""):
                raise RuntimeError("Black Marble BLOCKED -> authorize 'LAADS Web' once at ladsweb.modaps.eosdis.nasa.gov")
            open(fn, "wb").write(rr.content)
        with h5py.File(fn, "r") as f:
            grids = f["HDFEOS/GRIDS"]; grp = grids[list(grids.keys())[0]]["Data Fields"]
            lyr = next((k for k in ("Gap_Filled_DNB_BRDF-Corrected_NTL", "NearNadir_Composite_Snow_Free", "AllAngle_Composite_Snow_Free") if k in grp), None)
            ds = grp[lyr]; n = ds.shape[0]; res = 10.0 / n
            col = int((lon - (-180 + H * 10)) / res); rp = int(((90 - V * 10) - lat) / res)
            win = ds[max(0, rp - half):rp + half + 1, max(0, col - half):col + half + 1].astype("float64")
            sf = float(np.atleast_1d(ds.attrs.get("scale_factor", 1.0))[0]); fv = float(np.atleast_1d(ds.attrs.get("_FillValue", 65535))[0])
            win[win == fv] = np.nan; rows.append((pd.Timestamp(d), np.nanmean(win) * sf))
    return pd.DataFrame(rows, columns=["date", "radiance"])

def panel(ax, name, monthly, bm, cons, prod):
    ax.bar(monthly["month"], monthly["detections"], width=18, color="orangered")
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
            ax.text(x, ytop * 0.97, " " + lab, color=color, rotation=90, va="top", fontsize=7)
    ax.set_title(name, fontsize=9, loc="left")

# ---------------- main loop ----------------
firms_all, bm_all, summ = [], [], []
fig_all, axes = plt.subplots(len(SAMPLE), 1, figsize=(13, 2.7 * len(SAMPLE)), sharex=True)
for ax, (name, lat, lon, cons_s, prod_s) in zip(np.atleast_1d(axes), SAMPLE):
    cons, prod = pd.Timestamp(cons_s), pd.Timestamp(prod_s)
    print("==", name, flush=True)
    ref = gpd.GeoDataFrame({NAME_COL: [name]}, geometry=[Point(lon, lat)], crs=4326)
    rb = ref.to_crs(3857); rb["geometry"] = rb.buffer(BUFFER_M); rb = rb.to_crs(4326)
    minx, miny, maxx, maxy = rb.geometry.iloc[0].bounds
    bbox = f"{minx:.4f},{miny:.4f},{maxx:.4f},{maxy:.4f}"
    nrt0 = END - timedelta(days=60)
    a = firms_dl(name, ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"], bbox, START, nrt0 - timedelta(days=1))
    b = firms_dl(name, ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"], bbox, nrt0, END)
    fires = pd.concat([x for x in (a, b) if len(x)], ignore_index=True) if (len(a) or len(b)) else pd.DataFrame()
    if len(fires):
        fires["acq_date"] = pd.to_datetime(fires["acq_date"])
        fp = gpd.GeoDataFrame(fires, geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs=4326)
        hits = gpd.sjoin(fp, rb[[NAME_COL, "geometry"]], how="inner", predicate="within")
    else:
        hits = gpd.GeoDataFrame(columns=["acq_date"])
    if len(hits):
        hits["month"] = hits["acq_date"].values.astype("datetime64[M]")
        monthly = hits.groupby("month").size().reset_index(name="detections")
    else:
        monthly = pd.DataFrame(columns=["month", "detections"])
    monthly.insert(0, "refinery", name); firms_all.append(monthly)

    try:
        bm = bm_series(lon, lat)
    except Exception as e:
        print("  ! BM:", e); bm = pd.DataFrame(columns=["date", "radiance"])
    bm2 = bm.copy(); bm2.insert(0, "refinery", name); bm_all.append(bm2)
    print(f"  -> {int(monthly['detections'].sum() or 0)} det | {len(bm)} BM yrs", flush=True)

    # per-refinery figure
    f1, a1 = plt.subplots(figsize=(13, 4.2)); panel(a1, name, monthly, bm, cons, prod)
    f1.suptitle(f"{name} — FIRMS active fire (bars) + Black Marble night-lights (line)", fontsize=11)
    f1.tight_layout(); f1.savefig(os.path.join(IMG_DIR, slug(name) + ".png"), dpi=120, bbox_inches="tight"); plt.close(f1)
    # overview panel
    panel(ax, name, monthly, bm, cons, prod)
    summ.append((name, int(monthly["detections"].sum() or 0), len(bm)))

np.atleast_1d(axes)[-1].set_xlabel("year")
fig_all.suptitle("Refineries — FIRMS active fire (bars) + Black Marble night-lights (line)", y=1.002, fontsize=12)
fig_all.tight_layout(); fig_all.savefig(os.path.join(IMG_DIR, "all_refineries.png"), dpi=120, bbox_inches="tight")

# ---------------- CSVs ----------------
firms_df = pd.concat(firms_all, ignore_index=True)
bm_df = pd.concat(bm_all, ignore_index=True)
firms_df.to_csv(os.path.join(DATA_DIR, "firms_monthly_all.csv"), index=False)
bm_df.to_csv(os.path.join(DATA_DIR, "blackmarble_all.csv"), index=False)
long = pd.concat([
    firms_df.rename(columns={"month": "date", "detections": "value"}).assign(series="firms_detections_monthly"),
    bm_df.rename(columns={"radiance": "value"}).assign(series="blackmarble_ntl_yearly"),
], ignore_index=True)[["refinery", "date", "series", "value"]]
long.to_csv(os.path.join(DATA_DIR, "timeseries_long_all.csv"), index=False)

print("\nSUMMARY (refinery | FIRMS detections | BM years):")
for s in summ: print(f"  {s[0]:42s} {s[1]:6d}  {s[2]}")
print("\nsaved images/ (per-refinery + all_refineries.png) and data/*.csv")
