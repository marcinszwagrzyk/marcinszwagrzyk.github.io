"""
Prepare DEM for web viewers:
- terrain-RGB PNG (Mapbox encoding) for Deck.gl
- 16-bit grayscale PNG for Three.js
- metadata JSON with WGS84 bounds
"""
import rasterio
from rasterio.warp import transform_bounds
import numpy as np
from PIL import Image
import json, os

DEM_PATH = "dem/zamarla.tif"
OUT_DIR = "dem"

with rasterio.open(DEM_PATH) as src:
    data = src.read(1)
    nodata = src.nodata
    bounds_2180 = src.bounds
    crs = src.crs
    width, height = src.width, src.height

    # Convert bounds to WGS84
    bounds_wgs84 = transform_bounds(crs, "EPSG:4326", *bounds_2180)
    # bounds_wgs84: (west, south, east, north)

# Replace nodata with NaN then fill with min
data = data.astype(np.float64)
if nodata is not None:
    data[data == nodata] = np.nan

elev_min = float(np.nanmin(data))
elev_max = float(np.nanmax(data))

# Fill NaN with min elevation
data_filled = np.where(np.isnan(data), elev_min, data)

# --- 16-bit grayscale for Three.js ---
norm = (data_filled - elev_min) / (elev_max - elev_min)
gray16 = (norm * 65535).astype(np.uint16)
img16 = Image.fromarray(gray16, mode='I;16')
img16.save(os.path.join(OUT_DIR, "zamarla_gray16.png"))
print("Saved zamarla_gray16.png")

# --- terrain-RGB (Mapbox encoding) for Deck.gl ---
# height = -10000 + (R*256*256 + G*256 + B) * 0.1
# => encoded = (height + 10000) / 0.1
encoded = ((data_filled + 10000) / 0.1).astype(np.int32)
R = ((encoded >> 16) & 0xFF).astype(np.uint8)
G = ((encoded >> 8) & 0xFF).astype(np.uint8)
B = (encoded & 0xFF).astype(np.uint8)
rgb = np.stack([R, G, B], axis=-1)
img_rgb = Image.fromarray(rgb, mode='RGB')
img_rgb.save(os.path.join(OUT_DIR, "zamarla_terrain_rgb.png"))
print("Saved zamarla_terrain_rgb.png")

# --- metadata ---
meta = {
    "bounds_wgs84": {
        "west": bounds_wgs84[0],
        "south": bounds_wgs84[1],
        "east": bounds_wgs84[2],
        "north": bounds_wgs84[3]
    },
    "center_wgs84": {
        "lng": (bounds_wgs84[0] + bounds_wgs84[2]) / 2,
        "lat": (bounds_wgs84[1] + bounds_wgs84[3]) / 2
    },
    "elev_min": elev_min,
    "elev_max": elev_max,
    "width_px": width,
    "height_px": height,
    "res_m": 0.5,
    "vertical_exaggeration": 4.0
}
with open(os.path.join(OUT_DIR, "meta.json"), "w") as f:
    json.dump(meta, f, indent=2)
print("Saved meta.json")
print(f"Bounds WGS84: {bounds_wgs84}")
print(f"Center: {meta['center_wgs84']}")
print(f"Elevation: {elev_min:.1f} – {elev_max:.1f} m")
