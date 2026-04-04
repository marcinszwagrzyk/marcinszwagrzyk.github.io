"""Convert koscielec_v2.tif (Float32, PUWG1992) to:
 - koscielec_v2_terrain_rgb.png  (Mapbox terrain-RGB encoding)
 - koscielec_v2_meta.json        (bounds in WGS84 + stats)

The TIF has no embedded CRS but is in EPSG:2180 (PUWG1992).
Bounds were pre-computed with gdaltransform -s_srs EPSG:2180 -t_srs EPSG:4326.
"""
import sys, json
sys.path.insert(0,'C:/Users/marci/AppData/Local/Programs/OSGeo4W/apps/Python312/Lib/site-packages')
import warnings; warnings.filterwarnings('ignore')
from osgeo import gdal, osr
import numpy as np

SRC     = 'C:/git/marcinszwagrzyk.github.io/2026_tatra_3d_explorer/dem/koscielec_v2.tif'
OUT_PNG = 'C:/git/marcinszwagrzyk.github.io/2026_tatra_3d_explorer/dem/koscielec_v2_terrain_rgb.png'
OUT_META= 'C:/git/marcinszwagrzyk.github.io/2026_tatra_3d_explorer/dem/koscielec_v2_meta.json'

# Corners from: gdaltransform -s_srs EPSG:2180 -t_srs EPSG:4326
# UL (573377.264, 152037.594) -> lon=20.00820, lat=49.23145
# UR (574161.878, 152037.594) -> lon=20.01898, lat=49.23135
# LL (573377.264, 151020.135) -> lon=20.00801, lat=49.22229
# LR (574161.878, 151020.135) -> lon=20.01879, lat=49.22220
WEST  = 20.0080115989863
EAST  = 20.0189765994448
SOUTH = 49.2221995200785
NORTH = 49.231447711263

# --- read source ---
ds = gdal.Open(SRC)
gt = ds.GetGeoTransform()
w, h = ds.RasterXSize, ds.RasterYSize
data = ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
elev_min = float(data.min())
elev_max = float(data.max())
res_m = (abs(gt[1]) + abs(gt[5])) / 2.0
print(f'Size: {w} x {h},  Elev: {elev_min:.2f} – {elev_max:.2f} m')

# --- Mapbox terrain-RGB encoding ---
# height = -10000 + (R*65536 + G*256 + B) * 0.1
# => encoded = (height + 10000) / 0.1
encoded = ((data + 10000.0) / 0.1).astype(np.int64)
encoded = np.clip(encoded, 0, 16777215)

R = ((encoded >> 16) & 0xFF).astype(np.uint8)
G = ((encoded >>  8) & 0xFF).astype(np.uint8)
B = ( encoded        & 0xFF).astype(np.uint8)

# Stack to HxWx3
rgb = np.stack([R, G, B], axis=2)

# Write PNG via Pillow
from PIL import Image
img = Image.fromarray(rgb, mode='RGB')
img.save(OUT_PNG)
print(f'Written: {OUT_PNG}')

# Verify round-trip on a few pixels
sample_rows = [0, h//2, h-1]
sample_cols = [0, w//2, w-1]
for r in sample_rows:
    for c in sample_cols:
        orig = data[r, c]
        enc  = int(R[r,c])*65536 + int(G[r,c])*256 + int(B[r,c])
        decoded = -10000.0 + enc * 0.1
        err = abs(orig - decoded)
        print(f'  [{r},{c}] orig={orig:.2f} decoded={decoded:.2f} err={err:.3f}')

# --- write meta JSON ---
meta = {
    "elev_min": round(elev_min, 4),
    "elev_max": round(elev_max, 4),
    "width_px": w,
    "height_px": h,
    "res_m": round(res_m, 10),
    "bounds_wgs84": {
        "west":  WEST,
        "south": SOUTH,
        "east":  EAST,
        "north": NORTH
    }
}

with open(OUT_META, 'w') as f:
    json.dump(meta, f, indent=2)
print(f'Written: {OUT_META}')
print(json.dumps(meta, indent=2))
