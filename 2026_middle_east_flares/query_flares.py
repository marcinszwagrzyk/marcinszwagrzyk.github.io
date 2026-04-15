"""
Query and analyze the gas flare database.

Usage:
    python query_flares.py --country kuwait --date 2025-01-15
    python query_flares.py --country iraq --month 2025-06
    python query_flares.py --stats
    python query_flares.py --country kuwait --export csv
"""

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

from config import GPKG_PATH


def load_flares(gpkg_path: str, layer: str = None) -> gpd.GeoDataFrame:
    """Load flare data from GeoPackage. If layer not specified, tries common names."""
    path = Path(gpkg_path)
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}. Run download_firms.py first.")

    import fiona
    layers = fiona.listlayers(str(path))
    print(f"Available layers: {layers}")

    if layer:
        return gpd.read_file(path, layer=layer)

    # Try to load all flare layers and merge
    gdfs = []
    for lyr in layers:
        if lyr.startswith("flares"):
            gdfs.append(gpd.read_file(path, layer=lyr))

    if not gdfs:
        return gpd.read_file(path, layer=layers[0])
    return pd.concat(gdfs, ignore_index=True)


def query_by_country(gdf: gpd.GeoDataFrame, country: str) -> gpd.GeoDataFrame:
    """Filter flares for a specific country."""
    return gdf[gdf["country"] == country.lower()].copy()


def query_by_date(gdf: gpd.GeoDataFrame, date: str) -> gpd.GeoDataFrame:
    """Filter flares for a specific date (YYYY-MM-DD)."""
    return gdf[gdf["acq_date"] == date].copy()


def query_by_month(gdf: gpd.GeoDataFrame, month: str) -> gpd.GeoDataFrame:
    """Filter flares for a specific month (YYYY-MM)."""
    return gdf[gdf["acq_date"].str.startswith(month)].copy()


def print_stats(gdf: gpd.GeoDataFrame):
    """Print summary statistics for the flare database."""
    print(f"\n{'='*60}")
    print(f"GAS FLARE DATABASE STATISTICS")
    print(f"{'='*60}")
    print(f"Total detections: {len(gdf):,}")

    if "acq_date" in gdf.columns:
        print(f"Date range: {gdf['acq_date'].min()} to {gdf['acq_date'].max()}")
        print(f"Unique dates: {gdf['acq_date'].nunique()}")

    if "country" in gdf.columns:
        print(f"\nDetections by country:")
        country_stats = gdf.groupby("country").agg(
            count=("country", "size"),
            avg_frp=("frp", "mean") if "frp" in gdf.columns else ("country", "size"),
            max_frp=("frp", "max") if "frp" in gdf.columns else ("country", "size"),
        ).sort_values("count", ascending=False)
        print(country_stats.to_string())

    if "bright_ti4" in gdf.columns:
        print(f"\nBrightness Temperature (I4 band):")
        print(f"  Mean: {gdf['bright_ti4'].mean():.1f} K")
        print(f"  Max:  {gdf['bright_ti4'].max():.1f} K")

    if "frp" in gdf.columns:
        print(f"\nFire Radiative Power:")
        print(f"  Mean: {gdf['frp'].mean():.2f} MW")
        print(f"  Max:  {gdf['frp'].max():.2f} MW")
        print(f"  Sum:  {gdf['frp'].sum():.2f} MW")


def plot_flares(gdf: gpd.GeoDataFrame, title: str = "Gas Flares"):
    """Plot flare locations on a map, sized by FRP."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))

    # Base: country boundaries from Natural Earth via geopandas
    try:
        world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
        me_bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        pad = 2
        world_clip = world.cx[
            me_bounds[0] - pad : me_bounds[2] + pad,
            me_bounds[1] - pad : me_bounds[3] + pad,
        ]
        world_clip.plot(ax=ax, color="#1a1a2e", edgecolor="#333", linewidth=0.5)
    except Exception:
        pass

    # Flares sized by FRP
    size_col = "frp" if "frp" in gdf.columns else None
    if size_col:
        sizes = gdf[size_col].clip(lower=1) * 2
    else:
        sizes = 5

    gdf.plot(
        ax=ax,
        markersize=sizes,
        color="#ff6600",
        alpha=0.6,
        edgecolor="#ffaa00",
        linewidth=0.3,
    )

    ax.set_title(title, fontsize=16, fontweight="bold", color="white")
    ax.set_facecolor("#0d1117")
    fig.set_facecolor("#0d1117")
    ax.tick_params(colors="gray")
    for spine in ax.spines.values():
        spine.set_color("#333")

    plt.tight_layout()
    plt.savefig("data/flares_map.png", dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.show()
    print("Map saved to data/flares_map.png")


def plot_time_series(gdf: gpd.GeoDataFrame, country: str = None):
    """Plot daily flare count and total FRP over time."""
    if "acq_date" not in gdf.columns:
        return

    data = gdf.copy()
    if country:
        data = data[data["country"] == country.lower()]

    daily = data.groupby("acq_date").agg(
        count=("acq_date", "size"),
        total_frp=("frp", "sum") if "frp" in data.columns else ("acq_date", "size"),
    )
    daily.index = pd.to_datetime(daily.index)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    label = country.title() if country else "Middle East"

    ax1.bar(daily.index, daily["count"], color="#ff6600", alpha=0.8)
    ax1.set_ylabel("Detections/day")
    ax1.set_title(f"Gas Flare Activity - {label}", fontsize=14)

    if "total_frp" in daily.columns:
        ax2.bar(daily.index, daily["total_frp"], color="#ff3300", alpha=0.8)
        ax2.set_ylabel("Total FRP (MW)")

    for ax in [ax1, ax2]:
        ax.set_facecolor("#0d1117")
        ax.tick_params(colors="gray")
    fig.set_facecolor("#0d1117")

    plt.tight_layout()
    plt.savefig("data/flares_timeseries.png", dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.show()


def find_persistent_flares(gdf: gpd.GeoDataFrame, min_days: int = 5, radius_deg: float = 0.01):
    """
    Identify persistent flare locations (likely oil/gas infrastructure).
    Groups nearby detections and counts unique dates.
    """
    if gdf.empty:
        return gpd.GeoDataFrame()

    # Round coordinates to cluster nearby detections (~1km at equator)
    gdf = gdf.copy()
    gdf["lat_round"] = (gdf.geometry.y / radius_deg).round() * radius_deg
    gdf["lon_round"] = (gdf.geometry.x / radius_deg).round() * radius_deg
    gdf["cluster_id"] = gdf["lat_round"].astype(str) + "_" + gdf["lon_round"].astype(str)

    clusters = gdf.groupby("cluster_id").agg(
        lat=("latitude", "mean"),
        lon=("longitude", "mean"),
        num_detections=("cluster_id", "size"),
        num_days=("acq_date", "nunique"),
        mean_frp=("frp", "mean") if "frp" in gdf.columns else ("cluster_id", "size"),
        max_frp=("frp", "max") if "frp" in gdf.columns else ("cluster_id", "size"),
        mean_temp=("bright_ti4", "mean") if "bright_ti4" in gdf.columns else ("cluster_id", "size"),
        country=("country", "first"),
        first_seen=("acq_date", "min"),
        last_seen=("acq_date", "max"),
    ).reset_index()

    # Filter for persistent sources
    persistent = clusters[clusters["num_days"] >= min_days].copy()
    persistent = gpd.GeoDataFrame(
        persistent,
        geometry=gpd.points_from_xy(persistent["lon"], persistent["lat"]),
        crs="EPSG:4326",
    )
    persistent = persistent.sort_values("num_detections", ascending=False)

    print(f"\nPersistent flare sites (>={min_days} days): {len(persistent)}")
    if not persistent.empty:
        print(persistent[["country", "num_detections", "num_days", "mean_frp", "max_frp",
                          "first_seen", "last_seen"]].head(20).to_string())

    return persistent


def main():
    parser = argparse.ArgumentParser(description="Query gas flare database")
    parser.add_argument("--country", type=str, help="Filter by country")
    parser.add_argument("--date", type=str, help="Filter by date YYYY-MM-DD")
    parser.add_argument("--month", type=str, help="Filter by month YYYY-MM")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--plot", action="store_true", help="Plot flare map")
    parser.add_argument("--timeseries", action="store_true", help="Plot time series")
    parser.add_argument("--persistent", action="store_true", help="Find persistent flare sites")
    parser.add_argument("--min-days", type=int, default=5, help="Min days for persistent sites")
    parser.add_argument("--export", type=str, choices=["csv", "geojson"], help="Export format")
    parser.add_argument("--layer", type=str, help="GeoPackage layer name")
    args = parser.parse_args()

    gdf = load_flares(GPKG_PATH, layer=args.layer)
    print(f"Loaded {len(gdf):,} records")

    # Apply filters
    if args.country:
        gdf = query_by_country(gdf, args.country)
        print(f"Country filter ({args.country}): {len(gdf):,} records")

    if args.date:
        gdf = query_by_date(gdf, args.date)
        print(f"Date filter ({args.date}): {len(gdf):,} records")

    if args.month:
        gdf = query_by_month(gdf, args.month)
        print(f"Month filter ({args.month}): {len(gdf):,} records")

    if gdf.empty:
        print("No data matching filters.")
        return

    # Actions
    if args.stats:
        print_stats(gdf)

    if args.plot:
        title = f"Gas Flares"
        if args.country:
            title += f" - {args.country.title()}"
        if args.date:
            title += f" ({args.date})"
        elif args.month:
            title += f" ({args.month})"
        plot_flares(gdf, title)

    if args.timeseries:
        plot_time_series(gdf, args.country)

    if args.persistent:
        persistent = find_persistent_flares(gdf, min_days=args.min_days)
        if not persistent.empty and args.export:
            out = f"data/persistent_flares_{args.country or 'all'}.{args.export}"
            if args.export == "csv":
                persistent.drop(columns="geometry").to_csv(out, index=False)
            else:
                persistent.to_file(out, driver="GeoJSON")
            print(f"Exported to {out}")

    if args.export and not args.persistent:
        out = f"data/flares_{args.country or 'all'}.{args.export}"
        if args.export == "csv":
            gdf.drop(columns="geometry").to_csv(out, index=False)
        else:
            gdf.to_file(out, driver="GeoJSON")
        print(f"Exported to {out}")

    if not any([args.stats, args.plot, args.timeseries, args.persistent, args.export]):
        print_stats(gdf)


if __name__ == "__main__":
    main()
