# -*- coding: utf-8 -*-
"""One image per hazard, three hex maps each:

    1. what theory expects from El Niño,
    2. El Niño minus the Neutral benchmark   (red = more, green = less),
    3. La Niña minus the Neutral benchmark   (same colours).

Hazards are classified from long raw records (climate.py), compared on
EQUAL-SIZE groups of ENSO years. A bold number with * differs
from the benchmark at p < 0.10 (Welch t-test over the years of each group).

    python hexmaps.py   # -> out/hex_*.png
"""
from __future__ import annotations

from dataclasses import dataclass, field

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.stats import ttest_ind

import basemap as B
import climate
import config as C
import enso
import plots  # noqa: F401  (rcParams)

LAST = None   # last complete ENSO year, set in main()

# -------------------------------------------------------------- theory boxes
# (sign, lon0, lon1, lat0, lat1, label). +1 = El Niño brings MORE of the hazard.
# Sources: NOAA CPC / Climate.gov El Niño impact maps (DJF and JJA), IRI, WMO
# El Niño updates; cyclones after Camargo & Sobel 2005, Klotzbach 2011.
THEORY = {
    "cyclones": [
        (+1, -150, -100, 8, 22, "E Pacific"), (+1, -180, -145, 8, 22, "C Pacific / Hawaii"),
        (+1, 140, 180, 5, 20, "SE of Guam"), (+1, -170, -130, -25, -8, "French Polynesia"),
        (-1, -95, -20, 10, 30, "Atlantic"), (-1, 145, 170, -25, -10, "Coral Sea"),
        (-1, 105, 125, 8, 22, "S China Sea"), (-1, 105, 130, -22, -10, "NW Australia"),
    ],
    "major": [
        (+1, 125, 180, 8, 28, "W Pacific"), (+1, -145, -100, 8, 22, "E Pacific"),
        (+1, -180, -145, 8, 22, "C Pacific"), (+1, -170, -130, -25, -8, "S Pacific east"),
        (-1, -95, -20, 10, 32, "Atlantic"), (-1, 145, 170, -25, -10, "Coral Sea"),
    ],
    "rain": [
        (+1, -82, -76, -10, 2, "Peru/Ecuador"), (+1, -122, -80, 25, 37, "Southern US"),
        (+1, -62, -48, -35, -22, "SE South America"), (+1, 33, 48, -8, 8, "East Africa (OND)"),
        (+1, 105, 122, 22, 31, "SE China"),
        (-1, 95, 150, -10, 8, "Maritime Continent"), (-1, 130, 153, -35, -11, "N/E Australia"),
        (-1, 68, 90, 8, 30, "India"), (-1, 20, 40, -28, -9, "Southern Africa"),
        (-1, -77, -35, -12, 12, "N South America"), (-1, -92, -60, 8, 20, "Central America"),
    ],
    "drought": [
        (+1, 95, 150, -10, 8, "Maritime Continent"), (+1, 130, 153, -35, -11, "N/E Australia"),
        (+1, 68, 90, 8, 30, "India"), (+1, 20, 40, -28, -9, "Southern Africa"),
        (+1, -77, -35, -12, 12, "N South America"), (+1, -92, -60, 8, 20, "Central America"),
        (+1, -17, 35, 9, 17, "Sahel"),
        (-1, -122, -80, 25, 37, "Southern US"), (-1, -62, -48, -35, -22, "SE South America"),
        (-1, 33, 48, -8, 8, "East Africa"), (-1, -82, -76, -10, 2, "Peru/Ecuador"),
    ],
    "monsoon": [   # +1 = El Niño brings a rainfall DEFICIT (monsoon drought)
        (+1, 68, 92, 8, 30, "Indian monsoon"), (+1, 95, 150, -12, 8, "Indonesian monsoon"),
        (+1, 120, 150, -20, -10, "Australian monsoon"), (+1, -17, 35, 8, 18, "W African monsoon"),
        (+1, -110, -85, 10, 25, "Mexican monsoon"), (+1, 20, 40, -25, -9, "S African summer rain"),
        (-1, -60, -45, -30, -15, "S American (south)"),
    ],
    "heat": [
        (+1, -140, -60, 45, 66, "Canada / N US"), (+1, 95, 150, -10, 20, "SE Asia"),
        (+1, 113, 153, -38, -12, "Australia"), (+1, 15, 40, -35, -10, "Southern Africa"),
        (+1, -77, -35, -15, 10, "N South America"), (+1, 68, 90, 8, 30, "India"),
        (-1, -105, -80, 25, 35, "Gulf Coast US"),
    ],
}


@dataclass
class Hazard:
    key: str
    title: str
    unit: str
    source: str
    fmt: str = "{:.1f}"
    dfmt: str = "{:+.1f}"
    values: pd.DataFrame = field(default=None, repr=False)   # ENSO year x hex
    note: str = ""
    bench: pd.Series = None          # optional benchmark override (monsoon: mm/day)
    bench_unit: str = ""


# ------------------------------------------------------------ aggregation
def grid_to_hex(lat, lon, per_year: dict[int, np.ndarray], land_only=True) -> pd.DataFrame:
    gx, gy = np.meshgrid(lon, lat)
    hid = B.assign(gx.ravel(), gy.ravel())
    w = np.cos(np.deg2rad(gy.ravel()))
    mask = climate.land_mask(tuple(lat), tuple(lon)).ravel() if land_only else np.ones_like(w, bool)
    rows = {}
    for y, a in per_year.items():
        v = a.ravel()
        ok = mask & ~np.isnan(v)
        df = pd.DataFrame({"h": hid[ok], "wv": v[ok] * w[ok], "w": w[ok]}).groupby("h").sum()
        rows[y] = df.wv / df.w
    return pd.DataFrame(rows).T.sort_index()


def points_to_hex(pts: pd.DataFrame, first, last) -> pd.DataFrame:
    pts = pts.copy()
    pts["year"] = pts.time.dt.year - (pts.time.dt.month < C.ENSO_YEAR_START_MONTH)
    pts = pts[(pts.year >= first) & (pts.year <= last)]
    pts["h"] = B.assign(pts.lon, pts.lat)
    t = pts.groupby(["year", "h"]).size().unstack(fill_value=0) / 4.0   # 6-hourly -> days
    return t.reindex(range(first, last + 1), fill_value=0)


def build_hazards() -> list[Hazard]:
    pts = climate.ibtracs_points()
    H = []
    cyc = points_to_hex(pts, 1980, LAST)
    H.append(Hazard("cyclones", "Tropical cyclones — days with storm-force wind (≥ 34 kt)",
                    "days per season in the hexagon", "IBTrACS 6-hourly winds", values=cyc))
    maj = points_to_hex(pts[pts.wind >= 96], 1980, LAST)
    H.append(Hazard("major", "Major hurricanes / typhoons (cat. 3–5) — days with wind ≥ 96 kt",
                    "days per season in the hexagon", "IBTrACS 6-hourly winds", "{:.2f}", "{:+.2f}",
                    values=maj))
    lat, lon, d = climate.drought_months(1979, LAST)
    H.append(Hazard("drought", "Drought — dry months (6-month SPI ≤ −1.0)",
                    "months per year (land)", "GPCP v2.3 monthly precipitation", values=grid_to_hex(lat, lon, d)))
    lat, lon, d, mm = climate.monsoon_rain(1979, LAST)
    deficit = {y: 100 - v for y, v in d.items()}     # % below normal: positive = drier
    H.append(Hazard("monsoon", "Monsoon drought — summer rainfall deficit (Jun–Sep north, Dec–Mar south)",
                    "% below the long-term mean", "GPCP v2.3, monsoon domains (Wang & Ding)",
                    "{:.0f}", "{:+.0f}", values=grid_to_hex(lat, lon, deficit, land_only=False),
                    note="Red = larger rainfall deficit (drier monsoon), green = wetter monsoon.",
                    bench=grid_to_hex(lat, lon, {0: mm}, land_only=False).iloc[0],
                    bench_unit="long-term mean summer rainfall, mm/day"))
    lat, lon, d = climate.heat_months(1950, LAST)
    H.append(Hazard("heat", "Heatwaves — hot months (detrended temperature above the 90th percentile)",
                    "months per year (land)", "GHCN-CAMS 2 m temperature, linear warming trend removed",
                    values=grid_to_hex(lat, lon, d)))
    return H


# ----------------------------------------------------------------- drawing
GREEN_RED = ["#0f5c33", "#1d8a4a", "#6fbf8a", "#c4e6cf", "#efeeea", "#f6c4bd", "#e8776e", "#c8312f", "#8c1c1a"]
HEX_ALPHA = 0.62     # translucent, so the continents show through


def _levels(maxabs):
    s = maxabs / 4.0
    return np.array([-4, -3, -2, -1, -0.25, 0.25, 1, 2, 3, 4]) * s


def _bin(v, edges):
    return int(np.clip(np.searchsorted(edges, v) - 1, 0, len(edges) - 2))


def hexes(ax, colors: dict, texts: dict, bold: set = frozenset(), zorder=4):
    """Projected hexagons: built in lon/lat, cut at the dateline, then projected."""
    cen = B.hex_centers()
    patches, fcs = [], []
    for k, col in colors.items():
        x, y = cen[k]
        for p in B.geo_patches(B.hex_polygon(x, y, 0.94)):
            patches.append(p)
            fcs.append(col)
        if k in texts and B.X0 + 4 <= x <= B.X1 - 4:
            dark = col in (GREEN_RED[0], GREEN_RED[1], GREEN_RED[7], GREEN_RED[8])
            ax.text(*B.xy(x, y), texts[k] + ("*" if k in bold else ""), ha="center", va="center",
                    fontsize=8.2 if k in bold else 7.4,
                    color="white" if dark else C.INK, zorder=zorder + 4,
                    fontweight="bold" if k in bold else "normal", clip_on=True)
    pc = PatchCollection(patches, facecolors=fcs, edgecolors="none", alpha=HEX_ALPHA, zorder=zorder)
    ax.add_collection(pc)
    B._clip(ax, pc)          # hexagons stop at the edge of the globe


def panel_theory(ax, hz: Hazard):
    B.draw(ax, zorder=1)
    cen = B.hex_centers()
    colors, texts = {}, {}
    for sign, x0, x1, y0, y1, lab in THEORY[hz.key]:
        inside = (cen[:, 0] >= x0 - 2) & (cen[:, 0] <= x1 + 2) & (cen[:, 1] >= y0 - 2) & (cen[:, 1] <= y1 + 2)
        for k in np.where(inside)[0]:
            colors[k] = GREEN_RED[7] if sign > 0 else GREEN_RED[1]
            texts[k] = "▲" if sign > 0 else "▼"
    hexes(ax, colors, texts)
    B.outline(ax)
    for sign, x0, x1, y0, y1, lab in THEORY[hz.key]:
        ax.text(*B.xy((x0 + x1) / 2, y1 + 4.5), lab, ha="center", va="bottom", fontsize=7.5, color=C.INK,
                zorder=12, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    ax.set_title("1 · What theory expects from El Niño  (▲ more, ▼ less)", loc="left",
                 fontweight="bold", fontsize=12)


def panel_diff(ax, hz: Hazard, vals: pd.DataFrame, ph: str, eq: dict, base: pd.Series, levels, num):
    B.draw(ax, zorder=1)
    a, n = vals.reindex(eq[ph]), vals.reindex(eq[C.NEUTRAL])
    d = a.mean() - n.mean()
    keep = (a.mean().abs() + n.mean().abs()) > (0.02 if hz.key == "major" else 0.05)
    if hz.key == "monsoon":
        keep = base.notna() & d.notna()
    d = d[keep & d.notna()]
    with np.errstate(all="ignore"):
        p = pd.Series(ttest_ind(a[d.index], n[d.index], equal_var=False, nan_policy="omit").pvalue,
                      index=d.index)
    sig = set(p[p < 0.10].index)
    colors = {k: GREEN_RED[_bin(x, levels)] for k, x in d.items()}
    texts = {k: hz.dfmt.format(x) for k, x in d.items() if abs(x) >= levels[5]}
    hexes(ax, colors, texts, bold=sig)
    B.outline(ax)
    ax.set_title(f"{num} · {ph} minus the Neutral benchmark", loc="left", fontweight="bold",
                 fontsize=12, color=C.PHASE_COLORS[ph])
    ax.text(0, -0.012, f"{len(eq[ph])} {ph} years: " + _years(eq[ph], 30)
            + f"  ·  bold number with *: p < 0.10 ({len(sig)} hexagons)",
            transform=ax.transAxes, va="top", fontsize=7.8, color=C.INK2)
    return d


def _years(ys, maxn=14):
    ys = [str(y) for y in ys]
    return ", ".join(ys) if len(ys) <= maxn else ", ".join(ys[:maxn]) + f" … (+{len(ys) - maxn})"


def figure(hz: Hazard, years: pd.DataFrame, path):
    """Three stacked maps: theory, El Niño − Neutral, La Niña − Neutral.

    The Neutral benchmark is not drawn as a map: it is the zero of maps 2-3
    (its values per hexagon are in hex_*_values.csv)."""
    vals = hz.values
    eq = enso.equal_groups(years, vals.index)
    base = vals.reindex(eq[C.NEUTRAL]).mean()
    diffs = [(vals.reindex(eq[ph]).mean() - base).abs() for ph in ("El Niño", "La Niña")]
    levels = _levels(np.nanpercentile(pd.concat(diffs).dropna(), 95))

    fig, axes = plt.subplots(3, 1, figsize=(16, 21.5))
    panel_theory(axes[0], hz)
    panel_diff(axes[1], hz, vals, "El Niño", eq, base, levels, 2)
    panel_diff(axes[2], hz, vals, "La Niña", eq, base, levels, 3)

    fmt = hz.dfmt
    lab = lambda i, j: f"{fmt.format(levels[i])} … {fmt.format(levels[j])}"
    handles = [Patch(color=GREEN_RED[8], alpha=HEX_ALPHA, label=f"more: > {fmt.format(levels[8])}"),
               Patch(color=GREEN_RED[7], alpha=HEX_ALPHA, label=lab(7, 8)),
               Patch(color=GREEN_RED[6], alpha=HEX_ALPHA, label=lab(6, 7)),
               Patch(color=GREEN_RED[5], alpha=HEX_ALPHA, label=lab(5, 6)),
               Patch(color=GREEN_RED[4], alpha=HEX_ALPHA, label="≈ no change"),
               Patch(color=GREEN_RED[3], alpha=HEX_ALPHA, label=lab(3, 4)),
               Patch(color=GREEN_RED[2], alpha=HEX_ALPHA, label=lab(2, 3)),
               Patch(color=GREEN_RED[1], alpha=HEX_ALPHA, label=lab(1, 2)),
               Patch(color=GREEN_RED[0], alpha=HEX_ALPHA, label=f"less: < {fmt.format(levels[1])}"),
               Patch(facecolor="none", edgecolor="none", label="+1.2*  bold = p < 0.10")]
    fig.legend(handles=handles, loc="upper left", ncol=5, frameon=False, fontsize=9,
               bbox_to_anchor=(0.01, 0.966),
               title=f"Maps 2–3: difference vs the Neutral benchmark, {hz.unit}",
               title_fontsize=9.5, alignment="left")
    span = f"{vals.index.min()}/{str(vals.index.min()+1)[2:]}–{vals.index.max()}/{str(vals.index.max()+1)[2:]}"
    fig.suptitle(hz.title, x=0.01, ha="left", y=0.999, fontsize=16, fontweight="bold")
    fig.text(0.01, 0.980, f"Source: {hz.source}, ENSO years (Jun–May) {span}.", fontsize=9.5,
             color=C.INK2)
    fig.text(0.01, 0.972, f"Benchmark = mean of {len(eq[C.NEUTRAL])} Neutral years; compared with "
             f"{len(eq['El Niño'])} El Niño and {len(eq['La Niña'])} La Niña years "
             "(equal groups, the clearest years of each phase). " + hz.note, fontsize=9, color=C.INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.935), h_pad=3.5)
    # separator lines between the three maps
    for upper, lower in ((axes[0], axes[1]), (axes[1], axes[2])):
        ym = (upper.get_position().y0 + lower.get_position().y1) / 2 + 0.004
        fig.add_artist(Line2D([0.005, 0.995], [ym, ym], transform=fig.transFigure,
                              color=C.INK2, lw=1.5))
    fig.savefig(path, dpi=100)
    plt.close(fig)


def main(years=None):
    global LAST
    years = years if years is not None else enso.enso_years()
    LAST = int(years[years.complete].year.max())
    out = []
    for i, hz in enumerate(build_hazards(), 1):
        p = C.OUT / f"hex_{i}_{hz.key}.png"
        figure(hz, years, p)
        hz.values.to_csv(C.OUT / f"hex_{i}_{hz.key}_values.csv", float_format="%.3f")
        out.append(p)
        print("  ", p.name, flush=True)
    return out


if __name__ == "__main__":
    main()
