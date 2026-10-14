# -*- coding: utf-8 -*-
"""Phase comparison charts: bar = group mean, dots = individual years."""
from __future__ import annotations

import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

import config as C
import enso
from analysis import EN_VS_N, P_COL

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 9.5,
    "axes.edgecolor": C.GRID, "axes.labelcolor": C.INK2, "xtick.color": C.INK2,
    "ytick.color": C.INK2, "text.color": C.INK, "figure.facecolor": C.SURFACE,
    "axes.facecolor": C.SURFACE, "savefig.facecolor": C.SURFACE,
    "savefig.bbox": "tight", "figure.dpi": 110,
})
TICKS = ["El Niño", "Neutral", "La Niña"]


def _style(ax):
    ax.grid(axis="y", color=C.GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)


def _year_values(yearly: pd.DataFrame, row: pd.Series) -> dict[str, list[float]]:
    col = f"{row['section']} | {row['measure']} | {row['source']}"
    s = yearly[col]
    out = {}
    for ph in C.PHASES:
        ys = [int(t.split("/")[0]) for t in str(row[f"years {ph}"]).split()]
        out[ph] = s.reindex(ys).tolist()
    return out


def panel(ax, row, values=None):
    means = [row[ph] for ph in C.PHASES]
    x = np.arange(3)
    ax.bar(x, means, width=0.62, color=[C.PHASE_COLORS[p] for p in C.PHASES],
           edgecolor=C.SURFACE, linewidth=2, zorder=2)
    top = max(means)
    if values:
        for i, ph in enumerate(C.PHASES):
            v = values[ph]
            jit = np.linspace(-0.16, 0.16, len(v)) if len(v) > 1 else [0]
            ax.scatter(i + np.asarray(jit), v, s=14, color=C.SURFACE, edgecolor=C.INK,
                       linewidth=0.8, zorder=3)
            top = max(top, max(v))
    for i, m in enumerate(means):
        ax.text(i, m + top * 0.02, f"{m:.1f}", ha="center", va="bottom", fontsize=8, color=C.INK)
    ax.set_xticks(x, TICKS)
    ax.set_ylim(0, top * 1.18 if top else 1)
    d, p = row[EN_VS_N], row[P_COL]
    sub = f"El Niño vs Neutral: {d:+.0f}%" if np.isfinite(d) else ""
    if np.isfinite(p):
        sub += f" · p={p:.2f}" + (" ✱" if p < 0.05 else "")
    ax.annotate(f"{sub}\n{row['unit']} · n={row['n per phase']}/phase", (0, 1),
                xycoords="axes fraction", xytext=(0, 5), textcoords="offset points",
                fontsize=7.5, color=C.INK2, va="bottom")
    ax.set_title("\n".join(textwrap.wrap(row["measure"], 36)), loc="left", fontsize=9,
                 fontweight="bold", pad=30)
    _style(ax)


def section_figure(yearly: pd.DataFrame, rows: pd.DataFrame, title: str, path, ncols=4):
    n = len(rows)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 3.5 * nrows), squeeze=False)
    for ax, (_, r) in zip(axes.flat, rows.iterrows()):
        vals = None if r["section"] == "Droughts" else _year_values(yearly, r)
        panel(ax, r, vals)
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold", y=1.0)
    fig.tight_layout(h_pad=2.5)
    fig.savefig(path)
    plt.close(fig)


def categories_figure(storms: pd.DataFrame, years: pd.DataFrame, src: str, path):
    """Saffir-Simpson category mix: basins x phases, equal-size groups of seasons."""
    first = C.GDACS_FIRST_YEAR["TC"] if src == "GDACS" else 1980
    last = int(years[years.complete].year.max())
    eq = enso.equal_groups(years, range(first, last + 1))
    groups = [("Hurricanes: Atlantic", {"NA"}), ("Hurricanes: East Pacific", {"EP"}),
              ("Typhoons: West Pacific", {"WP"}), ("Cyclones: North Indian", {"NI"}),
              ("Cyclones: Southern Hemisphere", {"SI", "SP"})]
    # sequential ramp: tropical storm (light) to cat. 5 (dark)
    ramp = ["#d8d6cf", "#f3c3a8", "#ec835a", "#d95926", "#b13a1a", "#6e1f0c"]
    fig, axes = plt.subplots(1, len(groups), figsize=(15, 3.9))
    n = len(eq["El Niño"])
    for ax, (name, b) in zip(axes, groups):
        bottom = np.zeros(3)
        for ci, cat in enumerate(C.SS_LABELS):
            v = np.array([((storms.basin.isin(b)) & (storms.ss_cat == cat)
                           & storms.enso_year.isin(eq[ph])).sum() / n for ph in C.PHASES])
            ax.bar(range(3), v, bottom=bottom, color=ramp[ci], edgecolor=C.SURFACE,
                   linewidth=1.5, width=0.66, label=cat)
            bottom += v
        for i, t in enumerate(bottom):
            ax.text(i, t, f"{t:.1f}", ha="center", va="bottom", fontsize=8)
        ax.set_xticks(range(3), TICKS)
        for lbl, ph in zip(ax.get_xticklabels(), C.PHASES):
            lbl.set_color(C.PHASE_COLORS[ph])
            lbl.set_fontweight("bold")
        ax.set_title(name, loc="left", fontsize=9, fontweight="bold")
        _style(ax)
    axes[0].set_ylabel("storms per season")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h[::-1], l[::-1], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False,
               title="Saffir-Simpson")
    yrs = " | ".join(f"{ph}: {', '.join(str(y) for y in eq[ph])}" for ph in C.PHASES)
    fig.suptitle(f"Storm categories by ENSO phase — {src}, {n} seasons per phase",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.text(0.01, -0.04, f"Seasons (start year, Jun–May): {yrs}", fontsize=7.5, color=C.INK2,
             wrap=True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def enso_timeline(years: pd.DataFrame, path, first=1980):
    """Peak RONI anomaly of every ENSO year + the year in progress."""
    y = years[years.year >= first]
    fig, ax = plt.subplots(figsize=(13, 3.4))
    ax.bar(y.year, y.peak, color=[C.PHASE_COLORS[p] for p in y.phase], width=0.78,
           edgecolor=C.SURFACE, linewidth=1)
    for thr in (0.5, -0.5):
        ax.axhline(thr, color=C.INK2, lw=0.6, ls=(0, (3, 3)))
    ax.axhline(0, color=C.INK2, lw=0.8)
    # current year: the peak has not happened yet, so show the latest season
    last = enso.read_index("roni").iloc[-1]
    cy = int(last.year) if last.mid_month >= C.ENSO_YEAR_START_MONTH else int(last.year) - 1
    if cy not in set(y[y.complete].year):
        ax.bar(cy, last.anom, width=0.78, color="none", edgecolor=C.PHASE_COLORS["El Niño"],
               hatch="////", linewidth=1)
        ax.annotate(f"{cy}/{str(cy + 1)[2:]} in progress: {last.season} {last.year} = {last.anom:+.2f}\n"
                    "IRI outlook: Niño3.4 above +2.5°C this winter", (cy, last.anom),
                    xytext=(2016.4, 1.75), textcoords="data", fontsize=8, color=C.INK,
                    arrowprops=dict(arrowstyle="-", color=C.INK2, lw=0.6))
    ax.legend(handles=[Patch(color=C.PHASE_COLORS[ph], label=ph) for ph in C.PHASES],
              frameon=False, ncol=3, loc="lower left", fontsize=8)
    ax.set_ylabel("peak RONI [°C]")
    ax.set_title("ENSO years (Jun–May) by the Relative Oceanic Niño Index (RONI, NOAA CPC)",
                 loc="left", fontweight="bold")
    _style(ax)
    fig.savefig(path)
    plt.close(fig)
