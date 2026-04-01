"""
generate_mesh.py — generuje zamarla_rock_face.obj
Uruchom: python generate_mesh.py
Następnie otwórz w Blenderze (File > Import > Wavefront OBJ),
edytuj, eksportuj jako zamarla_rock_face.glb (File > Export > glTF 2.0)
do tego samego folderu.
"""
import math, struct, os

# ── parametry ─────────────────────────────────────────────────────────────────
COLS  = 200   # kolumny (poziome)
ROWS  = 280   # rzędy (pionowe wzdłuż profilu)
WIDTH = 500.0 # szerokość ściany [m]
OUT   = os.path.join(os.path.dirname(__file__), "zamarla_rock_face.obj")

# ── noise ─────────────────────────────────────────────────────────────────────
def h2(x, y):
    n = (((x & 0xfff) * 1619) ^ ((y & 0xfff) * 31337)) & 0xFFFFFFFF
    n = ((n >> 13) ^ n) & 0xFFFFFFFF
    n = ((n * (((n * n * 60493) & 0xFFFFFFFF) + 19990303)) & 0xFFFFFFFF)
    n = (n + 1376312589) & 0xFFFFFFFF
    return (n & 0xffff) / 65535.0

def vn2(x, y):
    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - ix, y - iy
    u = fx*fx*(3-2*fx); v = fy*fy*(3-2*fy)
    return (h2(ix,iy)*(1-u)*(1-v) + h2(ix+1,iy)*u*(1-v)
          + h2(ix,iy+1)*(1-u)*v   + h2(ix+1,iy+1)*u*v)

def fbm2(x, y, oct):
    v, a, f, s = 0.0, 0.5, 1.0, 0.0
    for o in range(oct):
        v += a * vn2(x*f + o*31.7, y*f + o*17.3)
        s += a; a *= 0.5; f *= 2.07
    return v / s

def h3(x, y, z):
    n = (((x & 0xfff)*1619) ^ ((y & 0xfff)*31337) ^ ((z & 0xfff)*6791)) & 0xFFFFFFFF
    n = ((n >> 13) ^ n) & 0xFFFFFFFF
    n = ((n * (((n*n*60493) & 0xFFFFFFFF) + 19990303)) & 0xFFFFFFFF)
    n = (n + 1376312589) & 0xFFFFFFFF
    return (n & 0xffff) / 65535.0

def vn3(x, y, z):
    ix,iy,iz = int(math.floor(x)),int(math.floor(y)),int(math.floor(z))
    fx,fy,fz = x-ix, y-iy, z-iz
    ux=fx*fx*(3-2*fx); uy=fy*fy*(3-2*fy); uz=fz*fz*(3-2*fz)
    return (h3(ix,  iy,  iz  )*(1-ux)*(1-uy)*(1-uz)
           +h3(ix+1,iy,  iz  )*ux    *(1-uy)*(1-uz)
           +h3(ix,  iy+1,iz  )*(1-ux)*uy    *(1-uz)
           +h3(ix+1,iy+1,iz  )*ux    *uy    *(1-uz)
           +h3(ix,  iy,  iz+1)*(1-ux)*(1-uy)*uz
           +h3(ix+1,iy,  iz+1)*ux    *(1-uy)*uz
           +h3(ix,  iy+1,iz+1)*(1-ux)*uy    *uz
           +h3(ix+1,iy+1,iz+1)*ux    *uy    *uz)

def fbm3(x, y, z, oct):
    v, a, f, s = 0.0, 0.5, 1.0, 0.0
    for o in range(oct):
        v += a * vn3(x*f+o*13.1, y*f+o*17.7, z*f+o*23.3)
        s += a; a *= 0.5; f *= 2.07
    return v / s

# ── profil ────────────────────────────────────────────────────────────────────
PROFILE_PTS = [
    (0.00,   0,   0),
    (0.06,  22,   1),
    (0.18,  70,   5),
    (0.32, 128,  18),
    (0.47, 195,  62),   # maksymalne przewieszenie
    (0.58, 228,  54),
    (0.67, 254,  20),
    (0.75, 276,   1),
    (0.87, 318,  -5),
    (1.00, 385, -16),
]

def get_profile(t):
    i = 0
    while i < len(PROFILE_PTS)-2 and PROFILE_PTS[i+1][0] <= t:
        i += 1
    t0,y0,z0 = PROFILE_PTS[i]
    t1,y1,z1 = PROFILE_PTS[i+1]
    s = (t - t0) / (t1 - t0)
    u = s*s*(3 - 2*s)
    return y0+(y1-y0)*u, z0+(z1-z0)*u

# ── generowanie wierzchołków ──────────────────────────────────────────────────
print(f"Generowanie {(COLS+1)*(ROWS+1)} wierzchołków, {COLS*ROWS*2} trójkątów...")

verts = []   # (x, y, z)
uvs   = []   # (u, v)

for row in range(ROWS + 1):
    t = row / ROWS
    pY, pZ = get_profile(t)

    for ci in range(COLS + 1):
        u = ci / COLS
        xBase = (u - 0.5) * WIDTH

        oZone = max(0.0, math.sin(max(0.0, (t - 0.28) / 0.48) * math.pi))

        colOvhg = (fbm2(xBase*0.0022 + 2.1, 0.3, 3) - 0.5) * 50
        pillarZ = (fbm2(xBase*0.0045, t*3.5 + 1.7, 4) - 0.5) * 42
        pillarY = (fbm2(xBase*0.0045, t*3.5 + 9.1, 3) - 0.5) * 18
        pillarX = (fbm2(xBase*0.0045, t*3.5 + 5.3, 3) - 0.5) * 28
        midZ    = (fbm3(xBase*0.025, pY*0.015, pZ*0.025 + 5, 3) - 0.5) * 14
        midY    = (fbm3(xBase*0.025, pY*0.015, pZ*0.025 + 15, 3) - 0.5) * 6
        fineZ   = (fbm3(xBase*0.18, pY*0.10, pZ*0.12 + 40, 2) - 0.5) * 2.2

        fx = xBase + pillarX * 0.45
        fy = pY    + pillarY  + midY
        fz = pZ    + colOvhg * oZone + pillarZ * 0.6 + midZ + fineZ

        verts.append((fx, fy, fz))
        uvs.append((u, t))

# ── indeksy trójkątów ─────────────────────────────────────────────────────────
faces = []  # (a, b, c) – 0-based
for row in range(ROWS):
    for ci in range(COLS):
        a = row*(COLS+1)+ci
        b = a + 1
        c = a + (COLS+1)
        d = c + 1
        faces.append((a, c, b))
        faces.append((b, c, d))

# ── normalne per-wierzchołek ──────────────────────────────────────────────────
normals = [(0.0, 0.0, 0.0)] * len(verts)
norm_arr = [[0.0, 0.0, 0.0] for _ in range(len(verts))]

for (ia, ib, ic) in faces:
    ax,ay,az = verts[ia]; bx,by,bz = verts[ib]; cx,cy,cz = verts[ic]
    ux2,uy2,uz2 = bx-ax, by-ay, bz-az
    vx2,vy2,vz2 = cx-ax, cy-ay, cz-az
    nx = uy2*vz2 - uz2*vy2
    ny = uz2*vx2 - ux2*vz2
    nz = ux2*vy2 - uy2*vx2
    for vi in (ia, ib, ic):
        norm_arr[vi][0] += nx
        norm_arr[vi][1] += ny
        norm_arr[vi][2] += nz

normals = []
for (nx,ny,nz) in norm_arr:
    ln = math.sqrt(nx*nx+ny*ny+nz*nz) + 1e-10
    normals.append((nx/ln, ny/ln, nz/ln))

# ── zapis OBJ ─────────────────────────────────────────────────────────────────
print(f"Zapisywanie do {OUT} ...")
with open(OUT, 'w') as f:
    f.write("# Rock face mesh – Tatra 3D Explorer\n")
    f.write("# Osie: X = poziomo, Y = pionowo (wysokosc), Z = glebokos\n")
    f.write("# Maks. przewieszenie: ~62 m (okolo Y=195)\n")
    f.write("# Import do Blendera: File > Import > Wavefront (.obj)\n")
    f.write("# Export z Blendera: File > Export > glTF 2.0 (.glb)\n\n")

    for (x,y,z) in verts:
        f.write(f"v {x:.3f} {y:.3f} {z:.3f}\n")
    f.write("\n")

    for (u,v) in uvs:
        f.write(f"vt {u:.5f} {v:.5f}\n")
    f.write("\n")

    for (nx,ny,nz) in normals:
        f.write(f"vn {nx:.5f} {ny:.5f} {nz:.5f}\n")
    f.write("\n")

    f.write("g rock_face\ns 1\n\n")
    for (ia, ib, ic) in faces:
        a,b,c = ia+1, ib+1, ic+1  # OBJ: 1-indexed
        f.write(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n")

size_mb = os.path.getsize(OUT) / 1024 / 1024
print(f"Gotowe! {OUT}")
print(f"Rozmiar: {size_mb:.1f} MB")
print(f"Wierzcholkow: {len(verts)}, Trojkatow: {len(faces)}")
print()
print("Nastepny krok:")
print("  1. Otwórz zamarla_rock_face.obj w Blenderze")
print("  2. Edytuj mesh")
print("  3. File > Export > glTF 2.0 (.glb) → zapisz jako zamarla_rock_face.glb w tym folderze")
print("  4. Otwórz viewer_mesh.html i wczytaj plik przez przycisk")
