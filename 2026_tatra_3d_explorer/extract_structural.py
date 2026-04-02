"""
extract_structural.py — linie strukturalne Koscielca
Wynik: structural_lines/koscielec_structural.geojson
  - ridge      : grzbiety/granie (rzadkie, ostre)
  - cliff_edge : gorny skraj scian pionowych (slope>65 deg)
"""
import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter, distance_transform_edt, maximum_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json, os

DEM_PATH = "dem/koscielec_dem.tif"
OUT_DIR  = "structural_lines"
os.makedirs(OUT_DIR, exist_ok=True)

BOUNDS = {"west": 20.005382, "south": 49.221589,
          "east": 20.025604, "north": 49.229117}

# ── 1. Wczytaj DEM ────────────────────────────────────────────────────────────
with rasterio.open(DEM_PATH) as src:
    dem    = src.read(1).astype(np.float64)
    nodata = src.nodata
    rows, cols = dem.shape
    res    = abs(src.transform.a)

if nodata is not None:
    dem[dem == nodata] = np.nan
dem_fill = np.where(np.isnan(dem), np.nanmin(dem), dem)
print(f"DEM: {cols}x{rows} px, {res:.3f} m/px")

# ── 2. Helper px → WGS84 ─────────────────────────────────────────────────────
def to_wgs84(r, c):
    lon = BOUNDS["west"]  + (c / cols) * (BOUNDS["east"]  - BOUNDS["west"])
    lat = BOUNDS["north"] - (r / rows) * (BOUNDS["north"] - BOUNDS["south"])
    return [round(float(lon), 7), round(float(lat), 7)]

def contour_to_features(arr, level, props, step=5, min_pts=8, min_len_px=30):
    fig, ax = plt.subplots(1, 1)
    cs = ax.contour(arr, levels=[level])
    feats = []
    for seg in cs.allsegs[0]:
        if len(seg) < min_pts:
            continue
        seg_rc = np.column_stack([seg[:,1], seg[:,0]])   # (row, col)
        if len(seg_rc) < min_len_px:
            continue
        pts = seg_rc[::step]
        if len(pts) < 3:
            continue
        coords = [to_wgs84(r, c) for r, c in pts]
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": props.copy()
        })
    plt.close(fig)
    return feats

# ── 3. Plan curvature z mocnym wygładzeniem (tylko główne grzbiety) ───────────
def plan_curv(d, res):
    dx  = np.gradient(d, res, axis=1)
    dy  = np.gradient(d, res, axis=0)
    dxx = np.gradient(dx, res, axis=1)
    dyy = np.gradient(dy, res, axis=0)
    dxy = np.gradient(dx, res, axis=0)
    denom = dx**2 + dy**2 + 1e-9
    return -(dxx*dx**2 + 2*dxy*dx*dy + dyy*dy**2) / (denom * np.sqrt(denom))

def slope_deg(d, res):
    dx = np.gradient(d, res, axis=1)
    dy = np.gradient(d, res, axis=0)
    return np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

# ── 4. RIDGE LINES ────────────────────────────────────────────────────────────
# Silne wygładzenie → tylko główne grzbiety, bez szumu
print("Obliczam grzbiety...")
dem_r  = gaussian_filter(dem_fill, sigma=10.0)   # ~10m sigma → grube struktury
pc     = plan_curv(dem_r, res)
sl     = slope_deg(dem_r, res)

# Maska grzbietu: plan_curv > 90. percentyl i nachylenie > 8 deg
valid  = sl > 8.0
thresh_r = float(np.percentile(pc[valid], 90))
mask_r   = (pc > thresh_r) & valid

# Skeleton przez distance transform: lokalne maksima odległości = oś grzbietu
dist_r = distance_transform_edt(mask_r)
local_max_r = (dist_r == maximum_filter(dist_r, size=9)) & mask_r & (dist_r > 1.5)

# Rozmyj lekko żeby matplotlib.contour miał gładkie kontury
ridge_field = gaussian_filter(local_max_r.astype(float), sigma=2.0)

feats_ridge = contour_to_features(
    ridge_field, 0.15,
    {"type": "ridge", "color": "#ffe000", "stroke-width": 2},
    step=3, min_pts=6, min_len_px=20
)
print(f"  grzbiety: {len(feats_ridge)} segmentow")

# ── 5. CLIFF EDGE (gorny skraj scian pionowych) ───────────────────────────────
print("Obliczam krawedzie scian...")
dem_c  = gaussian_filter(dem_fill, sigma=3.0)
sl_c   = slope_deg(dem_c, res)

mask_v = sl_c > 62.0   # strefa "pionowa"

# Erozja: zostaw tylko zewnetrzna krawedz (gorny brzeg sciany)
from scipy.ndimage import binary_erosion, binary_dilation
mask_dilated = binary_dilation(mask_v, iterations=3)
cliff_edge_mask = mask_dilated & ~binary_erosion(mask_dilated, iterations=3)

dist_c = distance_transform_edt(mask_v)
local_max_c = (dist_c == maximum_filter(dist_c, size=7)) & mask_v & (dist_c > 1.0)

# Chcemy gorny/zewnetrzny brzeg: wysokie piksele na granicy strefy pionowej
edge_field = gaussian_filter((cliff_edge_mask & (dem_fill > np.nanpercentile(dem_fill, 30))).astype(float), sigma=2.5)

feats_cliff = contour_to_features(
    edge_field, 0.25,
    {"type": "cliff_edge", "color": "#ff2200", "stroke-width": 2},
    step=3, min_pts=6, min_len_px=25
)
print(f"  krawedzie scian: {len(feats_cliff)} segmentow")

# ── 6. Zapis GeoJSON ──────────────────────────────────────────────────────────
all_features = feats_ridge + feats_cliff
geojson = {
    "type": "FeatureCollection",
    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
    "features": all_features
}
out_path = os.path.join(OUT_DIR, "koscielec_structural.geojson")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(geojson, f, ensure_ascii=False)
print(f"\nZapisano: {out_path}  ({len(all_features)} features)")
print(f"  ridge:      {len(feats_ridge)}")
print(f"  cliff_edge: {len(feats_cliff)}")

# ── 7. PNG do inspekcji ───────────────────────────────────────────────────────
from PIL import Image

def save_gray(arr, path):
    lo, hi = np.nanpercentile(arr, 1), np.nanpercentile(arr, 99)
    n = np.clip((arr - lo) / (hi - lo + 1e-9), 0, 1)
    Image.fromarray((n * 255).astype(np.uint8)).save(path)

save_gray(sl_c, os.path.join(OUT_DIR, "slope.png"))
save_gray(pc,   os.path.join(OUT_DIR, "plan_curv.png"))

# Hillshade
dem_h = gaussian_filter(dem_fill, sigma=1.5)
dxh = np.gradient(dem_h, res, axis=1)
dyh = np.gradient(dem_h, res, axis=0)
slr = np.arctan(np.sqrt(dxh**2 + dyh**2))
asp = (np.degrees(np.arctan2(dxh, -dyh)) + 360) % 360
az, el = np.radians(315), np.radians(40)
hs = np.cos(el)*np.cos(slr) + np.sin(el)*np.sin(slr)*np.cos(az - np.radians(asp))
save_gray(hs, os.path.join(OUT_DIR, "hillshade.png"))

# Podglad z liniami na hillshade
fig, ax = plt.subplots(figsize=(14, 8))
ax.imshow(hs, cmap='gray', origin='upper')
ax.contour(ridge_field, levels=[0.15], colors=['yellow'], linewidths=1.5)
ax.contour(edge_field,  levels=[0.25], colors=['red'],    linewidths=1.5)
ax.set_title('Linie strukturalne — zolty=grzbiety, czerwony=krawedzie scian')
ax.axis('off')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "preview.png"), dpi=150, bbox_inches='tight')
plt.close()

print("\nPNG: hillshade.png, slope.png, plan_curv.png, preview.png")
print("Sprawdz structural_lines/preview.png")
