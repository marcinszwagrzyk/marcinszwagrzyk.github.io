"""
Konwertuje markers/zamarla_markery.gpkg → markers.json
Uruchom po każdej edycji GPKG w QGIS:
    python gpkg_to_json.py
"""
import json
import geopandas as gpd
from pathlib import Path

GPKG = Path(__file__).parent / "markers" / "zamarla_markery.gpkg"
OUT  = Path(__file__).parent / "markers.json"

KNOWN_TYPES = {"szczyt", "przelecz", "stanowisko", "droga", "punkt", "zjazd"}

def _infer_type(row):
    t = str(row.get("type") or "").strip().lower()
    if t in KNOWN_TYPES:
        return t
    name = str(row.get("name") or "").lower()
    for kw in ("szczyt", "sczyt", "turnia", "wierch"):
        if kw in name:
            return "szczyt"
    for kw in ("przelecz", "przel"):
        if kw in name:
            return "przelecz"
    if "stanowisko" in name:
        return "stanowisko"
    if "zjazd" in name:
        return "zjazd"
    if "droga" in name:
        return "droga"
    return "punkt"

gdf = gpd.read_file(GPKG)
if gdf.crs and gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)

markers = []
for i, row in gdf.iterrows():
    markers.append({
        "id":          str(row.get("id") or f"marker_{i}"),
        "name":        str(row.get("name") or f"Punkt {i}"),
        "type":        _infer_type(row),
        "lat":         round(row.geometry.y, 7),
        "lon":         round(row.geometry.x, 7),
        "elevation_m": float(row["elevation_m"]) if row.get("elevation_m") is not None else 0,
        "description": str(row.get("description") or ""),
    })

result = {
    "_comment": "Wygenerowane automatycznie z zamarla_markery.gpkg – nie edytuj ręcznie.",
    "markers": markers
}

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Zapisano {len(markers)} markerow -> {OUT}")
