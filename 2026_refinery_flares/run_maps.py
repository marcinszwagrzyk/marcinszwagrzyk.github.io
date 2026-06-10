"""Satellite maps with FIRMS active-fire points for each refinery.
- per-refinery map -> images/maps/<refinery>.png  (Esri World Imagery + detections colored by year)
- overview map     -> images/maps/_overview.png
Reads the FIRMS chunk cache populated by run_all.py / run_single.py.
Usage: python run_maps.py [name-substring]   (default: all)
"""
import os, re, sys, glob
from datetime import date
import numpy as np, pandas as pd, geopandas as gpd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from shapely.geometry import Point
import contextily as cx

BUFFER_M = 3000
CACHE_DIR = "cache"; IMG_DIR = "images"; MAP_DIR = os.path.join(IMG_DIR, "maps")
os.makedirs(MAP_DIR, exist_ok=True)
SAT = cx.providers.Esri.WorldImagery

SAMPLE = [
    ("HPCL Barmer / HRRL (IN)",            25.9436,  72.2037),
    ("IOCL Panipat (IN)",                  29.4731,  76.8783),
    ("Thai Oil Sri Racha (TH)",            13.1125, 100.9045),
    ("Dangote / OK LNG site (NG)",          6.4314,   4.0054),
    ("Pulau Muara Besar / Hengyi (BN)",     4.9920, 115.0480),
    ("Pemex Olmeca / Dos Bocas (MX)",      18.4228, -93.1956),
]
slug = lambda s: re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_")
sub = (sys.argv[1].lower() if len(sys.argv) > 1 else None)

def load_hits(name, lon, lat):
    tag = f"{name}".replace("/", "-").replace(" ", "_")
    files = glob.glob(os.path.join(CACHE_DIR, f"{tag}__*.csv"))
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if len(df) and "latitude" in df.columns:
            frames.append(df)
    if not frames:
        return gpd.GeoDataFrame(columns=["acq_date", "frp", "geometry"], geometry="geometry", crs=4326)
    fires = pd.concat(frames, ignore_index=True)
    fires["acq_date"] = pd.to_datetime(fires["acq_date"], errors="coerce")
    fires = fires[fires["acq_date"] >= pd.Timestamp(2016, 1, 1)]          # 10-year window
    fp = gpd.GeoDataFrame(fires, geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs=4326)
    ref = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs=4326).to_crs(3857)
    buf = ref.buffer(BUFFER_M).to_crs(4326).iloc[0]
    return fp[fp.within(buf)].copy()

def make_map(name, lon, lat):
    hits = load_hits(name, lon, lat)
    ref = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs=4326).to_crs(3857)
    buf = gpd.GeoDataFrame(geometry=ref.buffer(BUFFER_M), crs=3857)
    fig, ax = plt.subplots(figsize=(9, 9))
    buf.boundary.plot(ax=ax, color="cyan", lw=1.5, ls="--")
    ref.plot(ax=ax, color="red", marker="*", markersize=180, zorder=5, edgecolor="white")
    if len(hits):
        h = hits.to_crs(3857)
        yrs = h["acq_date"].dt.year.values
        frp = pd.to_numeric(h.get("frp", pd.Series(np.ones(len(h)))), errors="coerce").fillna(1).values
        norm = Normalize(vmin=np.nanmin(yrs), vmax=np.nanmax(yrs))
        ax.scatter(h.geometry.x, h.geometry.y, c=yrs, cmap="autumn_r", norm=norm,
                   s=8 + 4 * np.sqrt(np.clip(frp, 0, None)), alpha=0.9, edgecolor="k", linewidth=0.2, zorder=4)
        sm = ScalarMappable(norm=norm, cmap="autumn_r"); sm.set_array([])
        cb = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.01); cb.set_label("detection year")
    # frame to buffer extent (+10% margin)
    minx, miny, maxx, maxy = buf.total_bounds
    mx = (maxx - minx) * 0.10
    ax.set_xlim(minx - mx, maxx + mx); ax.set_ylim(miny - mx, maxy + mx)
    try:
        cx.add_basemap(ax, source=SAT, crs=3857, attribution_size=5)
    except Exception as e:
        print("  ! basemap:", e)
    ax.set_axis_off()
    ax.set_title(f"{name}\nFIRMS active-fire detections (n={len(hits)}) on Esri World Imagery", fontsize=11)
    fig.tight_layout(); out = os.path.join(MAP_DIR, slug(name) + ".png")
    fig.savefig(out, dpi=130, bbox_inches="tight"); plt.close(fig)
    print(f"  saved {out}  ({len(hits)} pts)")
    return len(hits)

def overview():
    g = gpd.GeoDataFrame({"name": [s[0] for s in SAMPLE]},
                         geometry=[Point(s[2], s[1]) for s in SAMPLE], crs=4326).to_crs(3857)
    fig, ax = plt.subplots(figsize=(14, 7))
    g.plot(ax=ax, color="red", marker="*", markersize=160, edgecolor="white", zorder=5)
    for _, r in g.iterrows():
        ax.annotate(r["name"].split(" / ")[0].split(" (")[0], (r.geometry.x, r.geometry.y),
                    xytext=(6, 6), textcoords="offset points", color="white", fontsize=8,
                    path_effects=None)
    ax.set_global() if hasattr(ax, "set_global") else None
    ax.set_xlim(-1.9e7, 1.45e7); ax.set_ylim(-3.0e6, 6.2e6)
    try:
        cx.add_basemap(ax, source=SAT, crs=3857, zoom=3, attribution_size=5)
    except Exception as e:
        print("  ! basemap:", e)
    ax.set_axis_off(); ax.set_title("Refineries — locations on Esri World Imagery", fontsize=12)
    fig.tight_layout(); out = os.path.join(MAP_DIR, "_overview.png")
    fig.savefig(out, dpi=130, bbox_inches="tight"); plt.close(fig)
    print("  saved", out)

if __name__ == "__main__":
    for name, lat, lon in SAMPLE:
        if sub and sub not in name.lower():
            continue
        print("==", name, flush=True)
        make_map(name, lon, lat)
    if not sub:
        overview()
    print("done.")
