"""Convert gasienicowa_dem.tif + gasienicowa_orto.tif
DEM 2116x2136, res ~1m, EPSG:2180 (ETRF2000-PL/CS92)
Ortho 2222x2243, slightly larger extent → crop to DEM extent

EPSG:2180 axis order: (Northing, Easting) → TransformPoint(gt[3], gt[0])
WGS84 (OAMS_TRADITIONAL_GIS_ORDER): lon, lat

WGS84 bounds (computed):
  UL: lon=20.0069023  lat=49.2365346
  LR: lon=20.0355683  lat=49.2170569
"""
import sys, json
sys.path.insert(0,'C:/Users/marci/AppData/Local/Programs/OSGeo4W/apps/Python312/Lib/site-packages')
import warnings; warnings.filterwarnings('ignore')
from osgeo import gdal
import numpy as np
from PIL import Image

BASE      = 'C:/git/marcinszwagrzyk.github.io/2026_tatra_3d_explorer/dem/'
DEM_SRC   = BASE + 'gasienicowa_dem.tif'
ORTO_SRC  = BASE + 'gasienicowa_orto.tif'
OUT_PNG   = BASE + 'gasienicowa_terrain_rgb.png'
OUT_META  = BASE + 'gasienicowa_meta.json'
OUT_ORTO  = BASE + 'gasienicowa_orto.jpg'

WEST  = 20.0069023
EAST  = 20.0355683
SOUTH = 49.2170569
NORTH = 49.2365346

# ── DEM → terrain-RGB ────────────────────────────────────────────────────────
ds  = gdal.Open(DEM_SRC)
gt  = ds.GetGeoTransform()
w, h = ds.RasterXSize, ds.RasterYSize
data = ds.GetRasterBand(1).ReadAsArray().astype(np.float64)
elev_min, elev_max = float(data.min()), float(data.max())
res_m = (abs(gt[1]) + abs(gt[5])) / 2.0
print(f'DEM: {w}x{h}, elev {elev_min:.1f}–{elev_max:.1f} m, res {res_m:.6f} m/px')

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

# ── Ortho → crop to DEM extent → JPEG ────────────────────────────────────────
ods = gdal.Open(ORTO_SRC)
ogt = ods.GetGeoTransform()
ow, oh = ods.RasterXSize, ods.RasterYSize
print(f'Ortho source: {ow}x{oh}, res_x={ogt[1]:.6f} res_y={ogt[5]:.6f}')

# DEM extent in source CRS (EPSG:2180, X=Easting, Y=Northing)
dem_ul_x, dem_ul_y = gt[0], gt[3]              # UL Easting, UL Northing
dem_lr_x = gt[0] + gt[1] * w                   # LR Easting
dem_lr_y = gt[3] + gt[5] * h                   # LR Northing (negative step)

# Ortho pixel coordinates corresponding to DEM corners
o_col0 = (dem_ul_x - ogt[0]) / ogt[1]
o_row0 = (dem_ul_y - ogt[3]) / ogt[5]
o_col1 = (dem_lr_x - ogt[0]) / ogt[1]
o_row1 = (dem_lr_y - ogt[3]) / ogt[5]

col0 = max(0, int(round(o_col0)))
row0 = max(0, int(round(o_row0)))
col1 = min(ow, int(round(o_col1)))
row1 = min(oh, int(round(o_row1)))
print(f'Ortho crop: cols {col0}-{col1}, rows {row0}-{row1}  ({col1-col0}x{row1-row0})')

def norm8(arr):
    mn, mx = float(arr.min()), float(arr.max())
    if mx > 1.5:
        return np.clip(arr, 0, 255).astype(np.uint8)
    return (np.clip(arr, 0, 1) * 255).astype(np.uint8)

bands = [norm8(ods.GetRasterBand(i+1).ReadAsArray()) for i in range(ods.RasterCount)]
if len(bands) == 1:
    bands = bands * 3   # grayscale → RGB
orto_img = Image.fromarray(np.stack(bands[:3], axis=2), mode='RGB')

# Crop to DEM extent
orto_crop = orto_img.crop((col0, row0, col1, row1))
# Resize to DEM dimensions (width=w, height=h)
orto_scaled = orto_crop.resize((w, h), Image.LANCZOS)
orto_scaled.save(OUT_ORTO, quality=90)
print(f'Written: {OUT_ORTO}  ({w}x{h})')
