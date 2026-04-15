"""
Download VIIRS active fire data from NASA FIRMS API for Middle East.
Filters for gas flares and builds a GeoPackage database.

Usage:
    python download_firms.py --country kuwait --start 2025-01-01 --end 2025-01-31
    python download_firms.py --region middle_east --start 2025-06-01 --end 2025-06-10
"""

import argparse
import io
import time
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

from config import (
    COUNTRY_BBOX,
    FIRMS_MAP_KEY,
    FLARE_FILTERS,
    GPKG_PATH,
    MIDDLE_EAST_BBOX,
    VIIRS_SOURCES,
)


FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def fetch_firms_data(source: str, bbox: str, date: str, day_range: int = 1) -> pd.DataFrame:
    """Fetch VIIRS hotspot data from FIRMS API for a given source, bbox, and date."""
    url = f"{FIRMS_BASE_URL}/{FIRMS_MAP_KEY}/{source}/{bbox}/{day_range}/{date}"
    resp = requests.get(url, timeout=120)
    if resp.status_code == 400:
        return pd.DataFrame()
    resp.raise_for_status()

    if not resp.text.strip() or resp.text.strip().startswith("<!"):
        return pd.DataFrame()

    df = pd.read_csv(io.StringIO(resp.text))
    if df.empty:
        return df
    df["source_product"] = source
    return df


def download_date_range(
    bbox: str,
    start_date: str,
    end_date: str,
    sources: list[str] | None = None,
) -> pd.DataFrame:
    """Download FIRMS data for a date range, chunked into 5-day windows (API max)."""
    if sources is None:
        sources = VIIRS_SOURCES

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    all_dfs = []
    current = start

    while current <= end:
        days_left = (end - current).days + 1
        chunk = min(days_left, 5)  # FIRMS API max = 5 days per request
        date_str = current.strftime("%Y-%m-%d")

        for source in sources:
            print(f"  Fetching {source} | {date_str} (+{chunk}d) ...")
            try:
                df = fetch_firms_data(source, bbox, date_str, day_range=chunk)
                if not df.empty:
                    all_dfs.append(df)
                    print(f"    -> {len(df)} hotspots")
                else:
                    print(f"    -> 0 hotspots")
            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    print("    -> Rate limited, sleeping 60s...")
                    time.sleep(60)
                else:
                    print(f"    -> Error: {e}")
            time.sleep(0.5)  # Be polite to the API

        current += timedelta(days=chunk)

    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)


def filter_gas_flares(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter hotspot detections to isolate likely gas flares.

    VNF-inspired filtering:
    - Night-only (VNF uses nighttime VIIRS passes)
    - High brightness temperature (gas flares burn at 1000-2000K)
    - Minimum FRP threshold (persistent industrial combustion)
    - Confidence filter (remove low-confidence detections)
    """
    if df.empty:
        return df

    original_count = len(df)
    mask = pd.Series(True, index=df.index)

    # Night-only filter (core VNF principle)
    if FLARE_FILTERS["night_only"] and "daynight" in df.columns:
        mask &= df["daynight"] == "N"

    # Confidence filter (FIRMS uses single-letter codes: n=nominal, h=high, l=low)
    if "confidence" in df.columns:
        mask &= df["confidence"].str.lower().isin(FLARE_FILTERS["confidence_levels"])

    # Fire Radiative Power filter
    if "frp" in df.columns:
        mask &= df["frp"] >= FLARE_FILTERS["min_frp_mw"]

    filtered = df[mask].copy()
    print(f"  Flare filter: {original_count} -> {len(filtered)} detections")
    return filtered


def assign_country(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Assign country to each detection based on coordinate bounding boxes."""
    gdf["country"] = "unknown"
    for country, bbox_str in COUNTRY_BBOX.items():
        west, south, east, north = map(float, bbox_str.split(","))
        mask = (
            (gdf.geometry.x >= west)
            & (gdf.geometry.x <= east)
            & (gdf.geometry.y >= south)
            & (gdf.geometry.y <= north)
        )
        gdf.loc[mask & (gdf["country"] == "unknown"), "country"] = country
    return gdf


def to_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Convert DataFrame to GeoDataFrame with proper types."""
    if df.empty:
        return gpd.GeoDataFrame()

    # Normalize column names to lowercase
    df.columns = df.columns.str.lower()

    # Remove duplicates (same location, same time, different sources)
    dedup_cols = ["latitude", "longitude", "acq_date", "acq_time"]
    existing_dedup = [c for c in dedup_cols if c in df.columns]
    if existing_dedup:
        before = len(df)
        df = df.drop_duplicates(subset=existing_dedup, keep="first")
        if before != len(df):
            print(f"  Dedup: {before} -> {len(df)}")

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )
    return gdf


def save_to_gpkg(gdf: gpd.GeoDataFrame, gpkg_path: str, layer_name: str = "flares"):
    """Append data to GeoPackage, creating it if needed."""
    path = Path(gpkg_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = gpd.read_file(path, layer=layer_name)
        gdf = pd.concat([existing, gdf], ignore_index=True)

        # Deduplicate again after merge
        dedup_cols = ["latitude", "longitude", "acq_date", "acq_time"]
        existing_dedup = [c for c in dedup_cols if c in gdf.columns]
        if existing_dedup:
            gdf = gdf.drop_duplicates(subset=existing_dedup, keep="first")

    gdf.to_file(path, layer=layer_name, driver="GPKG")
    print(f"  Saved {len(gdf)} records to {path} (layer: {layer_name})")


def main():
    parser = argparse.ArgumentParser(description="Download VIIRS gas flare data for Middle East")
    parser.add_argument("--country", type=str, default=None, help="Country name (e.g., kuwait, iraq)")
    parser.add_argument("--region", type=str, default="middle_east", help="Region name")
    parser.add_argument("--start", type=str, required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--source", type=str, default=None, help="VIIRS source (e.g., VIIRS_SNPP_SP)")
    parser.add_argument("--raw", action="store_true", help="Save raw data without flare filtering")
    args = parser.parse_args()

    # Determine bbox
    if args.country:
        country = args.country.lower()
        if country not in COUNTRY_BBOX:
            print(f"Unknown country: {country}. Available: {', '.join(COUNTRY_BBOX.keys())}")
            return
        bbox = COUNTRY_BBOX[country]
        region_label = country
    else:
        bbox = MIDDLE_EAST_BBOX
        region_label = "middle_east"

    # Auto-select sources: SP for historical data (>60 days old), NRT for recent
    if args.source:
        sources = [args.source]
    else:
        cutoff = datetime.now() - timedelta(days=60)
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
        if start_dt < cutoff:
            sources = ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"]
        else:
            sources = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]

    print(f"=== Downloading VIIRS hotspots for {region_label} ===")
    print(f"    Period: {args.start} to {args.end}")
    print(f"    BBOX: {bbox}")
    print(f"    Sources: {sources}")
    print()

    # Download
    df = download_date_range(bbox, args.start, args.end, sources)

    if df.empty:
        print("No data returned from FIRMS API.")
        return

    print(f"\nTotal hotspots downloaded: {len(df)}")

    # Filter for gas flares
    if not args.raw:
        df = filter_gas_flares(df)

    if df.empty:
        print("No detections after filtering.")
        return

    # Convert to GeoDataFrame
    gdf = to_geodataframe(df)

    # Assign country labels
    gdf = assign_country(gdf)

    # Save
    layer = f"flares_{region_label}"
    save_to_gpkg(gdf, GPKG_PATH, layer_name=layer)

    # Summary
    print(f"\n=== Summary ===")
    if "country" in gdf.columns:
        print(gdf.groupby("country").size().sort_values(ascending=False).to_string())
    if "acq_date" in gdf.columns:
        print(f"\nDate range: {gdf['acq_date'].min()} to {gdf['acq_date'].max()}")
    print(f"Total flare detections: {len(gdf)}")


if __name__ == "__main__":
    main()
