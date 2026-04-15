"""
Gulf States Gas Flare Analysis — VIIRS Nightfire
Download, Planck fitting, analysis, and plotting.
API key lives in config.py (gitignored), not here.
"""

import io
import pickle
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Physical constants ──
_h = 6.62607015e-34
_c = 2.99792458e8
_kB = 1.380649e-23
_sigma = 5.670374419e-8
LAM_I4 = 3.74e-6
LAM_I5 = 11.45e-6
PIXEL_AREA = 375.0 * 375.0

DARK_STYLE = {
    "figure.facecolor": "#0d1117", "axes.facecolor": "#0d1117",
    "axes.edgecolor": "#333", "text.color": "#c9d1d9",
    "axes.labelcolor": "#c9d1d9", "xtick.color": "#8b949e",
    "ytick.color": "#8b949e", "figure.dpi": 130, "font.size": 10,
}

COUNTRY_COLORS = {
    "Iraq": "#ff3300", "Iran": "#ff6600", "Saudi Arabia": "#ffaa00",
    "Kuwait": "#44cc44", "UAE": "#4488ff", "Oman": "#aa66ff",
    "Qatar": "#00cccc", "Yemen": "#ff66aa", "Bahrain": "#cccccc",
}


FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

VIIRS_SOURCES_SP = ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"]
VIIRS_SOURCES_NRT = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]


# ═══════════════════════════════════════════════════════════════════
# Download
# ═══════════════════════════════════════════════════════════════════

def _fetch_firms(api_key, source, bbox, date_str, days=1):
    """Single FIRMS API call. Returns DataFrame or empty."""
    url = f"{FIRMS_BASE_URL}/{api_key}/{source}/{bbox}/{days}/{date_str}"
    r = requests.get(url, timeout=120)
    if r.status_code == 400:
        return pd.DataFrame()
    r.raise_for_status()
    t = r.text.strip()
    if not t or t.startswith("<!") or t.startswith("{"):
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(t))


def download_firms(api_key, bbox, start_date, end_date, output_path,
                   sources=None):
    """
    Download VIIRS data from FIRMS API with checkpoint/resume.

    Args:
        api_key:     NASA FIRMS MAP_KEY
        bbox:        "west,south,east,north" string
        start_date:  "YYYY-MM-DD"
        end_date:    "YYYY-MM-DD"
        output_path: Path for output parquet
        sources:     list of VIIRS source names (auto-selects SP vs NRT if None)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = output_path.parent / "_download_checkpoint.pkl"

    if sources is None:
        cutoff = datetime.now() - timedelta(days=60)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        sources = VIIRS_SOURCES_SP if start_dt < cutoff else VIIRS_SOURCES_NRT

    # Resume from checkpoint
    if checkpoint.exists():
        with open(checkpoint, "rb") as f:
            state = pickle.load(f)
        dfs, done = state["dfs"], state["done"]
        print(f"Resuming: {len(dfs)} chunks, {sum(len(d) for d in dfs):,} rows")
    else:
        dfs, done = [], set()

    s = datetime.strptime(start_date, "%Y-%m-%d")
    e = datetime.strptime(end_date, "%Y-%m-%d")
    cur = s

    while cur <= e:
        chunk = min((e - cur).days + 1, 5)
        ds = cur.strftime("%Y-%m-%d")

        if ds not in done:
            for src in sources:
                try:
                    df = _fetch_firms(api_key, src, bbox, ds, chunk)
                    if not df.empty:
                        dfs.append(df)
                except requests.HTTPError as ex:
                    if ex.response.status_code == 429:
                        print(f"  429 at {ds}, sleeping 90s...")
                        time.sleep(90)
                        try:
                            df = _fetch_firms(api_key, src, bbox, ds, chunk)
                            if not df.empty:
                                dfs.append(df)
                        except Exception:
                            pass
                    else:
                        print(f"  Error {ds} {src}: {ex}")
                time.sleep(0.3)

            done.add(ds)
            if len(done) % 10 == 0:
                with open(checkpoint, "wb") as f:
                    pickle.dump({"dfs": dfs, "done": done}, f)

        n = sum(len(d) for d in dfs)
        if cur.day <= 5:
            print(f"  {ds} ... {n:,} rows ({len(done)} chunks done)")
        cur += timedelta(days=chunk)

    raw = pd.concat(dfs, ignore_index=True)
    raw.columns = raw.columns.str.lower()
    raw.to_parquet(output_path, index=False)
    print(f"Done! {len(raw):,} rows -> {output_path}")

    if checkpoint.exists():
        checkpoint.unlink()

    return raw


# ═══════════════════════════════════════════════════════════════════
# Planck fitting
# ═══════════════════════════════════════════════════════════════════

def _planck(lam, T):
    T = np.asarray(T, dtype=float)
    x = np.clip(_h * _c / (lam * _kB * T), 0, 500)
    return (2 * _h * _c**2 / lam**5) / (np.exp(x) - 1) * 1e-6


def estimate_fire_params(T4, T5, FRP):
    """FRP-constrained Dozier method. Returns (Temp_K, Area_m2)."""
    T4 = np.asarray(T4, dtype=float)
    T5 = np.asarray(T5, dtype=float)
    FRP_w = np.asarray(FRP, dtype=float) * 1e6

    L4_obs = _planck(LAM_I4, T4)
    L4_bg = _planck(LAM_I4, T5)
    L4_exc = L4_obs - L4_bg

    n = len(T4)
    Tf_out = np.full(n, np.nan)
    Af_out = np.full(n, 0.0)

    valid = L4_exc > 0
    R_target = np.where(valid, FRP_w / (_sigma * L4_exc * PIXEL_AREA), 0)

    T_grid = np.linspace(400, 3000, 500)
    B4_grid = np.array([_planck(LAM_I4, t) for t in T_grid])

    CHUNK = 50_000
    for start in range(0, n, CHUNK):
        end = min(start + CHUNK, n)
        sl = slice(start, end)
        v = valid[sl]
        if not v.any():
            continue

        L4_bg_chunk = L4_bg[sl]
        T5_chunk = T5[sl]
        denom = B4_grid[:, None] - L4_bg_chunk[None, :]
        T4_diff = T_grid[:, None] ** 4 - T5_chunk[None, :] ** 4
        R_model = np.where(denom > 0, T4_diff / denom, 1e20)

        diffs = np.abs(R_model - R_target[sl][None, :])
        best_j = np.argmin(diffs, axis=0)

        Tf_best = T_grid[best_j]
        B4_best = B4_grid[best_j]
        denom_best = B4_best - L4_bg_chunk
        L4_exc_chunk = L4_exc[sl]

        p = np.where(denom_best > 0, L4_exc_chunk / denom_best, 0)
        good = v & (p > 1e-8) & (p < 1.0)

        Tf_out[sl] = np.where(good, Tf_best, np.nan)
        Af_out[sl] = np.where(good, p * PIXEL_AREA, 0.0)

    return Tf_out, Af_out


def load_and_process(parquet_path, country_bbox):
    """Load parquet, filter night flares, run Planck fitting, assign countries."""
    raw = pd.read_parquet(parquet_path)
    print(f"Loaded: {len(raw):,} rows")

    # Filter: night, confidence n/h, FRP >= 0.5
    mask = (
        (raw["daynight"] == "N")
        & (raw["confidence"].str.lower().isin(["n", "h"]))
        & (raw["frp"] >= 0.5)
    )
    df = raw[mask].drop_duplicates(
        subset=["latitude", "longitude", "acq_date", "acq_time"], keep="first"
    ).copy()
    print(f"Filtered: {len(raw):,} -> {len(df):,}")

    # Planck fitting
    print("Running Planck fitting...")
    df["Temp_primary"], df["Area_primary"] = estimate_fire_params(
        df["bright_ti4"].values, df["bright_ti5"].values, df["frp"].values
    )
    df["Temp_class"] = pd.cut(
        df["Temp_primary"], bins=[0, 1000, 1450, 9999],
        labels=["Low", "Medium", "High"],
    )

    # Assign country via spatial join
    world = gpd.read_file(
        "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    )
    borders = world[world["NAME"].isin(country_bbox.keys())][["NAME", "geometry"]]
    borders = borders.rename(columns={"NAME": "country"})

    gdf = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs="EPSG:4326"
    )
    gdf = gpd.sjoin(gdf, borders, how="inner", predicate="within")
    df = gdf.drop(columns=["geometry", "index_right"]).copy()

    df["acq_date"] = pd.to_datetime(df["acq_date"])
    df["month"] = df["acq_date"].dt.to_period("M")

    # Flare volume: ~1000 m³/day per MW FRP, 12h effective, to MCF
    df["flare_volume_mcf"] = df["frp"] * 1000 * 35.3147 * 12 / 1e6

    print(f"Result: {len(df):,} detections, {df['country'].nunique()} countries")
    return df


def build_monthly_timeseries(df):
    """Monthly detection counts per country. Returns wide DataFrame (index=month, cols=countries)."""
    ts = df.groupby(["month", "country"]).size().unstack(fill_value=0)
    ts.index = ts.index.to_timestamp()
    ts = ts[ts.sum().sort_values(ascending=False).index]
    return ts


def apply_scale_factors(timeseries, scale_factors):
    """
    Scale monthly time series per country.
    scale_factors: dict {country: multiplier} e.g. {"Iran": 1.5, "Iraq": 0.8}
    Multiplier 1.0 = no change. Unmentioned countries keep original values.
    """
    result = timeseries.copy()
    for country, factor in scale_factors.items():
        if country in result.columns:
            result[country] = (result[country] * factor).round().astype(int)
    return result


def plot_timeseries_bars(timeseries, title="Gulf States — Monthly Flare Detections",
                         save_path=None):
    """Grouped bar chart: monthly detections per country (time series)."""
    plt.rcParams.update(DARK_STYLE)
    countries = timeseries.columns.tolist()
    months = timeseries.index
    n_countries = len(countries)
    n_months = len(months)

    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(n_months)
    total_width = 0.8
    w = total_width / n_countries

    for i, country in enumerate(countries):
        offset = (i - n_countries / 2 + 0.5) * w
        color = COUNTRY_COLORS.get(country, "#888")
        ax.bar(x + offset, timeseries[country], w,
               label=country, color=color, edgecolor="#0d1117", linewidth=0.3)

    ax.set_xticks(x)
    ax.set_xticklabels([m.strftime("%b\n%Y") for m in months], fontsize=9)
    ax.set_ylabel("Flare detections / month")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.legend(loc="upper right", fontsize=9, facecolor="#161b22", edgecolor="#333")
    ax.grid(axis="y", color="#21262d", linewidth=0.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.show()


def plot_hightemp_map(df, date_start, date_end, save_path=None):
    """Map of high-temperature flares (> 1450 K) for a date range."""
    plt.rcParams.update(DARK_STYLE)

    hi = df[
        (df["Temp_class"] == "High")
        & (df["acq_date"] >= date_start)
        & (df["acq_date"] <= date_end)
    ].copy()
    print(f"High-temp detections {date_start} to {date_end}: {len(hi)}")

    world = gpd.read_file(
        "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    )
    gulf = world.cx[43:61, 15:37]

    fig, ax = plt.subplots(figsize=(14, 10))
    gulf.plot(ax=ax, color="#161b22", edgecolor="#30363d", linewidth=0.7)

    for _, row in gulf.iterrows():
        cx, cy = row.geometry.centroid.x, row.geometry.centroid.y
        if 43 < cx < 61 and 15 < cy < 37:
            ax.text(cx, cy, row["NAME"], fontsize=8, color="#484f58",
                    ha="center", style="italic")

    if not hi.empty:
        ax.scatter(hi["longitude"], hi["latitude"],
                   c="#ff6600", s=12, alpha=0.8,
                   edgecolors="#ffcc00", linewidths=0.4, zorder=5)

    ax.set_xlim(43, 61)
    ax.set_ylim(15, 37)
    ax.set_title(
        f"High Temperature Flares (> 1450 K) — {date_start} to {date_end}\n"
        f"{len(hi)} detections",
        fontsize=13, fontweight="bold", pad=12,
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.show()


def export_csv(df_or_ts, path):
    """Export DataFrame/time series to CSV."""
    out = df_or_ts.copy()
    out.to_csv(path)
    print(f"Exported: {path}")
