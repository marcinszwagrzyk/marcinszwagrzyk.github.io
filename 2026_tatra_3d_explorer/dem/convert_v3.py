"""Convert koscielec_v3_dem.tif + koscielec_v3_orto.tif
DEM and ortho share identical extents — no compositing needed.
WGS84 corners (gdaltransform -s_srs EPSG:2180 -t_srs EPSG:4326):
  UL (572923.824, 152596.530) -> 20.0020703°E 49.2365304°N
  LR (574392.936, 150649.416) -> 20.0218932°E 49.2188363°N
"""
import sys, json
sys.path.insert(0,'C:/Users/marci/AppData/Local/Programs/OSGeo4W/apps/Python312/Lib/site-packages')
import warnings; warnings.filterwarnings('ignore')
from osgeo import gdal
import numpy as np
from PIL import Image

BASE      = 'C:/git/marcinszwagrzyk.github.io/2026_tatra_3d_explorer/dem/'
DEM_SRC   = BASE + 'koscielec_v3_dem.tif'
ORTO_SRC  = BASE + 'koscielec_v3_orto.tif'
OUT_PNG   = BASE + 'koscielec_v3_terrain_rgb.png'
OUT_META  = BASE + 'koscielec_v3_meta.json'
OUT_ORTO  = BASE + 'koscielec_v3_orto.jpg'

WEST  = 20.0017161047577
EAST  = 20.0222545526246
SOUTH = 49.2188362961219
NORTH = 49.2365304222403

# ── DEM → terrain-RGB ────────────────────────────────────────────────────────
ds  = gdal.Open(DEM_SRC)
gt  = ds.GetGeoTransform()
w, h = ds.RasterXSize, ds.RasterYSize
data = ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
elev_min, elev_max = float(data.min()), float(data.max())
res_m = (abs(gt[1]) + abs(gt[5])) / 2.0
print(f'DEM: {w}x{h}, elev {elev_min:.1f}–{elev_max:.1f} m, res {res_m:.4f} m/px')

encoded = np.clip(((data + 10000.0) / 0.1).astype(np.int64), 0, 16777215)
rgb = np.stack([
    ((encoded >> 16) & 0xFF).astype(np.uint8),
    ((encoded >>  8) & 0xFF).astype(np.uint8),
    ( encoded        & 0xFF).astype(np.uint8),
], axis=2)
Image.fromarray(rgb, mode='RGB').save(OUT_PNG)
print(f'Written: {OUT_PNG}')

# ── meta JSON ─────────────────────────────────────────────────────────────────
meta = {
    "elev_min": round(elev_min, 4),
    "elev_max": round(elev_max, 4),
    "width_px": w,
    "height_px": h,
    "res_m": round(res_m, 10),
    "bounds_wgs84": {"west": WEST, "south": SOUTH, "east": EAST, "north": NORTH}
}
with open(OUT_META, 'w') as f:
    json.dump(meta, f, indent=2)
print(f'Written: {OUT_META}')
print(json.dumps(meta, indent=2))

# ── Ortho → JPEG (same extent as DEM, just resample) ─────────────────────────
ods = gdal.Open(ORTO_SRC)
ow, oh = ods.RasterXSize, ods.RasterYSize
print(f'Ortho source: {ow}x{oh}')

def norm8(arr):
    mn, mx = float(arr.min()), float(arr.max())
    if mx > 1.5:
        return np.clip(arr, 0, 255).astype(np.uint8)
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)

bands = [norm8(ods.GetRasterBand(i+1).ReadAsArray()) for i in range(ods.RasterCount)]
if len(bands) == 1:
    bands = bands * 3  # grayscale → RGB
orto_img = Image.fromarray(np.stack(bands[:3], axis=2), mode='RGB')
# Resample to DEM pixel size (1469×1947 ≈ native 1m res)
orto_scaled = orto_img.resize((w, h), Image.LANCZOS)
orto_scaled.save(OUT_ORTO, quality=90)
print(f'Written: {OUT_ORTO}  ({w}x{h})')
