"""
prepare_koscielec.py — przetwarza koscielec_dem.tif + koscielec_orto.tif
Tworzy:
  dem/koscielec_terrain_rgb.png   (Mapbox terrain-RGB dla viewera)
  dem/koscielec_meta.json         (metadane)
  dem/koscielec_orto.jpg          (ortofoto 0.5m/px do viewera)

Uruchom w środowisku geo-toolbox:
  python prepare_koscielec.py
"""
import rasterio
from rasterio.warp import transform_bounds
from rasterio.enums import Resampling
import numpy as np
from PIL import Image
import json, os, math

DEM_PATH  = "dem/koscielec_dem.tif"
ORTO_PATH = "dem/koscielec_orto.tif"
OUT_DIR   = "dem"

# Bounds WGS84 z ortofoto (DEM nie ma CRS)
BOUNDS_WGS84 = {
    "west":  20.005382,
    "south": 49.221589,
    "east":  20.025604,
    "north": 49.229117
}

# ── 1. Wczytaj DEM ────────────────────────────────────────────────────────────
print("Wczytuję", DEM_PATH)
with rasterio.open(DEM_PATH) as src:
    data   = src.read(1).astype(np.float64)
    nodata = src.nodata
    width, height = src.width, src.height
    res_m  = abs(src.transform.a)

if nodata is not None:
    data[data == nodata] = np.nan

elev_min = float(np.nanmin(data))
elev_max = float(np.nanmax(data))
data_filled = np.where(np.isnan(data), elev_min, data)

print(f"  rozmiar: {width} × {height} px,  res: {res_m:.4f} m/px")
print(f"  wys. min/max: {elev_min:.1f} – {elev_max:.1f} m")

# ── 2. terrain-RGB PNG (Mapbox encoding) ──────────────────────────────────────
encoded = ((data_filled + 10000) / 0.1).astype(np.int32)
R = ((encoded >> 16) & 0xFF).astype(np.uint8)
G = ((encoded >>  8) & 0xFF).astype(np.uint8)
B = ( encoded        & 0xFF).astype(np.uint8)
out_png = os.path.join(OUT_DIR, "koscielec_terrain_rgb.png")
Image.fromarray(np.stack([R, G, B], axis=-1), 'RGB').save(out_png)
print(f"Zapisano {out_png}")

# ── 3. Metadane JSON ──────────────────────────────────────────────────────────
meta = {
    "elev_min":    elev_min,
    "elev_max":    elev_max,
    "width_px":    width,
    "height_px":   height,
    "res_m":       res_m,
    "bounds_wgs84": BOUNDS_WGS84
}
out_json = os.path.join(OUT_DIR, "koscielec_meta.json")
with open(out_json, "w") as f:
    json.dump(meta, f, indent=2)
print(f"Zapisano {out_json}")

# ── 4. Ortofoto → JPG (resample do 0.5 m/px) ─────────────────────────────────
print(f"Konwertuję {ORTO_PATH} → koscielec_orto.jpg (0.5m/px)…")
with rasterio.open(ORTO_PATH) as src:
    orto_res = abs(src.transform.a)
    scale    = orto_res / 0.5          # np. 0.05/0.5 = 0.1 → 10x downscale
    new_w    = max(1, int(src.width  * scale))
    new_h    = max(1, int(src.height * scale))
    print(f"  {src.width}×{src.height} @ {orto_res:.3f}m → {new_w}×{new_h} @ 0.5m")

    data_orto = src.read(
        out_shape=(src.count, new_h, new_w),
        resampling=Resampling.lanczos
    )

bands = data_orto.shape[0]
if bands >= 3:
    rgb = np.stack([data_orto[0], data_orto[1], data_orto[2]], axis=-1)
else:
    rgb = np.stack([data_orto[0]] * 3, axis=-1)

rgb = rgb.astype(np.uint8)
out_jpg = os.path.join(OUT_DIR, "koscielec_orto.jpg")
Image.fromarray(rgb, 'RGB').save(out_jpg, quality=88, optimize=True)
size_mb = os.path.getsize(out_jpg) / 1024 / 1024
print(f"Zapisano {out_jpg} ({size_mb:.1f} MB)")

print()
print("Następny krok:")
print("  python prepare_koscielec.py  (jeśli jeszcze nie uruchomiony)")
print("  Otwórz viewer_koscielec.html")
