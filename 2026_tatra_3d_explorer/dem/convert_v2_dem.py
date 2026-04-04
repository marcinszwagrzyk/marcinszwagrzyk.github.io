"""Convert koscielec_v2_dem.tif (Float32, EPSG:2180, 1569x2836) to:
 - koscielec_v2_dem_terrain_rgb.png
 - koscielec_v2_dem_meta.json
 - koscielec_v2_dem_orto.jpg  (ortho composited to full DEM extent)

WGS84 corners (from gdaltransform -s_srs EPSG:2180 -t_srs EPSG:4326):
  UL (572922, 153245) → 20.0022°E 49.2424°N
  LR (574491, 150409) → 20.0232°E 49.2167°N

Ortho koscielec_v2_orto.tif PUWG1992 extent:
  UL (572922, 152670)  LR (574491, 150984)
  → covers DEM rows 575–2261 (of 2836 total)
"""
import sys, json
sys.path.insert(0,'C:/Users/marci/AppData/Local/Programs/OSGeo4W/apps/Python312/Lib/site-packages')
import warnings; warnings.filterwarnings('ignore')
from osgeo import gdal
import numpy as np
from PIL import Image

BASE     = 'C:/git/marcinszwagrzyk.github.io/2026_tatra_3d_explorer/dem/'
SRC      = BASE + 'koscielec_v2_dem.tif'
ORTO_SRC = BASE + 'koscielec_v2_orto.tif'
OUT_PNG  = BASE + 'koscielec_v2_dem_terrain_rgb.png'
OUT_META = BASE + 'koscielec_v2_dem_meta.json'
OUT_ORTO = BASE + 'koscielec_v2_dem_orto.jpg'

# Pre-computed WGS84 bounds (via gdaltransform, correct lon/lat order)
WEST  = 20.0021672335561
EAST  = 20.023729505103
NORTH = 49.2423647606394
SOUTH = 49.2166649243629

# ── terrain-RGB PNG ───────────────────────────────────────────────────────────
ds = gdal.Open(SRC)
gt = ds.GetGeoTransform()
w, h = ds.RasterXSize, ds.RasterYSize
data = ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
elev_min, elev_max = float(data.min()), float(data.max())
res_m = (abs(gt[1]) + abs(gt[5])) / 2.0
print(f'DEM: {w}x{h}, elev {elev_min:.1f}–{elev_max:.1f} m, res {res_m:.4f} m/px')

dem_ul_y = gt[3]          # northing of top edge
dem_res_y = abs(gt[5])    # ~1 m/px

encoded = ((data + 10000.0) / 0.1).astype(np.int64)
encoded = np.clip(encoded, 0, 16777215)
rgb = np.stack([
    ((encoded >> 16) & 0xFF).astype(np.uint8),
    ((encoded >>  8) & 0xFF).astype(np.uint8),
    ( encoded        & 0xFF).astype(np.uint8),
], axis=2)
Image.fromarray(rgb, mode='RGB').save(OUT_PNG)
print(f'Written terrain-RGB: {OUT_PNG}')

# ── meta JSON ─────────────────────────────────────────────────────────────────
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
print(f'Written meta: {OUT_META}')
print(json.dumps(meta, indent=2))

# ── ortho composited to DEM extent ───────────────────────────────────────────
# Ortho PUWG1992 extent: UL=(572922, 152670)  LR=(574491, 150984)
# DEM PUWG1992:          UL=(572922, 153245)  LR=(574491, 150409)
ORTO_TOP    = 152670.285   # northing of ortho top
ORTO_BOTTOM = 150984.124   # northing of ortho bottom

# Rows in DEM where ortho starts/ends (row 0 = DEM top = northing 153245)
row_start = int(round((dem_ul_y - ORTO_TOP)    / dem_res_y))   # ~575
row_end   = int(round((dem_ul_y - ORTO_BOTTOM)  / dem_res_y))  # ~2261
orto_h_dem = row_end - row_start   # height in DEM pixels
print(f'Ortho in DEM rows: {row_start}–{row_end}  (height {orto_h_dem} px)')

# Read ortho TIF (3-band RGB Float32 → uint8)
ods = gdal.Open(ORTO_SRC)
ow, oh = ods.RasterXSize, ods.RasterYSize
print(f'Ortho source: {ow}x{oh}')
R_o = ods.GetRasterBand(1).ReadAsArray().astype(np.float32)
G_o = ods.GetRasterBand(2).ReadAsArray().astype(np.float32)
B_o = ods.GetRasterBand(3).ReadAsArray().astype(np.float32)
# Normalise Float32 to uint8 (GIUK ortho may be float 0-255 or 0-1 range)
def norm8(arr):
    mn, mx = arr.min(), arr.max()
    if mx > 1.5:   # 0–255 range
        return np.clip(arr, 0, 255).astype(np.uint8)
    else:          # 0–1 range
        return (np.clip(arr, 0, 1) * 255).astype(np.uint8)
r8 = norm8(R_o); g8 = norm8(G_o); b8 = norm8(B_o)
orto_img = Image.fromarray(np.stack([r8,g8,b8],axis=2), mode='RGB')

# Scale ortho to fit exactly DEM-width × orto_h_dem
orto_scaled = orto_img.resize((w, orto_h_dem), Image.LANCZOS)

# Compose onto black canvas of DEM size
canvas = Image.new('RGB', (w, h), (0, 0, 0))
canvas.paste(orto_scaled, (0, row_start))

canvas.save(OUT_ORTO, quality=88)
print(f'Written ortho composite: {OUT_ORTO}')
