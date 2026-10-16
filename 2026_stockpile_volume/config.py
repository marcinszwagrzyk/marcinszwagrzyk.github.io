# -*- coding: utf-8 -*-
"""Shared settings: site, grids, time window, paths.

The site itself (coordinates, control windows) lives in `site.json`, which is
kept out of version control. Copy `site.example.json` to `site.json` and fill it in.
"""
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"          # raw downloads and composites (not in git)
OUT = ROOT / "out"            # results (charts, tables, 3D viewer)
DATA.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

SITE = json.load(open(ROOT / "site.json", encoding="utf-8"))
NAME = SITE.get("name", "Stockpile X")


def utm_epsg(lon, lat):
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


CRS = f"EPSG:{utm_epsg(SITE['lon'], SITE['lat'])}"
RES_S1 = 10.0     # m — native Sentinel-1 RTC / Sentinel-2 grid
RES_DEM = 30.0    # m — native DEM grid
HALF = float(SITE.get("half_size_m", 1500))

_fwd = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
_x, _y = _fwd.transform(SITE["lon"], SITE["lat"])
# Aligned to 30 m so the 10 m and 30 m grids nest pixel-in-pixel (3 × 3).
PX, PY = round(_x / RES_DEM) * RES_DEM, round(_y / RES_DEM) * RES_DEM
X0, X1, Y0, Y1 = PX - HALF, PX + HALF, PY - HALF, PY + HALF
_inv = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
_lo0, _la0 = _inv.transform(X0, Y0)
_lo1, _la1 = _inv.transform(X1, Y1)
BBOX_LL = (min(_lo0, _lo1), min(_la0, _la1), max(_lo0, _lo1), max(_la0, _la1))

N10 = int(round(2 * HALF / RES_S1))    # 10 m grid size (square)
N30 = int(round(2 * HALF / RES_DEM))   # 30 m grid size


def _parse_q(s):
    return int(s[:4]), int(s[-1])


def quarters():
    """[(label, start, end)] from first_quarter to last_quarter (end exclusive)."""
    out = []
    y, q = _parse_q(SITE.get("first_quarter", "2016Q3"))
    last = _parse_q(SITE.get("last_quarter", "2026Q3"))
    while (y, q) <= last:
        m0 = 3 * (q - 1) + 1
        y1, m1 = (y, m0 + 3) if q < 4 else (y + 1, 1)
        out.append((f"{y}Q{q}", f"{y}-{m0:02d}-01", f"{y1}-{m1:02d}-01"))
        y, q = (y, q + 1) if q < 4 else (y + 1, 1)
    return out


def km_window(w):
    """[x0, x1, y0, y1] in km from the site centre → (row slice, col slice) on the 10 m grid."""
    x0, x1, y0, y1 = w
    c = N10 // 2
    return (slice(int(round(c - y1 * 1000 / RES_S1)), int(round(c - y0 * 1000 / RES_S1))),
            slice(int(round(c + x0 * 1000 / RES_S1)), int(round(c + x1 * 1000 / RES_S1))))


CONTROL_WINDOWS = [km_window(w) for w in SITE["control_windows_km"]]
NATURAL_WINDOW = km_window(SITE["natural_window_km"])
EXTENT_KM = [-HALF / 1000, HALF / 1000, -HALF / 1000, HALF / 1000]


def geometry():
    """Sentinel-1 acquisition geometry written by download.py (orbit, incidence, heading)."""
    return json.load(open(DATA / "geometry.json", encoding="utf-8"))
