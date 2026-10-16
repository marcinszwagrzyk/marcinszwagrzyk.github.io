# -*- coding: utf-8 -*-
"""Standalone 3D viewer — out/stockpile_3d.html (one file, opens from disk).

Frames: three DEM epochs (measured), then the Sentinel-1 quarters: terrain =
Copernicus DEM + measured stockpile height change (Δh × outline, soft edge).
Texture = Sentinel-2 composite of the quarter (first composite for DEM epochs).
"""
import base64
import io
import json

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage

import config as C

CROP_KM = 1.0   # ±1 km around the stockpile


def b64(arr):
    return base64.b64encode(np.ascontiguousarray(arr).tobytes()).decode()


def jpg(rgb, q=82):
    buf = io.BytesIO()
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype("uint8")).save(buf, "JPEG", quality=q)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    w = np.load(C.DATA / "results.npz")
    tab = pd.read_csv(C.OUT / "stockpile_quarterly.csv")
    dem = pd.read_csv(C.OUT / "stockpile_dem.csv")
    summ = json.load(open(C.OUT / "stockpile_summary.json", encoding="utf-8"))
    k30 = int(round((C.HALF - CROP_KM * 1000) / C.RES_DEM))
    S30 = (slice(k30, C.N30 - k30), slice(k30, C.N30 - k30))
    S10 = (slice(3 * k30, C.N10 - 3 * k30), slice(3 * k30, C.N10 - 3 * k30))
    z = {k: w[f"z_{k}"][S30] for k in ("srtm", "alos", "cop")}
    m30 = w["m30"][S30]
    soft = ndimage.gaussian_filter(m30.astype(float), 1.0)
    area = summ["area_km2"]
    v_cop = float(dem.volume_Mm3.iloc[-1])
    base_h = float((z["cop"] - z["srtm"])[m30].mean())

    tex, tex_idx = [], {}
    for lab in tab.quarter:
        f = C.DATA / "s2" / f"{lab}.npz"
        if f.exists():
            tex_idx[lab] = len(tex)
            s = np.load(f)["refl"][S10]
            tex.append(jpg(np.clip(np.nan_to_num(s[..., [2, 1, 0]]) / 0.25, 0, 1) ** 0.8))
    frames = []
    for r, k, src in zip(dem.itertuples(), ("srtm", "alos", "cop"),
                         ("SRTM — ground before the stockpile", "ALOS AW3D30 (2006–2011)", "Copernicus DEM (2011–2015)")):
        frames.append(dict(label={"srtm": "2000", "alos": "~2008", "cop": "~2012"}[k], src=src + " · measured",
                           z=b64(np.round(z[k] * 10).astype("<i2")), v=round(r.volume_Mm3, 2), sv=0.3,
                           h=round(r.mean_height_m, 1), tex=0, dem=True))
    cur_tex = 0
    sig = summ["s1_sigma_m_per_quarter"]
    for r in tab.itertuples():
        cur_tex = tex_idx.get(r.quarter, cur_tex)
        ok = not np.isnan(r.dh_m)
        dh = float(r.dh_m) if ok else 0.0
        frames.append(dict(label=r.quarter, src="Copernicus DEM + Δh from Sentinel-1" + ("" if ok else " (no measurement)"),
                           z=b64(np.round((z["cop"] + dh * soft) * 10).astype("<i2")),
                           v=round(v_cop + dh * area, 2) if ok else None, sv=round(sig * area, 2),
                           h=round(base_h + dh, 1) if ok else None, tex=cur_tex, dem=False))
    data = dict(nx=m30.shape[1], ny=m30.shape[0], res=C.RES_DEM, zmin=float(min(v.min() for v in z.values())),
                frames=frames)
    html = (C.ROOT / "viewer_template.html").read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/null", json.dumps(data)).replace("/*__TEX__*/null", json.dumps(tex))
    out = C.OUT / "stockpile_3d.html"
    out.write_text(html, encoding="utf-8")
    print(out.name, f"{out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
