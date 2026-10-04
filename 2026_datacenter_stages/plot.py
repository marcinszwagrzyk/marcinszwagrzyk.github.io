# -*- coding: utf-8 -*-
"""Wykres: który obszar kiedy wszedł w który etap."""
from __future__ import annotations

import os

# UWAGA: ten moduł NIE ustawia backendu matplotlib.
# Wcześniej było tu `matplotlib.use("Agg")`. Ponieważ notatnik importuje `plot`,
# backend Agg narzucał się całemu procesowi notatnika — a pod Agg `plt.show()`
# jest ciche i NIE RYSUJE NIC. Skutkiem był notatnik, który kończył się bez
# jednego błędu i bez prawie żadnej mapy: 11 obrazków zamiast ~50, same te,
# które szły przez `display(Image(...))`.
# Backend wybiera teraz ten, kto uruchamia: run.py ustawia Agg (bez ekranu),
# notatnik ustawia `%matplotlib inline`.
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

import stages as S

# Kolory etapów: od zielonego (nietknięte) przez ziemiste (wykopy) i szare
# (beton) do zielonego nasyconego (zieleń urządzona). Kolejność czytelna
# jak pasek postępu.
COLORS = ["#2f6b3a", "#9c7338", "#b8b0a2", "#6e737a", "#49a35b"]


def timeline(dfl, path: str):
    """Mapa etapów: wiersz = obszar, kolumna = epoka, kolor = etap."""
    ids = list(dict.fromkeys(dfl["id"]))
    eps = sorted(dfl["epoch"].unique())
    M = np.full((len(ids), len(eps)), np.nan)
    for _, r in dfl.iterrows():
        M[ids.index(r["id"]), eps.index(r["epoch"])] = r["stage"]

    fig, ax = plt.subplots(figsize=(1.0 + 0.52 * len(eps), 1.4 + 0.42 * len(ids)),
                           dpi=130)
    cmap = ListedColormap(COLORS)
    cmap.set_bad("#e6e3dd")
    ax.imshow(M, aspect="auto", cmap=cmap,
              norm=BoundaryNorm(np.arange(-0.5, 5.0, 1), cmap.N))

    ax.set_xticks(range(len(eps)))
    ax.set_xticklabels(eps, rotation=90, fontsize=7)
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels(ids, fontsize=8)
    ax.set_xticks(np.arange(-0.5, len(eps), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(ids), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.8)
    ax.tick_params(which="minor", length=0)

    ax.set_title("Etap budowy kampusów data center\n"
                 "Sentinel-2 L2A, kompozyty półroczne, Planetary Computer",
                 fontsize=10, pad=10)
    ax.legend(handles=[Patch(facecolor=COLORS[k], label=S.STAGE_NAMES[k])
                       for k in range(5)],
              loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=7.5,
              frameon=False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def site_curves(dfl, site_id: str, path: str):
    """Udziały klas w czasie dla jednego obszaru — do sprawdzania wyniku ręcznie."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    d = dfl[dfl["id"] == site_id].sort_values("epoch")
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=130)
    for key, lab, col in [("veg", "zieleń", "#2f6b3a"),
                          ("bare", "goły grunt", "#9c7338"),
                          ("built", "zabudowa potwierdzona", "#4a4f55"),
                          ("collar_green", "zieleń w kołnierzu hal", "#49a35b")]:
        ax.plot(d["epoch"], d[key] * 100, marker="o", ms=3, label=lab, color=col)
    ax2 = ax.twinx()
    ax2.step(d["epoch"], d["stage"], where="mid", color="#b03030",
             linewidth=1.2, alpha=0.7, label="etap")
    ax2.set_ylim(-0.3, 4.3)
    ax2.set_yticks(range(5))
    ax2.set_yticklabels([S.STAGE_SHORT[k] for k in range(5)], fontsize=7)
    ax.set_ylabel("udział obszaru [%]", fontsize=8)
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.set_title(site_id, fontsize=10)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
