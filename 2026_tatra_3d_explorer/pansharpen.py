"""
Pansharpening: blends ortofoto RGB with DEM hillshade using Brovey transform.
DEM hillshade = high-freq detail (0.5m), ortofoto = color info.
Output: wyostrzony ortofoto z detailami reliefu.
"""
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from PIL import Image
import json

DEM_PATH  = "dem/zamarla.tif"
ORTO_PATH = "dem/zamarla_ortho.jpg"
OUT_PATH  = "dem/zamarla_pansharp.jpg"

# ── Load DEM ──────────────────────────────────────────────────────────────────
with rasterio.open(DEM_PATH) as src:
    dem = src.read(1).astype(np.float64)
    nodata = src.nodata
    transform = src.transform
    crs = src.crs
    H_dem, W_dem = dem.shape

dem[dem == nodata] = np.nan
dem_filled = np.where(np.isnan(dem), np.nanmin(dem), dem)

# ── Compute hillshade ─────────────────────────────────────────────────────────
# Sun azimuth & altitude chosen for max detail (not solar position)
az_deg  = 315   # NW – classic cartographic sun
alt_deg = 35

az_rad  = np.radians(360 - az_deg + 90)
alt_rad = np.radians(alt_deg)

res = 0.5  # meter/pixel

# Gradient via Sobel-like central differences
zy, zx = np.gradient(dem_filled, res)

# Surface normal
slope = np.arctan(np.sqrt(zx**2 + zy**2))
aspect = np.arctan2(-zy, zx)

hillshade = (
    np.cos(alt_rad) * np.cos(slope) +
    np.sin(alt_rad) * np.sin(slope) * np.cos(az_rad - aspect)
)
hillshade = np.clip(hillshade, 0, 1)

# Soften low-angle shadows (keep shadows but not pitch black)
hillshade = hillshade * 0.75 + 0.25

print(f"Hillshade: min={hillshade.min():.3f}  max={hillshade.max():.3f}")

# ── Load ortofoto ──────────────────────────────────────────────────────────────
orto = np.array(Image.open(ORTO_PATH).convert('RGB')).astype(np.float32)
H_o, W_o = orto.shape[:2]
print(f"Orto size: {W_o}×{H_o},  DEM size: {W_dem}×{H_dem}")

# Resize hillshade to match ortofoto (should be same size, but just in case)
if (H_o, W_o) != (H_dem, W_dem):
    from PIL import Image as PILImage
    hs_img = PILImage.fromarray((hillshade * 255).astype(np.uint8))
    hs_img = hs_img.resize((W_o, H_o), PILImage.LANCZOS)
    hillshade = np.array(hs_img).astype(np.float32) / 255.0
else:
    hillshade = hillshade.astype(np.float32)

# ── Brovey pansharpening ────────────────────────────────────────────────────────
# Intensity = perceptual luminance
R, G, B = orto[:,:,0], orto[:,:,1], orto[:,:,2]
intensity = (0.299*R + 0.587*G + 0.114*B)

# Avoid division by zero
intensity_safe = np.where(intensity < 1.0, 1.0, intensity)

hs255 = hillshade * 255.0

R_pan = np.clip(R * hs255 / intensity_safe, 0, 255)
G_pan = np.clip(G * hs255 / intensity_safe, 0, 255)
B_pan = np.clip(B * hs255 / intensity_safe, 0, 255)

# Blend: 70% Brovey + 30% original (avoid oversaturation)
alpha = 0.70
R_out = alpha*R_pan + (1-alpha)*R
G_out = alpha*G_pan + (1-alpha)*G
B_out = alpha*B_pan + (1-alpha)*B

result = np.stack([R_out, G_out, B_out], axis=-1).astype(np.uint8)

# Mild unsharp mask on top for extra crispness
from scipy.ndimage import gaussian_filter
blur = gaussian_filter(result.astype(np.float32), sigma=1.2)
sharp = result.astype(np.float32) + 0.4 * (result.astype(np.float32) - blur)
sharp = np.clip(sharp, 0, 255).astype(np.uint8)

Image.fromarray(sharp).save(OUT_PATH, quality=95)
print(f"Zapisano {OUT_PATH}")
