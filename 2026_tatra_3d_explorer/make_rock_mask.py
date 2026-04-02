"""
make_rock_mask.py
Rasteryzuje linie strukturalne (GeoJSON) na siatkę terenu,
tworzy bufor 40m i zapisuje maskę jako PNG:
  0 = brak skały (ortofoto),  255 = skała
Wynik: dem/koscielec_rock_mask.png  (rozmiar = rozmiar DEM)
"""
import numpy as np
import json
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter
import os

GEOJSON  = "structural_lines/koscielec_structural.geojson"
OUT_PNG  = "dem/koscielec_rock_mask.png"
BOUNDS   = {"west": 20.005382, "south": 49.221589,
            "east": 20.025604, "north": 49.229117}
DEM_W, DEM_H = 1461, 817   # piksele DEM (= rozmiar maski)
BUFFER_PX    = 40           # bufor w pikselach (~40 m przy res=1m/px)
EDGE_SIGMA   = 12.0         # rozmycie krawedzi przejscia (px)

def wgs84_to_px(lon, lat):
    c = (lon - BOUNDS["west"])  / (BOUNDS["east"]  - BOUNDS["west"]) * DEM_W
    r = (BOUNDS["north"] - lat) / (BOUNDS["north"] - BOUNDS["south"]) * DEM_H
    return int(round(c)), int(round(r))

# ── 1. Wczytaj GeoJSON ────────────────────────────────────────────────────────
with open(GEOJSON, encoding="utf-8") as f:
    gj = json.load(f)

# ── 2. Rasteryzuj linie na obraz binarny ─────────────────────────────────────
img  = Image.new("L", (DEM_W, DEM_H), 0)
draw = ImageDraw.Draw(img)

n_lines = 0
for feat in gj["features"]:
    geom = feat["geometry"]
    if geom["type"] != "LineString":
        continue
    coords = geom["coordinates"]
    px_pts = [wgs84_to_px(lon, lat) for lon, lat in coords]
    # Rysuj linia po linii
    for i in range(len(px_pts) - 1):
        draw.line([px_pts[i], px_pts[i+1]], fill=255, width=3)
    n_lines += 1

print(f"Rasteryzowano {n_lines} linii")
line_arr = np.array(img, dtype=np.float32) / 255.0

# ── 3. Bufor: distance transform od linii ─────────────────────────────────────
# distance_transform_edt liczy odleglosc od 0 — odwracamy: 1=linia, 0=brak
inv = (line_arr < 0.5).astype(np.uint8)   # 1 = daleko od linii, 0 = linia
dist = distance_transform_edt(inv)         # odleglosc od najblizszej linii (px)

# Maska binarna z buforem
buffer_mask = (dist <= BUFFER_PX).astype(np.float32)

# ── 4. Miekkie przejscie na krawedzi buforu ───────────────────────────────────
# Ramp: 1.0 na linii → 0.0 poza buforem, sigmoida
ramp = np.clip(1.0 - dist / (BUFFER_PX * 1.2), 0.0, 1.0)
ramp = gaussian_filter(ramp, sigma=EDGE_SIGMA)
ramp = np.clip(ramp / (ramp.max() + 1e-9), 0.0, 1.0)

# ── 5. Zapis PNG ──────────────────────────────────────────────────────────────
out_arr = (ramp * 255).astype(np.uint8)
Image.fromarray(out_arr, "L").save(OUT_PNG)

mb = os.path.getsize(OUT_PNG) / 1024 / 1024
print(f"Zapisano {OUT_PNG}  ({DEM_W}x{DEM_H}, {mb:.2f} MB)")
print(f"  max ramp={ramp.max():.3f}, pokrycie buforu: {buffer_mask.mean()*100:.1f}% pikseli")

# Podglad
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(16, 6))
axes[0].imshow(line_arr, cmap='hot', origin='upper')
axes[0].set_title("Linie strukturalne (raster)")
axes[1].imshow(ramp, cmap='hot', origin='upper')
axes[1].set_title(f"Maska skaly (bufor {BUFFER_PX}px + rozmycie)")
for ax in axes: ax.axis('off')
plt.tight_layout()
plt.savefig("structural_lines/rock_mask_preview.png", dpi=120, bbox_inches='tight')
plt.close()
print("Podglad: structural_lines/rock_mask_preview.png")
