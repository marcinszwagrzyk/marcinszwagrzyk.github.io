# -*- coding: utf-8 -*-
"""World map in the Natural Earth projection (a rounded, Mollweide-like globe)
without cartopy: geometries are built in lon/lat, cut at the dateline and
projected with pyproj. Also the grid of large hexagons shared by all hex maps.

Everything that draws on a map goes through xy() / geo_patches(), so callers
keep thinking in degrees.
"""
from __future__ import annotations

from functools import lru_cache

import geopandas as gpd
import numpy as np
import shapely
from matplotlib.patches import Polygon as MplPolygon
from pyproj import Transformer
from shapely.affinity import translate
from shapely.geometry import Polygon, box

import config as C
from data import fetch_naturalearth

PROJ = "+proj=natearth +lon_0=0 +datum=WGS84 +units=m"
_T = Transformer.from_crs("EPSG:4326", PROJ, always_xy=True)

X0, X1, Y0, Y1 = -180.0, 180.0, -58.0, 75.0     # hexagon grid extent (degrees)
VIEW_LAT = (-60.0, 82.0)                         # visible latitude band

OCEAN = "#dce8f0"      # cool blue-grey sea
LAND = "#ebe5d6"       # warm sand land
COAST = "#5f5e58"
GRATICULE = "#c3d3de"


# ------------------------------------------------------------ projection core
def xy(lon, lat):
    """lon/lat (degrees, any longitude) -> projected metres."""
    lon = ((np.asarray(lon, float) + 180) % 360) - 180
    return _T.transform(lon, np.asarray(lat, float))


def _split_dateline(geom):
    """Cut a lon/lat geometry that may extend past ±180° into pieces inside [-180, 180]."""
    parts = [geom.intersection(box(-180, -90, 180, 90))]
    right = geom.intersection(box(180, -90, 540, 90))
    left = geom.intersection(box(-540, -90, -180, 90))
    if not right.is_empty:
        parts.append(translate(right, xoff=-360))
    if not left.is_empty:
        parts.append(translate(left, xoff=360))
    return [p for p in parts if not p.is_empty]


def _project(geom):
    geom = shapely.segmentize(geom, 1.0)            # densify so edges bend with the projection
    return shapely.ops.transform(lambda x, y, z=None: _T.transform(x, y), geom)


def _polygons(geom):
    if geom.geom_type == "Polygon":
        return [geom]
    if hasattr(geom, "geoms"):
        return [g for sub in geom.geoms for g in _polygons(sub)]
    return []


def geo_patches(geom, **kw) -> list[MplPolygon]:
    """lon/lat shapely polygon -> projected matplotlib patches (split at the dateline)."""
    out = []
    for part in _split_dateline(geom):
        for poly in _polygons(_project(part)):
            out.append(MplPolygon(np.asarray(poly.exterior.coords), closed=True, **kw))
    return out


# ------------------------------------------------------------------ the map
@lru_cache(maxsize=1)
def world() -> gpd.GeoDataFrame:
    w = gpd.read_file(fetch_naturalearth())[["ISO_A3", "NAME", "CONTINENT", "geometry"]]
    return w[w.NAME != "Antarctica"]


@lru_cache(maxsize=1)
def land() -> gpd.GeoSeries:
    """All countries dissolved into one land mass (no national or continental borders),
    projected. A tiny buffer closes the slivers between neighbouring polygons."""
    merged = shapely.union_all(world().geometry.buffer(0.05).values).buffer(-0.05)
    return gpd.GeoSeries([merged], crs=world().crs).to_crs(PROJ)


@lru_cache(maxsize=1)
def _globe_outline() -> np.ndarray:
    """Outline of the visible band of the globe: curved sides, flat top and bottom."""
    lat = np.linspace(VIEW_LAT[0], VIEW_LAT[1], 143)
    lon = np.r_[np.full_like(lat, -180), np.full_like(lat, 180)[::-1]]
    la = np.r_[lat, lat[::-1]]
    x, y = _T.transform(lon, la)
    return np.column_stack([x, y])


def _clip(ax, artist):
    artist.set_clip_path(MplPolygon(_globe_outline(), closed=True, transform=ax.transData))


def draw(ax, nino_box=True, zorder=1):
    ax.set_facecolor(C.SURFACE)
    g = _globe_outline()
    ax.add_patch(MplPolygon(g, closed=True, facecolor=OCEAN, edgecolor="none", zorder=0))
    land().plot(ax=ax, color=LAND, edgecolor="none", zorder=zorder)
    # graticule every 30°
    for lon in range(-150, 151, 30):
        lat = np.linspace(*VIEW_LAT, 91)
        ax.plot(*_T.transform(np.full_like(lat, lon), lat), color=GRATICULE, lw=0.5, zorder=zorder)
    for lat in range(-60, 61, 30):
        lon = np.linspace(-180, 180, 181)
        ax.plot(*_T.transform(lon, np.full_like(lon, lat)), color=GRATICULE,
                lw=0.9 if lat == 0 else 0.5, zorder=zorder)
    ax.add_patch(MplPolygon(g, closed=True, facecolor="none", edgecolor=C.INK2, lw=1.0, zorder=11))
    pad = 0.01 * (g[:, 0].max() - g[:, 0].min())
    ax.set_xlim(g[:, 0].min() - pad, g[:, 0].max() + pad)
    ax.set_ylim(g[:, 1].min() - pad, g[:, 1].max() + pad)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    # the globe outline is the frame; no rectangle around it
    for s in ax.spines.values():
        s.set_visible(False)
    if nino_box:   # Niño 3.4 region (5°S–5°N, 170°W–120°W) as a reference
        for p in geo_patches(box(-170, -5, -120, 5), fill=False, ec=C.INK2, lw=0.8, ls="--",
                             zorder=9):
            ax.add_patch(p)
        ax.text(*xy(-145, 7), "Niño 3.4", ha="center", va="bottom", fontsize=7,
                color=C.INK2, zorder=9)


def outline(ax):
    """Continent coastlines on top of the hexes, so the land stays readable."""
    land().boundary.plot(ax=ax, color=COAST, linewidth=0.7, zorder=6)


def smooth(points, iters=3):
    """Chaikin smoothing: turns a few vertices into a soft blob."""
    p = np.asarray(points, float)
    for _ in range(iters):
        q = np.roll(p, -1, axis=0)
        p = np.stack([0.75 * p + 0.25 * q, 0.25 * p + 0.75 * q], axis=1).reshape(-1, 2)
    return p


def fill_geo(ax, pts, **kw):
    """Fill a lon/lat polygon (may cross the dateline) on the projected map."""
    for p in geo_patches(Polygon(pts).buffer(0), **kw):
        ax.add_patch(p)


def centroid_xy(pts):
    """Projected label position of a lon/lat polygon (kept inside ±180°)."""
    c = Polygon(pts).buffer(0).centroid
    return xy(c.x, c.y)


# -------------------------------------------------------------------- hexes
HEX_R = 8.0                       # centre-to-vertex, degrees: ~14° wide hexagons


@lru_cache(maxsize=1)
def hex_centers() -> np.ndarray:
    """Pointy-top hexagon grid (in lon/lat degrees) covering the map."""
    w, h = np.sqrt(3) * HEX_R, 1.5 * HEX_R
    out = []
    for i, y in enumerate(np.arange(Y0 + HEX_R * 0.5, Y1 + h, h)):
        off = 0 if i % 2 == 0 else w / 2
        for x in np.arange(X0 + off, X1 + w, w):
            out.append((x, y))
    return np.array(out)


def hex_polygon(cx, cy, scale=1.0) -> Polygon:
    a = np.deg2rad(np.arange(6) * 60 + 30)
    r = HEX_R * scale
    return Polygon(np.column_stack([cx + r * np.cos(a), cy + r * np.sin(a)]))


def assign(lon, lat) -> np.ndarray:
    """Index of the nearest hexagon for every point (lon wrapped to -180..180)."""
    cen = hex_centers()
    lon = ((np.asarray(lon, float) + 180) % 360) - 180
    lat = np.asarray(lat, float)
    if len(lon) == 0:
        return np.array([], int)
    dx = np.abs(lon[:, None] - cen[None, :, 0])
    dx = np.minimum(dx, 360 - dx)
    d2 = dx ** 2 + (lat[:, None] - cen[None, :, 1]) ** 2
    return d2.argmin(1)
