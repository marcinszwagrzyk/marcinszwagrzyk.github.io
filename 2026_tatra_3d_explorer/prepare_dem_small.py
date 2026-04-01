"""
prepare_dem_small.py — przetwarza zamarla_small.tif
Tworzy:
  dem/zamarla_small_terrain_rgb.png  (dla viewera)
  dem/zamarla_small_meta.json        (metadane)
  zamarla_small_rock_face.obj        (mesh z przewieszeniami, gotowy do Blendera)

Uruchom w środowisku z rasterio+numpy+Pillow (to samo co prepare_dem.py):
  python prepare_dem_small.py
"""
import rasterio
from rasterio.warp import transform_bounds
import numpy as np
from PIL import Image
import json, os, math

DEM_PATH = "dem/zamarla_small.tif"
OUT_DIR  = "dem"

# ── 1. Wczytaj DEM ────────────────────────────────────────────────────────────
print("Wczytuję", DEM_PATH)
with rasterio.open(DEM_PATH) as src:
    data       = src.read(1).astype(np.float64)
    nodata     = src.nodata
    bounds_src = src.bounds
    crs        = src.crs
    width, height = src.width, src.height
    res_m = abs(src.transform.a)   # rozmiar piksela [m]

if nodata is not None:
    data[data == nodata] = np.nan

elev_min = float(np.nanmin(data))
elev_max = float(np.nanmax(data))
data_filled = np.where(np.isnan(data), elev_min, data)

print(f"  rozmiar: {width} × {height} px,  res: {res_m:.2f} m/px")
print(f"  wys. min/max: {elev_min:.1f} – {elev_max:.1f} m")

# ── 2. terrain-RGB PNG (Mapbox encoding) ──────────────────────────────────────
encoded = ((data_filled + 10000) / 0.1).astype(np.int32)
R = ((encoded >> 16) & 0xFF).astype(np.uint8)
G = ((encoded >>  8) & 0xFF).astype(np.uint8)
B = ( encoded        & 0xFF).astype(np.uint8)
Image.fromarray(np.stack([R,G,B], axis=-1), 'RGB').save(
    os.path.join(OUT_DIR, "zamarla_small_terrain_rgb.png"))
print("Zapisano zamarla_small_terrain_rgb.png")

# ── 3. Metadane JSON ──────────────────────────────────────────────────────────
try:
    bounds_wgs84 = transform_bounds(crs, "EPSG:4326", *bounds_src)
except Exception:
    bounds_wgs84 = (0, 0, 1, 1)  # fallback

meta = {
    "elev_min": elev_min, "elev_max": elev_max,
    "width_px": width,    "height_px": height,
    "res_m": res_m,
    "bounds_wgs84": dict(zip(["west","south","east","north"], bounds_wgs84))
}
with open(os.path.join(OUT_DIR, "zamarla_small_meta.json"), "w") as f:
    json.dump(meta, f, indent=2)
print("Zapisano zamarla_small_meta.json")

# ── 4. Generuj mesh OBJ z prawdziwego DEM + przewieszenia ─────────────────────
print("Generuję mesh OBJ…")

STEP  = 2          # co ile pikseli bierzemy wierzchołek (downscale)
physW = width  * res_m
physD = height * res_m

cols = width  // STEP
rows = height // STEP

# -- noise (pure Python, deterministyczny) ------------------------------------
def h2(x, y):
    n = (((x & 0xfff)*1619) ^ ((y & 0xfff)*31337)) & 0xFFFFFFFF
    n = ((n >> 13) ^ n) & 0xFFFFFFFF
    n = ((n * (((n*n*60493) & 0xFFFFFFFF) + 19990303)) & 0xFFFFFFFF)
    return ((n + 1376312589) & 0xFFFF) / 65535.0

def vn2(x, y):
    ix,iy = int(math.floor(x)), int(math.floor(y))
    fx,fy = x-ix, y-iy
    u = fx*fx*(3-2*fx); v = fy*fy*(3-2*fy)
    return (h2(ix,iy)*(1-u)*(1-v) + h2(ix+1,iy)*u*(1-v)
          + h2(ix,iy+1)*(1-u)*v   + h2(ix+1,iy+1)*u*v)

def fbm2(x, y, oct):
    v,a,f,s = 0.0, 0.5, 1.0, 0.0
    for o in range(oct):
        v += a*vn2(x*f+o*31.7, y*f+o*17.3); s += a; a *= 0.5; f *= 2.07
    return v/s

# -- wybieramy piksel dla każdego wierzchołka ---------------------------------
# Dane DEM jako numpy array, STEP co STEP
dem_sub = data_filled[::STEP, ::STEP][:rows, :cols]  # (rows, cols)

# Nachylenie ≈ gradient pionowy → gdzie jest ściana (strome = potencjalne przewieszenie)
gy, gx = np.gradient(dem_sub, res_m*STEP)
slope   = np.arctan(np.sqrt(gx**2 + gy**2)) / (math.pi/2)  # 0=płasko, 1=pionowo

verts, uvs, normals_acc = [], [], []
faces = []

nV = (cols+1) * (rows+1)
norm_arr = [[0.0,0.0,0.0] for _ in range(nV)]  # inicjalizacja poniżej

for r in range(rows):
    for c in range(cols):
        u  = c / (cols-1)
        tv = r / (rows-1)
        x  = (u - 0.5) * physW
        z0 = (tv - 0.5) * physD   # oś Z = głębokość terenu (S-N)

        elev = dem_sub[r, c]
        y    = elev                 # wysokość = Y

        # Przewieszenie tylko na stromych ścianach — przesunięcie w osi X
        # (ściana Zamarłej jest zorientowana N-S, więc X = ku widzowi)
        sl  = float(slope[r, c]) if r < slope.shape[0] and c < slope.shape[1] else 0.0
        # strefa: gdzie slope > 0.8 i elev w okolicach środka ściany
        t_elev = (elev - elev_min) / (elev_max - elev_min)
        ovhg_zone = max(0.0, sl - 0.75) * 4.0          # 0 gdy płasko, >0 na ścianie
        ovhg_zone *= max(0.0, math.sin(t_elev * math.pi))  # znika u dołu i góry

        # Lokalne przewieszenie: szum + wzmocnienie na ścianie
        noise_ovhg = (fbm2(x*0.008+1.1, z0*0.008+3.7, 3) - 0.5) * 2.0
        prevish = ovhg_zone * (8.0 + noise_ovhg * 6.0)   # maks ~14 m wysunięcia

        # Przesunięcie w osi X (ku S, od strony wspinacza)
        x_out = x + prevish

        verts.append((x_out, y, z0))
        uvs.append((u, tv))

        if r < rows-1 and c < cols-1:
            a = r*cols+c; b=a+1; cv2=a+cols; d=cv2+1
            faces.append((a, cv2, b))
            faces.append((b, cv2, d))

# -- normalne per-wierzchołek -------------------------------------------------
nV = len(verts)
norm_arr = [[0.0,0.0,0.0] for _ in range(nV)]
for (ia,ib,ic) in faces:
    ax,ay,az = verts[ia]; bx,by,bz = verts[ib]; cx,cy,cz = verts[ic]
    ux2,uy2,uz2 = bx-ax, by-ay, bz-az
    vx2,vy2,vz2 = cx-ax, cy-ay, cz-az
    nx = uy2*vz2-uz2*vy2; ny = uz2*vx2-ux2*vz2; nz = ux2*vy2-uy2*vx2
    for vi in (ia,ib,ic):
        norm_arr[vi][0]+=nx; norm_arr[vi][1]+=ny; norm_arr[vi][2]+=nz

normals = []
for (nx,ny,nz) in norm_arr:
    ln = math.sqrt(nx*nx+ny*ny+nz*nz)+1e-10
    normals.append((nx/ln, ny/ln, nz/ln))

# -- zapis OBJ ----------------------------------------------------------------
OUT_OBJ = "zamarla_small_rock_face.obj"
print(f"Zapisuję {OUT_OBJ} …")
with open(OUT_OBJ, "w") as f:
    f.write("# zamarla_small rock face mesh\n")
    f.write(f"# {cols}x{rows} siatka z DEM + przewieszenia na stromych ścianach\n")
    f.write("# Import do Blendera: File > Import > Wavefront (.obj)\n\n")
    for (x,y,z) in verts:
        f.write(f"v {x:.3f} {y-elev_min:.3f} {z:.3f}\n")
    f.write("\n")
    for (u,v) in uvs:
        f.write(f"vt {u:.5f} {v:.5f}\n")
    f.write("\n")
    for (nx,ny,nz) in normals:
        f.write(f"vn {nx:.5f} {ny:.5f} {nz:.5f}\n")
    f.write("\ng terrain_with_overhangs\ns 1\n\n")
    for (ia,ib,ic) in faces:
        a,b,c = ia+1,ib+1,ic+1
        f.write(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n")

size_mb = os.path.getsize(OUT_OBJ)/1024/1024
print(f"Gotowe! {OUT_OBJ} ({size_mb:.1f} MB)")
print(f"Wierzchołków: {len(verts)}, Trójkątów: {len(faces)}")
print()
print("Następny krok:")
print("  1. Otwórz zamarla_small_rock_face.obj w Blenderze")
print("  2. File > Export > glTF 2.0 (.glb) → zamarla_small_rock_face.glb")
print("  3. Otwórz viewer_mesh_small.html i wczytaj plik")
