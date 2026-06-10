"""Run the FIRMS + Black Marble pipeline for ONE refinery and render the combined graph.
Usage: python run_single.py "Dangote"
"""
import os, io, sys, time
from datetime import date, timedelta
import numpy as np, pandas as pd, geopandas as gpd, requests
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point

FIRMS_MAP_KEY = ""
BLACKMARBLE_TOKEN = open("build_notebook.py", encoding="utf-8").read().split('BLACKMARBLE_TOKEN = "', 1)[1].split('"', 1)[0]
BM_PRODUCT, BM_COLLECTION = "VNP46A4", "5200"
NAME_COL = "name"
START, END = date(2012, 1, 1), date.today()
BM_START = date(2012, 1, 1)
BUFFER_M = 3000
CACHE_DIR = "cache"; os.makedirs(CACHE_DIR, exist_ok=True)

SAMPLE = [
    ("HPCL Barmer / HRRL (IN)",            25.9436,  72.2037, "2018-01", "2026-01"),
    ("Petronas Pengerang Biorefinery (MY)", 1.3600, 104.1300, "2024-11", "2028-07"),
    ("Thai Oil Sri Racha (TH)",            13.1125, 100.9045, "1961-01", "1964-01"),
    ("Dangote / OK LNG site (NG)",          6.4314,   4.0054, "2016-01", "2024-01"),
    ("OMV Petrom Petrobrazi (RO)",         44.8718,  26.0160, "1934-06", "1934-06"),
    ("Pulau Muara Besar / Hengyi (BN)",     4.9920, 115.0480, "2017-01", "2019-11"),
    ("Pemex Olmeca / Dos Bocas (MX)",      18.4228, -93.1956, "2019-08", "2024-10"),
]
key = (sys.argv[1] if len(sys.argv) > 1 else "Dangote").lower()
row = next(s for s in SAMPLE if key in s[0].lower())
NAME, LAT, LON, CONS, PROD = row[0], row[1], row[2], pd.Timestamp(row[3]), pd.Timestamp(row[4])
print("Refinery:", NAME)

ref = gpd.GeoDataFrame({NAME_COL: [NAME]}, geometry=[Point(LON, LAT)], crs=4326)
ref_buf = ref.to_crs(3857); ref_buf["geometry"] = ref_buf.buffer(BUFFER_M); ref_buf = ref_buf.to_crs(4326)
minx, miny, maxx, maxy = ref_buf.geometry.iloc[0].bounds
bbox = f"{minx:.4f},{miny:.4f},{maxx:.4f},{maxy:.4f}"

# ---------------- FIRMS ----------------
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/{bbox}/{days}/{start}"
SRC_MIN = {"VIIRS_SNPP_SP": date(2012, 1, 20), "VIIRS_SNPP_NRT": date(2012, 1, 20),
           "VIIRS_NOAA20_SP": date(2018, 1, 1), "VIIRS_NOAA20_NRT": date(2018, 1, 1)}

def firms_chunk(src, start, days=5):
    fn = os.path.join(CACHE_DIR, f"{NAME}__{src}__{start}.csv".replace("/", "-").replace(" ", "_"))
    if os.path.exists(fn):
        try: return pd.read_csv(fn)
        except Exception: return pd.DataFrame()
    url = FIRMS_URL.format(key=FIRMS_MAP_KEY, src=src, bbox=bbox, days=days, start=start)
    for attempt in range(6):                       # FIRMS limit = 5000 transactions / 10 min
        r = requests.get(url, timeout=120)
        if r.status_code in (400, 429, 503):       # throttled -> wait for the window to refill
            time.sleep(20); continue
        r.raise_for_status(); break
    else:
        raise RuntimeError("throttled after retries")
    txt = r.text.strip(); first = txt.split("\n", 1)[0] if txt else ""
    df = pd.read_csv(io.StringIO(txt)) if "," in first else pd.DataFrame()
    df.to_csv(fn, index=False); return df

def firms_dl(sources, start, end):
    frames = []
    for src in sources:
        d = max(start, SRC_MIN.get(src, start))
        while d <= end:
            try:
                df = firms_chunk(src, d.isoformat())
            except Exception as e:
                print("  !", src, d, e); df = pd.DataFrame()
            if len(df): df["source"] = src; frames.append(df)
            d += timedelta(days=5); time.sleep(0.05)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

nrt0 = END - timedelta(days=60)
print("downloading FIRMS (cached chunks) ...")
a = firms_dl(["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"], START, nrt0 - timedelta(days=1))
b = firms_dl(["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"], nrt0, END)
fires = pd.concat([x for x in (a, b) if len(x)], ignore_index=True)
fires["acq_date"] = pd.to_datetime(fires["acq_date"])
fpts = gpd.GeoDataFrame(fires, geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs=4326)
hits = gpd.sjoin(fpts, ref_buf[[NAME_COL, "geometry"]], how="inner", predicate="within")
print("detections in buffer:", len(hits))
hits["month"] = hits["acq_date"].values.astype("datetime64[M]")
monthly = hits.groupby("month").size().reset_index(name="detections")

# ---------------- Black Marble ----------------
def fetch_bm():
    import h5py
    hdr = {"Authorization": "Bearer " + BLACKMARBLE_TOKEN}
    H, V = int((LON + 180) // 10), int((90 - LAT) // 10)
    half = max(1, round(BUFFER_M / 463))
    dates = [date(y, 1, 1) for y in range(BM_START.year, END.year + 1)] if BM_PRODUCT == "VNP46A4" \
        else [d.date() for d in pd.date_range(BM_START, END, freq="MS")]
    bmdir = os.path.join(CACHE_DIR, "blackmarble"); os.makedirs(bmdir, exist_ok=True)
    rows = []
    for d in dates:
        doy = d.timetuple().tm_yday
        fn = os.path.join(bmdir, f"{BM_PRODUCT}.{d.year}{doy:03d}.h{H:02d}v{V:02d}.h5")
        if not (os.path.exists(fn) and os.path.getsize(fn) > 1_000_000):
            lst = requests.get(f"https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/{BM_COLLECTION}/{BM_PRODUCT}/{d.year}/{doy:03d}.json", headers=hdr, timeout=120)
            if lst.status_code != 200: continue
            tile = f"h{H:02d}v{V:02d}"
            hit = next((it for it in lst.json().get("content", []) if tile in it["name"]), None)
            if not hit: continue
            rr = requests.get(hit["downloadsLink"], headers=hdr, timeout=900)
            if "text/html" in rr.headers.get("content-type", ""):
                print("  ! Black Marble BLOCKED -> authorize 'LAADS Web' once at ladsweb.modaps.eosdis.nasa.gov"); return pd.DataFrame(columns=["date", "radiance"])
            open(fn, "wb").write(rr.content)
        with h5py.File(fn, "r") as f:
            grids = f["HDFEOS/GRIDS"]; grp = grids[list(grids.keys())[0]]["Data Fields"]
            lyr = next((k for k in ("Gap_Filled_DNB_BRDF-Corrected_NTL", "NearNadir_Composite_Snow_Free", "AllAngle_Composite_Snow_Free") if k in grp), None)
            ds = grp[lyr]; n = ds.shape[0]; res = 10.0 / n
            col = int((LON - (-180 + H * 10)) / res); rp = int(((90 - V * 10) - LAT) / res)
            win = ds[max(0, rp - half):rp + half + 1, max(0, col - half):col + half + 1].astype("float64")
            sf = float(np.atleast_1d(ds.attrs.get("scale_factor", 1.0))[0]); fv = float(np.atleast_1d(ds.attrs.get("_FillValue", 65535))[0])
            win[win == fv] = np.nan; rows.append((pd.Timestamp(d), np.nanmean(win) * sf))
    return pd.DataFrame(rows, columns=["date", "radiance"])

try:
    bm = fetch_bm()
except Exception as e:
    print("  ! Black Marble error:", e); bm = pd.DataFrame(columns=["date", "radiance"])
print("Black Marble timesteps:", len(bm))

# ---------------- Plot ----------------
fig, ax = plt.subplots(figsize=(13, 4.5))
ax.bar(monthly["month"], monthly["detections"], width=18, color="orangered", label="FIRMS det./mo")
ax.set_ylabel("FIRMS active-fire det./month", color="orangered"); ax.tick_params(axis="y", labelcolor="orangered")
ax.set_xlim(pd.Timestamp(START), pd.Timestamp(END)); ax.set_xlabel("year")

if len(bm):
    ax2 = ax.twinx(); bm = bm.sort_values("date")
    ax2.plot(bm["date"], bm["radiance"], color="purple", lw=1.6, marker="o", ms=4, label=f"Black Marble NTL ({BM_PRODUCT})")
    ax2.set_ylabel("Night-lights radiance (nW/cm²/sr)", color="purple"); ax2.tick_params(axis="y", labelcolor="purple")
else:
    ax.text(0.5, 0.9, "Black Marble pending LAADS authorization (FIRMS only)", transform=ax.transAxes,
            ha="center", color="purple", fontsize=9, style="italic")

ytop = ax.get_ylim()[1]
ax.axvline(CONS, color="grey", ls=":", lw=1.6); ax.text(CONS, ytop * 0.97, " construction", color="grey", rotation=90, va="top", fontsize=8)
ax.axvline(PROD, color="green", ls="--", lw=1.6); ax.text(PROD, ytop * 0.97, " production", color="green", rotation=90, va="top", fontsize=8)

fig.suptitle(f"{NAME} — FIRMS active fire (bars) + Black Marble night-lights (line)", fontsize=12)
plt.tight_layout(); plt.savefig("single_refinery.png", dpi=120, bbox_inches="tight")
print("first detection:", hits["acq_date"].min(), "| total:", len(hits))
print("saved single_refinery.png")
