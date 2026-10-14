# -*- coding: utf-8 -*-
"""Forecast impact maps for El Niño 2026/27: winter (+3–6 months) and summer (+9–12 months).

    python forecast.py    # -> out/forecast_maps.png, out/after_strong_el_nino.csv

Where the map content comes from:
  * rainfall / drought / temperature regions: canonical El Niño teleconnections
    (NOAA CPC / Climate.gov, IRI, WMO El Niño Update) for the given season; for
    summer 2027 the impacts of a DECAYING strong El Niño and a possible La Niña;
  * numbers next to the cyclone basins: from our own analysis (out/comparison.csv,
    IBTrACS 1980–2025, equal-size groups of years) and, for summer 2027, from the
    composite of seasons that followed a strong El Niño (this module).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.colors import to_rgba
from matplotlib.patches import Patch
from shapely.geometry import Polygon

import basemap as B
import config as C
import enso
import events
import plots  # noqa: F401  (rcParams)
from analysis import EN_VS_N, LN_VS_N

# ------------------------------------------------ ENSO status (source, date)
# Typed in from the bulletins because they are text, not data; every number has a source and a date.
ENSO_STATUS = {
    "cpc": ("NOAA CPC ENSO Diagnostic Discussion, Oct 2026: El Niño Advisory — strong to very strong "
            "El Niño likely through Jan–Mar 2027 (>83%); Niño3.4 +2.1°C, Niño1+2 +3.9°C"),
    "iri": ("IRI/CCSR plume, mid-Sep 2026: El Niño 100% from Sep–Nov 2026 to Feb–Apr 2027, "
            "99% Mar–May, 90% Apr–Jun, 61% May–Jul 2027; positive IOD through Dec 2026"),
}

WET, DRY, WARM = "#1b8a7a", "#b7792b", "#e34948"
UP, DOWN, MID = "#b13a1a", "#2a78d6", "#8c8b85"

# Regions: (kind, description, lon/lat vertices, confidence 'high'|'medium'|'low')
WINTER = [
    ("wet", "Peru and Ecuador: torrential rain, floods, landslides (Jan–Apr); ocean +4°C off the coast",
     [(-82, 1), (-78, 2), (-76, -2), (-77, -10), (-80, -9), (-82, -4)], "high"),
    ("wet", "Southern US and northern Mexico: wet, stormy winter (California → Florida)",
     [(-123, 38), (-114, 35), (-100, 33), (-85, 33), (-79, 31), (-80, 25), (-97, 25),
      (-110, 28), (-119, 32)], "high"),
    ("wet", "SE South America: heavy rain and river floods (Uruguay, S Brazil, Paraguay, NE Argentina)",
     [(-61, -21), (-48, -23), (-48, -31), (-53, -35), (-61, -35), (-64, -27)], "high"),
    ("wet", "East Africa: very wet short rains Oct–Dec (El Niño + positive IOD)",
     [(35, 5), (45, 11), (51, 10), (47, 2), (41, -4), (39, -9), (32, -6), (32, 1)], "high"),
    ("wet", "Equatorial Pacific (Kiribati, Tuvalu): downpours over the warm water",
     [(172, -6), (200, -7), (235, -4), (235, 4), (200, 6), (172, 4)], "high"),
    ("wet", "SE China and Taiwan: wetter winter",
     [(106, 22), (121, 22), (123, 30), (115, 31), (106, 27)], "medium"),
    ("dry", "Indonesia, Malaysia, Philippines, Papua: drought, peat fires, haze",
     [(95, 5), (105, 6), (118, 8), (125, 14), (128, 6), (141, -2), (151, -5), (148, -10),
      (130, -9), (115, -9), (105, -7), (95, 0)], "high"),
    ("dry", "Northern and eastern Australia: drought, heat, bushfire risk",
     [(129, -12), (142, -10), (146, -15), (153, -26), (151, -35), (141, -37), (137, -30),
      (131, -21)], "high"),
    ("dry", "Southern Africa: drought Dec–Mar (Zimbabwe, Zambia, Malawi, Mozambique) — maize harvest at risk",
     [(21, -9), (35, -9), (40, -15), (36, -24), (31, -28), (24, -27), (19, -19)], "high"),
    ("dry", "Northern South America: drought (Colombia, Venezuela, Amazon, NE Brazil) — low rivers",
     [(-77, 8), (-70, 11), (-60, 9), (-50, 3), (-36, -5), (-38, -12), (-50, -10), (-66, -9),
      (-75, -2)], "high"),
    ("dry", "Central America and Caribbean: dry (Dry Corridor; Panama Canal water levels)",
     [(-92, 16), (-85, 17), (-75, 21), (-63, 18), (-62, 12), (-77, 8), (-84, 9), (-90, 13)], "medium"),
    ("dry", "Hawaii and western Micronesia: dry winter",
     [(-164, 15), (-151, 15), (-151, 26), (-164, 26)], "medium"),
    ("warm", "Canada, Alaska, northern US: mild winter, less snow",
     [(-150, 58), (-130, 62), (-95, 60), (-65, 53), (-70, 45), (-95, 45), (-124, 46),
      (-140, 55)], "high"),
    ("warm", "World: a record-warm 2027 is very likely (El Niño adds ~0.1–0.2°C to the global mean)",
     None, "high"),
]

SUMMER = [
    ("wet", "Yangtze valley, Japan, Korea: Meiyu/Baiu downpours after a strong El Niño (as in 1998, 2016, 2020)",
     [(106, 27), (120, 26), (132, 30), (141, 35), (141, 40), (129, 37), (118, 33), (106, 32)], "medium"),
    ("wet", "India and Pakistan: normal or stronger monsoon if the Pacific turns to La Niña",
     [(67, 24), (75, 33), (88, 28), (92, 23), (80, 9), (73, 16)], "low"),
    ("wet", "Sahel: wet rainy season Jul–Sep (floods in Niger, Chad, Sudan)",
     [(-17, 12), (0, 16), (20, 16), (36, 15), (36, 10), (15, 9), (-15, 10)], "low"),
    ("wet", "Indonesia and northern Australia: rains return after the drought",
     [(95, 4), (120, 6), (140, -1), (150, -8), (135, -13), (110, -9), (95, -3)], "medium"),
    ("wet", "Central America: wet season, flood risk with an active Atlantic",
     [(-92, 16), (-85, 17), (-78, 20), (-70, 18), (-77, 8), (-84, 9), (-90, 13)], "low"),
    ("dry", "East Africa: risk of failed short rains from Oct 2027 (if La Niña)",
     [(35, 5), (45, 11), (51, 10), (47, 2), (41, -4), (36, -3)], "low"),
    ("dry", "Argentina, Uruguay, S Brazil: spring drought Sep–Nov (if La Niña)",
     [(-64, -26), (-52, -27), (-53, -35), (-62, -39), (-66, -33)], "low"),
    ("dry", "Peru, Ecuador: the ocean cools — rains end, fisheries recover", None, "medium"),
    ("warm", "World: 2027 probably the warmest year on record (lagged El Niño effect)", None, "medium"),
]


# ------------------------------------------- composite: season after a strong El Niño
def after_strong_composite(ib: pd.DataFrame, years: pd.DataFrame) -> pd.DataFrame:
    """Cyclone seasons in the year AFTER a strong El Niño (peak RONI ≥ 1.5) vs the 1980–2025 mean."""
    an = enso.after_strong_el_nino(years)
    nxt = [int(l.split("/")[0]) for l in an.next_label]
    nxt = [y for y in nxt if y >= 1980]
    last = int(years[years.complete].year.max())
    allyrs = range(1980, last + 1)
    sel = {
        "Typhoons (W Pacific) Jun–Aug": (ib.basin == "WP") & ib.month.isin([6, 7, 8]),
        "Typhoons (W Pacific) whole season": ib.basin == "WP",
        "Atlantic hurricanes": ib.basin == "NA",
        "Atlantic hurricanes cat. 3–5": (ib.basin == "NA") & ib.ss_cat.isin(C.MAJOR),
        "East Pacific hurricanes": ib.basin == "EP",
        "North Indian cyclones": ib.basin == "NI",
    }
    rows = []
    for name, m in sel.items():
        s = ib[m].groupby("enso_year").size().reindex(allyrs).fillna(0)
        a, b = s.reindex(nxt).mean(), s.mean()
        rows.append(dict(measure=name, after_strong_EN=a, mean_1980_2025=b,
                         difference_pct=100 * (a / b - 1),
                         seasons=" ".join(f"{y}/{str(y + 1)[2:]}" for y in nxt)))
    return pd.DataFrame(rows)


def _pct(cmp_, measure, src="IBTrACS", col=EN_VS_N):
    r = cmp_[(cmp_.measure == measure) & (cmp_.source == src)]
    return float(r[col].iloc[0]) if len(r) else np.nan


# ---------------------------------------------------------------- drawing
def draw_map(ax, regions, tc_notes, title, subtitle, alpha_by_conf):
    B.draw(ax)
    B.outline(ax)
    listing = []
    k = 0
    for kind, text, pts, conf in regions:
        if pts is None:
            listing.append((None, kind, text, conf))
            continue
        k += 1
        p = B.smooth(pts)
        col = {"wet": WET, "dry": DRY, "warm": WARM}[kind]
        ls = "-" if conf == "high" else (0, (3, 2))
        poly = Polygon(p).buffer(0)
        if kind == "warm":
            kw = dict(facecolor="none", edgecolor=col, hatch="////", lw=0.9, alpha=0.75, zorder=2)
        else:
            kw = dict(facecolor=to_rgba(col, alpha_by_conf[conf]), edgecolor=col, lw=0.9, ls=ls,
                      zorder=2)
        for patch in B.geo_patches(poly, **kw):
            ax.add_patch(patch)
        ax.text(*B.centroid_xy(p), str(k), ha="center", va="center", fontsize=8, fontweight="bold",
                color="white", zorder=12,
                bbox=dict(boxstyle="circle,pad=0.25", fc=col, ec="white", lw=0.8))
        listing.append((k, kind, text, conf))
    for note in tc_notes:
        lon, lat, sym, txt, col = note[:5]
        left = len(note) > 5 and note[5] == "L"
        pos = B.xy(lon, lat)
        ax.text(*pos, sym, ha="center", va="center", fontsize=15, color=col, zorder=12,
                fontweight="bold")
        ax.annotate(txt, pos, xytext=(-10 if left else 10, 0), textcoords="offset points",
                    ha="right" if left else "left", va="center", fontsize=7.4, color=C.INK,
                    zorder=12, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col, lw=0.7,
                                         alpha=0.92))
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=22)
    ax.text(0, 1.012, subtitle, transform=ax.transAxes, fontsize=8.5, color=C.INK2, va="bottom")
    return listing


def legend_list(ax, listing):
    ax.axis("off")
    y = 1.0
    for k, kind, text, conf in listing:
        col = {"wet": WET, "dry": DRY, "warm": WARM}[kind]
        ax.text(0.0, y, f"{k}" if k else "●", fontsize=8, fontweight="bold", color="white",
                va="top", ha="center", transform=ax.transAxes,
                bbox=dict(boxstyle="circle,pad=0.25", fc=col, ec="none"))
        ax.text(0.03, y, text, fontsize=8.2, va="top", transform=ax.transAxes)
        ax.text(1.0, y, f"confidence: {conf}", fontsize=7.5, va="top", ha="right", color=C.INK2,
                transform=ax.transAxes)
        y -= 0.071


def make(cmp_: pd.DataFrame, ib: pd.DataFrame, years: pd.DataFrame, path):
    comp = after_strong_composite(ib, years)
    comp.to_csv(C.OUT / "after_strong_el_nino.csv", index=False, float_format="%.2f")
    cv = lambda m: float(comp[comp.measure == m].difference_pct.iloc[0])
    ln = lambda m: _pct(cmp_, m, col=LN_VS_N)

    na = _pct(cmp_, "North Atlantic — ACE energy")
    ep45 = _pct(cmp_, "Hurricanes: East/Central Pacific — cat. 4–5")
    wp45 = _pct(cmp_, "Typhoons: West Pacific — cat. 4–5")
    sh45 = _pct(cmp_, "Cyclones: Southern Hemisphere (Indian + Pacific) — cat. 4–5")
    na_ln = ln("North Atlantic — all storms")

    tc_w = [
        (-45, 24, "▼", f"Atlantic: end of season suppressed\nACE in El Niño years {na:+.0f}%", DOWN),
        (-128, 9, "▲", f"East Pacific: cat. 4–5 hurricanes\nin El Niño years {ep45:+.0f}% (to Nov)", UP),
        (165, 30, "▲", f"Typhoons cat. 4–5 {wp45:+.0f}%;\ngenesis shifted east,\nlonger tracks (Nov–Dec)", UP, "L"),
        (-150, -22, "▲", f"South Pacific cyclones shifted\neast: French Polynesia, Cook Is.,\nSamoa (cat. 4–5 S. Hem. {sh45:+.0f}%)", UP),
        (168, -36, "▼", "Fewer cyclones off\nQueensland and New Caledonia", DOWN, "L"),
    ]

    def sym(v, thr=10):
        return ("▲", UP) if v >= thr else ("▼", DOWN) if v <= -thr else ("◆", MID)

    wp_after, na_after = cv("Typhoons (W Pacific) Jun–Aug"), cv("Atlantic hurricanes")
    s_na, c_na = sym(na_ln)
    s_wp, c_wp = sym(ln("West Pacific — ACE energy"))
    s_ep, c_ep = sym(ln("East/Central Pacific — all storms"))
    tc_s = [
        (172, 12, s_wp, f"Typhoons with La Niña: ACE {ln('West Pacific — ACE energy'):+.0f}%\n"
                        f"after a strong El Niño (Jun–Aug): {wp_after:+.0f}%", c_wp, "L"),
        (-45, 25, s_na, f"Atlantic with La Niña: storms {na_ln:+.0f}%, "
                        f"cat. 4–5 {ln('Hurricanes: North Atlantic — cat. 4–5'):+.0f}%\n"
                        f"after a strong El Niño: on average {na_after:+.0f}%\n"
                        "(1983, 1992 quiet; 1998, 2010, 2016 active)", c_na),
        (-128, 9, s_ep, f"East Pacific with La Niña:\n{ln('East/Central Pacific — all storms'):+.0f}% "
                        f"hurricanes, ACE {ln('East/Central Pacific — ACE energy'):+.0f}%", c_ep),
    ]
    an = enso.after_strong_el_nino(years)
    nln = (an.next_phase == "La Niña").sum()
    nn = (an.next_phase == C.NEUTRAL).sum()
    nen = (an.next_phase == "El Niño").sum()
    last = enso.read_index("roni").iloc[-1]

    fig = plt.figure(figsize=(24, 10.2))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.9], hspace=0.06, wspace=0.07,
                          left=0.01, right=0.99, top=0.84, bottom=0.04)
    ax1 = fig.add_subplot(gs[0, 0])
    l1 = draw_map(ax1, WINTER, tc_w, "Winter 2026/27 · 3–6 months ahead (Nov 2026 – Apr 2027)",
                  f"El Niño at its peak: RONI {last.season} {last.year} = {last.anom:+.2f}; "
                  "IRI: El Niño 100% through Feb–Apr 2027, Niño3.4 likely above +2.5°C",
                  {"high": 0.55, "medium": 0.38, "low": 0.25})
    ax2 = fig.add_subplot(gs[0, 1])
    l2 = draw_map(ax2, SUMMER, tc_s, "Summer 2027 · 9–12 months ahead (Jun – Oct 2027)",
                  f"El Niño decaying: IRI 61% in May–Jul 2027; after {len(an)} strong El Niños since 1950 "
                  f"the next year was La Niña {nln}×, Neutral {nn}×, El Niño {nen}×",
                  {"high": 0.45, "medium": 0.32, "low": 0.2})
    legend_list(fig.add_subplot(gs[1, 0]), l1)
    legend_list(fig.add_subplot(gs[1, 1]), l2)
    # vertical separator between the winter and the summer column
    xm = (ax1.get_position().x1 + ax2.get_position().x0) / 2
    fig.add_artist(Line2D([xm, xm], [0.03, ax1.get_position().y1 + 0.05], transform=fig.transFigure,
                          color=C.INK2, lw=1.5))

    handles = [Patch(color=WET, alpha=0.55, label="wetter / floods"),
               Patch(color=DRY, alpha=0.55, label="drought / drier"),
               Patch(facecolor="none", edgecolor=WARM, hatch="////", label="warmer than usual"),
               Line2D([], [], color=C.INK2, ls="-", label="solid outline: high confidence"),
               Line2D([], [], color=C.INK2, ls=(0, (3, 2)), label="dashed: medium/low"),
               Line2D([], [], marker="^", ls="", color=UP, ms=9, label="more / stronger cyclones"),
               Line2D([], [], marker="v", ls="", color=DOWN, ms=9, label="fewer cyclones"),
               Line2D([], [], marker="D", ls="", color=MID, ms=7, label="weak signal (<10%)")]
    fig.legend(handles=handles, loc="upper left", ncol=8, frameon=False,
               bbox_to_anchor=(0.006, 0.94), fontsize=9)
    fig.suptitle("El Niño 2026/27 — expected impacts around the world", x=0.012, ha="left",
                 y=0.995, fontsize=18, fontweight="bold")
    fig.text(0.012, 0.952, "Regions: canonical El Niño impacts (NOAA CPC, IRI, WMO) for the season. "
             "Cyclone numbers: own analysis of IBTrACS 1980–2025 (equal groups of ENSO years, El Niño vs Neutral) "
             "and the composite of seasons after a strong El Niño.", fontsize=9, color=C.INK2)
    fig.text(0.012, 0.005, f"ENSO status: {ENSO_STATUS['cpc']}.  {ENSO_STATUS['iri']}.",
             fontsize=7.8, color=C.INK2)
    fig.savefig(path, dpi=110, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return comp


if __name__ == "__main__":
    years = enso.enso_years()
    cmp_ = pd.read_csv(C.OUT / "comparison.csv")
    print(make(cmp_, events.load_storms(), years, C.OUT / "forecast_maps.png").round(1).to_string(index=False))
