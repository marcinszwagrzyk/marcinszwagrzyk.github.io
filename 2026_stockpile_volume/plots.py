# -*- coding: utf-8 -*-
"""Charts to out/ — reads stockpile_quarterly.csv, stockpile_dem.csv, data/results.npz."""
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

import config as C
import style as P

tab = pd.read_csv(C.OUT / "stockpile_quarterly.csv")
dem = pd.read_csv(C.OUT / "stockpile_dem.csv")
summ = json.load(open(C.OUT / "stockpile_summary.json", encoding="utf-8"))
test = json.load(open(C.OUT / "sensitivity_test.json"))
w = np.load(C.DATA / "results.npz")
m10 = w["m10"]
labels = list(tab.quarter)
SIG = summ["s1_sigma_m_per_quarter"]
AREA = summ["area_km2"]
EXT = C.EXTENT_KM
KM = C.RES_S1 / 1000


def s2_rgb(lab):
    f = C.DATA / "s2" / f"{lab}.npz"
    if not f.exists():
        return None
    s = np.load(f)["refl"]
    return np.clip(np.nan_to_num(s[..., [2, 1, 0]]) / 0.25, 0, 1) ** 0.8


def outline(ax, m, color, lw=1.6):
    ax.contour(np.flipud(m), [0.5], colors=color, linewidths=lw, extent=EXT, origin="lower")


def box(ax, win, color, label):
    r, c = win
    x0 = EXT[0] + c.start * KM
    y1 = EXT[3] - r.start * KM
    ax.add_patch(Rectangle((x0, y1 - (r.stop - r.start) * KM), (c.stop - c.start) * KM, (r.stop - r.start) * KM,
                           fill=False, ec=color, lw=1.4, ls=(0, (3, 2))))
    ax.text(x0 + 0.02, y1 - 0.02, label, color=color, fontsize=8, va="top", fontweight="bold")


def km_axes(ax):
    ax.set_xlabel("km east of the site"); ax.set_ylabel("km north of the site"); ax.grid(False)


def fig_map():
    good = [l for l in labels if s2_rgb(l) is not None]
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(s2_rgb(good[-1]), extent=EXT)
    outline(ax, m10, P.ORANGE, 2.2)
    o = summ["s1_window_px"]
    box(ax, (slice(o[0], o[1]), slice(o[2], o[3])), "#ffffff", "S1 measurement window")
    for i, win in enumerate(C.CONTROL_WINDOWS):
        box(ax, win, P.BLUES[3], f"control {i + 1}")
    ax.plot(0, 0, "+", color="#ffffff", ms=14, mew=2)
    km_axes(ax)
    ax.set_title(f"Stockpile outline from Sentinel-2 ({AREA * 100:.0f} ha), Sentinel-2 {good[-1]}")
    P.save(fig, C.OUT / "01_map.png")


def fig_dem():
    z = {k: w[f"z_{k}"] for k in ("srtm", "alos", "cop")}
    m30 = w["m30"]
    fig = plt.figure(figsize=(14, 6.2))
    for i, (k, t) in enumerate((("alos", "~2008 (ALOS)"), ("cop", "~2012 (Copernicus)"))):
        ax = fig.add_axes([0.03 + i * 0.27, 0.1, 0.25, 0.78])
        im = ax.imshow(np.where(m30, z[k] - z["srtm"], np.nan), cmap=P.HEIGHT, vmin=0, vmax=22, extent=EXT)
        outline(ax, m10, P.INK2, 0.8)
        ax.set_title(f"height above the 2000 ground\n{t}", fontsize=10); ax.grid(False)
        ax.set_xticks([-1, 0, 1]); ax.set_yticks([-1, 0, 1])
    cb = fig.colorbar(im, ax=fig.axes, shrink=0.7, location="left", pad=0.08, label="m")
    cb.outline.set_visible(False)
    ax = fig.add_axes([0.66, 0.14, 0.32, 0.72])
    ax.bar(dem.year, dem.volume_Mm3, width=1.6, color=P.BLUE, edgecolor=P.SURF, linewidth=2)
    for r in dem.itertuples():
        ax.text(r.year, r.volume_Mm3 + 0.15, f"{r.volume_Mm3:.1f} Mm³\nmean {r.mean_height_m:.1f} m",
                ha="center", va="bottom", fontsize=9, color=P.INK)
    ax.set_xticks(dem.year); ax.set_xticklabels(["2000\nSRTM", "~2008\nALOS", "~2012\nCopernicus"])
    ax.set_ylim(0, dem.volume_Mm3.max() * 1.3)
    ax.set_ylabel("Mm³ above the 2000 ground"); ax.set_title("Measured stockpile volume (DEM)")
    ax.axhline(0, color=P.BASE, lw=1)
    P.save(fig, C.OUT / "02_dem_history.png")


def fig_s1():
    x = np.arange(len(tab))
    h, s = tab.dh_m.values, SIG
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw=dict(height_ratios=[1.2, 1]))
    a1.fill_between(x, -2 * s, 2 * s, color=P.GRID, lw=0, label=f"±2σ method noise (σ = {s:.1f} m per quarter)")
    a1.plot(x, h, color=P.BLUE, lw=1.6, marker="o", ms=4, label="stockpile Δh (quarter)")
    yr = tab.groupby("year").dh_m.median()
    a1.plot([x[tab.year == y].mean() for y in yr.index], yr.values, color=P.ORANGE, lw=2.4, label="annual median")
    a1.axhline(0, color=P.INK2, lw=0.8)
    a1.set_ylabel(f"height change since {labels[0]} [m]")
    a1.set_title("Sentinel-1: stockpile height change from the geocoding shift (radargrammetry)")
    a1.legend(loc="upper left", fontsize=8.5, ncol=3)
    lim = max(6, np.nanmax(np.abs(h)) + 1)
    a1.set_ylim(-lim, lim)
    t, se = summ["s1_trend_m_per_year"], summ["s1_trend_se_m_per_year"]
    a1.text(0.99, 0.04, f"trend {t:+.2f} ± {se:.2f} m/yr  →  {t * AREA:+.2f} ± {se * AREA:.2f} Mm³/yr",
            transform=a1.transAxes, ha="right", fontsize=10, fontweight="bold", color=P.INK)
    a2.bar(x, tab.dv_Mm3, color=[P.BLUE if v >= 0 else P.RED for v in tab.dv_Mm3.fillna(0)], width=0.75,
           edgecolor=P.SURF)
    a2.axhline(0, color=P.BASE, lw=1)
    a2.set_ylabel(f"ΔV since {labels[0]} [Mm³]")
    a2.set_xticks(x[::2]); a2.set_xticklabels(tab.quarter[::2], rotation=60, fontsize=8)
    P.save(fig, C.OUT / "03_s1_height.png")


def fig_cover():
    x = np.arange(len(tab))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True)
    a1.plot(x, tab.coal_ha, color=P.INK, lw=2, marker="o", ms=4, label="black material (coal)")
    a1.plot(x, tab.water_ha, color=P.BLUE, lw=2, marker="o", ms=4, label="water")
    a1.set_ylabel("ha inside the outline"); a1.legend(loc="center left")
    a1.set_ylim(0, AREA * 100 * 1.1)
    a1.set_title(f"Sentinel-2: surface cover of the stockpile ({AREA * 100:.0f} ha), quarter by quarter")
    a2.bar(x, tab.activity_pct, color=P.BLUE, width=0.75, edgecolor=P.SURF)
    a2.set_ylabel("% of stockpile with S1 change")
    a2.set_title("Sentinel-1: activity (dumping, reclaiming, dozers) — change since the previous quarter",
                 fontsize=10)
    a2.set_xticks(x[::2]); a2.set_xticklabels(tab.quarter[::2], rotation=60, fontsize=8)
    P.save(fig, C.OUT / "04_cover_activity.png")


def fig_mosaic():
    sel = []
    for y in sorted(set(tab.year)):
        for qq in ("Q3", "Q2", "Q4", "Q1"):
            if s2_rgb(f"{y}{qq}") is not None:
                sel.append(f"{y}{qq}"); break
    n = len(sel)
    cols = (n + 1) // 2
    fig, axs = plt.subplots(2, cols, figsize=(3 * cols, 6.6))
    a, b = int(C.N10 * 0.2), int(C.N10 * 0.87)
    for ax, lab in zip(axs.ravel(), sel):
        ax.imshow(s2_rgb(lab)[a:b, a:b]); ax.set_title(lab, fontsize=10); ax.axis("off")
        ax.contour(m10[a:b, a:b], [0.5], colors=P.ORANGE, linewidths=0.8)
    for ax in axs.ravel()[n:]:
        ax.axis("off")
    fig.suptitle("Sentinel-2 year by year (orange line = stockpile outline)", x=0.02, ha="left",
                 fontweight="bold", fontsize=13)
    P.save(fig, C.OUT / "05_s2_mosaic.png")


def fig_test():
    fig, ax = plt.subplots(figsize=(6.5, 5))
    inj = [r["injected_m"] for r in test]
    rec = [r["recovered_after_m"] for r in test]
    ax.plot([-7, 7], [-7, 7], color=P.BASE, lw=1, ls=(0, (4, 3)), label="ideal")
    ax.scatter(inj, rec, s=70, color=P.BLUE, zorder=3, edgecolor=P.SURF, linewidth=2, label="recovered by the network")
    g = summ["method_sensitivity"]
    ax.plot([-7, 7], [-7 * g, 7 * g], color=P.ORANGE, lw=2, label=f"sensitivity {g:.2f} (calibration)")
    ax.set_xlabel("injected height step [m]"); ax.set_ylabel("recovered step [m]")
    ax.set_title("Sensitivity test on real Sentinel-1 images")
    ax.legend(fontsize=8.5, loc="upper left")
    P.save(fig, C.OUT / "06_sensitivity_test.png")


if __name__ == "__main__":
    fig_map(); fig_dem(); fig_s1(); fig_cover(); fig_mosaic(); fig_test()
