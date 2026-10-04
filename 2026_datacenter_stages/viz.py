# -*- coding: utf-8 -*-
"""Mapki i obrazy do notatnika.

Wszystko czyta z tego, co zapisał run.py (out/maps/*.npz, out/cache/*.nc),
więc notatnik RYSUJE, a nie liczy — i rysuje dokładnie te liczby, które
poszły do raportu.
"""
from __future__ import annotations

import os

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

import config as C
import labels as L
import mpc
import stages as S

# Kolory klas. Dach jasnoszary, asfalt ciemnoszary — tak jak w rzeczywistości,
# bo to jasność je rozdziela i chcemy, żeby czytelnik to widział na mapce.
CLASS_ORDER = [L.ZIELEN, L.GRUNT, L.DACH, L.ASFALT, L.WODA]
CLASS_HEX = ["#3f7d4a", "#a9803f", "#dcd8d0", "#4d5155", "#2f6f9e"]
CLASS_CMAP = ListedColormap(CLASS_HEX)
CLASS_CMAP.set_bad("#ffffff")
CLASS_NORM = BoundaryNorm(np.arange(-0.5, 5.0, 1), CLASS_CMAP.N)


def load_maps(site_id: str) -> dict:
    """Mapy klas/zabudowy zapisane przez run.py."""
    p = os.path.join(C.OUT_DIR, "maps", f"{site_id}.npz")
    if not os.path.exists(p):
        raise FileNotFoundError(
            f"brak {p} — uruchom najpierw: python run.py {site_id}")
    z = np.load(p, allow_pickle=False)
    return {"cls": z["cls"], "built": z["built"], "p_roof": z["p_roof"],
            "epochs": [str(e) for e in z["epochs"]], "stages": z["stages"]}


def composite(site_id: str, epoch: str):
    """Kompozyt z cache albo None, gdy go nie ma."""
    p = os.path.join(C.CACHE_DIR, f"{site_id}_{epoch}.nc")
    return xr.open_dataset(p) if os.path.exists(p) else None


def rgb(ds, gain: float = 3.2, gamma: float = 1.25) -> np.ndarray:
    """Barwy naturalne z B04/B03/B02.

    Odbicie roślinności i betonu to 0,03-0,30, więc bez wzmocnienia obraz jest
    prawie czarny. `gain` rozciąga zakres, `gamma` rozjaśnia cienie, żeby było
    widać teksturę placu budowy, a nie tylko jasne dachy.
    """
    r, g, b = (ds[k].values.astype("float32") for k in ("B04", "B03", "B02"))
    im = np.dstack([r, g, b]) * gain
    im = np.clip(im, 0, 1) ** (1.0 / gamma)
    return np.nan_to_num(im, nan=1.0)


def false_color(ds, gain: float = 2.6, gamma: float = 1.2) -> np.ndarray:
    """SWIR/NIR/czerwień (B11,B08,B04) — „geologiczny" zestaw.

    Po co drugi zestaw: w barwach naturalnych świeży beton i jasna glina są
    oba szarobiałe. W tym zestawie goła ziemia idzie w róż i magentę, a
    roślinność w jaskrawą zieleń — czyli widać gołym okiem to, co klasyfikator
    ma rozdzielić.
    """
    a, b, c = (ds[k].values.astype("float32") for k in ("B11", "B08", "B04"))
    im = np.dstack([a, b, c]) * gain
    im = np.clip(im, 0, 1) ** (1.0 / gamma)
    return np.nan_to_num(im, nan=1.0)


def _clean(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(0.4)
        s.set_color("#999999")


def strip(site: dict, epochs: list, kind: str = "rgb", ncols: int = 8,
          title: str | None = None):
    """Pasek obrazów przez epoki: 'rgb', 'swir' albo 'cls'."""
    maps = load_maps(site["id"]) if kind == "cls" else None
    n = len(epochs)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(2.05 * ncols, 2.25 * nrows),
                             dpi=120)
    axes = np.atleast_1d(axes).ravel()

    for k, ep in enumerate(epochs):
        ax = axes[k]
        _clean(ax)
        if kind == "cls":
            if ep not in maps["epochs"]:
                ax.text(0.5, 0.5, "brak", ha="center", va="center", fontsize=7)
                continue
            i = maps["epochs"].index(ep)
            a = maps["cls"][i].astype("float32")
            a[a == L.NOLABEL] = np.nan
            ax.imshow(a, cmap=CLASS_CMAP, norm=CLASS_NORM, interpolation="nearest")
            st = maps["stages"][i]
            ax.set_title(f"{ep}  ·  {S.STAGE_SHORT[int(st)]}", fontsize=7.5)
            continue

        ds = composite(site["id"], ep)
        if ds is None:
            ax.text(0.5, 0.5, "brak", ha="center", va="center", fontsize=7)
            continue
        ax.imshow(rgb(ds) if kind == "rgb" else false_color(ds))
        ax.set_title(ep, fontsize=8)

    for ax in axes[n:]:
        ax.axis("off")
    if title:
        fig.suptitle(title, fontsize=11, y=1.0)
    if kind == "cls":
        fig.legend(handles=[Patch(facecolor=CLASS_HEX[i], edgecolor="#888",
                                  label=L.CLASS_NAMES[c])
                            for i, c in enumerate(CLASS_ORDER)],
                   loc="lower center", ncol=5, fontsize=8.5, frameon=False,
                   bbox_to_anchor=(0.5, 0.005))
    fig.tight_layout()
    if kind == "cls":
        # Miejsce na legendę pod siatką — bez tego podpisy klas są ucięte.
        fig.subplots_adjust(bottom=0.12 if nrows > 1 else 0.22)
    return fig


def built_growth(site: dict, maps: dict | None = None):
    """Jedna mapa: KIEDY dany piksel został potwierdzony jako zabudowa.

    To jest obraz, który najlepiej odpowiada na pytanie „jak rosła ta
    inwestycja" — kolor mówi, w której epoce hala się pojawiła.
    """
    maps = maps or load_maps(site["id"])
    b = maps["built"]
    eps = maps["epochs"]
    first = np.full(b.shape[1:], np.nan, "float32")
    for i in range(len(eps) - 1, -1, -1):
        first[b[i]] = i

    fig, ax = plt.subplots(figsize=(6.4, 6.0), dpi=120)
    _clean(ax)
    cm = plt.get_cmap("viridis").copy()
    cm.set_bad("#f0eeea")
    im = ax.imshow(np.ma.masked_invalid(first), cmap=cm,
                   vmin=0, vmax=max(1, len(eps) - 1), interpolation="nearest")
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    tick = range(0, len(eps), max(1, len(eps) // 8))
    cb.set_ticks(list(tick))
    cb.set_ticklabels([eps[i] for i in tick], fontsize=7)
    cb.set_label("epoka potwierdzenia zabudowy", fontsize=8)
    ax.set_title(f"{site['id']} — kiedy pojawiła się zabudowa\n"
                 f"(szare: nigdy nie potwierdzona)", fontsize=10)
    fig.tight_layout()
    return fig


def collar_view(site: dict, maps: dict | None = None, epoch: str | None = None):
    """Kołnierz wokół hal i zieleń w nim — dowód na etap „zieleń urządzona"."""
    maps = maps or load_maps(site["id"])
    i = maps["epochs"].index(epoch) if epoch else len(maps["epochs"]) - 1
    built = maps["built"][i]
    col = S.collar(built)
    cls = maps["cls"][i]
    green_in_collar = col & (cls == L.ZIELEN)

    rgbim = None
    ds = composite(site["id"], maps["epochs"][i])
    if ds is not None:
        rgbim = rgb(ds)

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.4), dpi=120)
    for ax in axes:
        _clean(ax)
    if rgbim is not None:
        axes[0].imshow(rgbim)
    axes[0].set_title(f"{site['id']} — barwy naturalne, {maps['epochs'][i]}",
                      fontsize=10)

    lay = np.zeros(built.shape + (4,), "float32")
    lay[built] = (0.30, 0.32, 0.35, 1.0)            # hale
    lay[col] = (0.85, 0.72, 0.30, 0.85)             # kołnierz
    lay[green_in_collar] = (0.25, 0.75, 0.35, 1.0)  # zieleń w kołnierzu
    if rgbim is not None:
        axes[1].imshow(rgbim * 0.45)
    axes[1].imshow(lay)
    nz = int(col.sum())
    if nz:
        fr = green_in_collar.sum() / nz
        t = (f"zabudowa + kołnierz {C.LANDSCAPE_COLLAR_M:.0f} m\n"
             f"zieleń w kołnierzu: {fr*100:.0f}%   ({nz} px)")
    else:
        t = "brak potwierdzonej zabudowy — nie ma kołnierza"
    axes[1].set_title(t, fontsize=10)
    fig.legend(handles=[Patch(facecolor="#4d5155", label="zabudowa potwierdzona"),
                        Patch(facecolor="#d9b84d", label="kołnierz wokół hal"),
                        Patch(facecolor="#40bf59", label="zieleń w kołnierzu")],
               loc="lower center", ncol=3, fontsize=8.5, frameon=False,
               bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout()
    return fig


def overview(sites: list, first_epoch: str, last_epoch: str, ncols: int = 5):
    """Przegląd: każdy obszar „przed" i „teraz", barwy naturalne.

    To jest mapa poglądowa całego zadania — jednym spojrzeniem widać, które
    obszary się zmieniły, a które nie, niezależnie od tego, co orzekł model.
    """
    n = len(sites)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows * 2, ncols,
                             figsize=(2.3 * ncols, 2.55 * nrows * 2), dpi=120)
    axes = np.atleast_2d(axes)

    for k, site in enumerate(sites):
        r, c = divmod(k, ncols)
        for j, ep in enumerate((first_epoch, last_epoch)):
            ax = axes[r * 2 + j, c]
            _clean(ax)
            ds = composite(site["id"], ep)
            if ds is None:
                ax.text(0.5, 0.5, f"brak\n{ep}", ha="center", va="center",
                        fontsize=7)
            else:
                ax.imshow(rgb(ds))
            lab = f"{site['id']}\n{ep}" if j == 0 else ep
            ax.set_title(lab, fontsize=7.5)

    for k in range(n, nrows * ncols):
        r, c = divmod(k, ncols)
        axes[r * 2, c].axis("off")
        axes[r * 2 + 1, c].axis("off")
    fig.suptitle(f"Obszary: {first_epoch} (góra) vs {last_epoch} (dół)",
                 fontsize=12, y=1.0)
    fig.tight_layout()
    return fig


def confusion(rep: dict):
    """Macierz pomyłek modelu — z pliku, nie z nowego treningu."""
    cm = np.asarray(rep["confusion"], float)
    pct = cm / np.maximum(1, cm.sum(axis=1, keepdims=True)) * 100
    names = rep["class_names"]

    fig, ax = plt.subplots(figsize=(5.6, 4.8), dpi=120)
    im = ax.imshow(pct, cmap="Blues", vmin=0, vmax=100)
    ax.set_xticks(range(len(names)), names, fontsize=8, rotation=35, ha="right")
    ax.set_yticks(range(len(names)), names, fontsize=8)
    ax.set_xlabel("model", fontsize=9)
    ax.set_ylabel("prawda", fontsize=9)
    for i in range(len(names)):
        for j in range(len(names)):
            ax.text(j, i, f"{pct[i, j]:.0f}", ha="center", va="center",
                    fontsize=8, color="white" if pct[i, j] > 55 else "#333")
    ax.set_title(f"Macierz pomyłek   ·   dokładność "
                 f"{rep['accuracy']*100:.1f}%", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03, label="% wiersza")
    fig.tight_layout()
    return fig


def importances(rep: dict):
    """Waga cech — pokazuje, na czym model naprawdę się opiera."""
    it = sorted(rep["importances"].items(), key=lambda t: t[1])
    fig, ax = plt.subplots(figsize=(6.0, 3.8), dpi=120)
    ax.barh([k for k, _ in it], [v * 100 for _, v in it], color="#4a6f8a")
    ax.set_xlabel("waga [%]", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.set_title("Na czym opiera się klasyfikator", fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


# ====================== KONTROLA NIEZALEŻNA ======================
# Potok sam o sobie mówi, że zabudowa jest „potwierdzona". To jest twierdzenie,
# które trzeba sprawdzić czymś spoza potoku — a mamy czym: obrysami budynków
# z OSM, których klasyfikator NIE widział dla tego obszaru (pola treningowe
# pochodzą z otoczenia, z wyłączeniem samego kampusu).
#
# Dlaczego to jest potrzebne akurat tutaj: pomyłka GRUNT -> DACH wynosi 10,5%
# w pojedynczej klasyfikacji, a zapadka etapów sprawia, że raz potwierdzona
# zabudowa NIE ZNIKA. Fałszywie potwierdzony płat suchej, jasnej gliny zostaje
# w wyniku na zawsze. Te dwie liczby mówią, czy tak się stało.
def osm_check(site: dict, maps: dict | None = None, epoch: str | None = None,
              tol_px: int = 1, min_area_m2: float | None = None,
              core: "np.ndarray | None" = None) -> dict:
    """Porównaj zabudowę potwierdzoną z obrysami budynków OSM.

    celnosc  — ile z potwierdzonej zabudowy leży pod obrysem budynku
               (niska = potok bierze grunt za dach)
    pokrycie — ile z obrysów hal potok zdążył potwierdzić
               (niskie bywa POPRAWNE: OSM zna hale, których jeszcze nie ma,
               bo są otagowane jako w budowie albo dopiero powstają)
    """
    from scipy import ndimage
    import labels as _L
    import osm as _osm

    maps = maps or load_maps(site["id"])
    i = maps["epochs"].index(epoch) if epoch else len(maps["epochs"]) - 1
    ds = composite(site["id"], maps["epochs"][i])
    if ds is None:
        return {}

    try:
        bld = _osm.buildings(site, mpc.aoi_bbox(site, 2.0), verbose=False)
    except Exception:                                   # noqa: BLE001
        return {}
    # Domyślnie BEZ progu powierzchni. Próg 2000 m² wycinał z odniesienia małe
    # budynki, których klasyfikator słusznie nie pomija — i zaniżał celność:
    # na Papillion dał 40%, a po uwzględnieniu wszystkich budynków obraz się
    # zmienia. Odniesienie ma być możliwie pełne, inaczej „fałszywe trafienie"
    # bywa po prostu domem spoza odniesienia.
    ref = _L._rasterize(bld, ds, shrink_m=0.0,
                        min_area_m2=(C.ROOF_MIN_AREA if min_area_m2 is None
                                     else min_area_m2))
    if not ref.any():
        return {"epoch": maps["epochs"][i], "ref_px": 0}

    # Tolerancja jednego piksela: obrys OSM i siatka Sentinela nie pokrywają się
    # co do metra, a piksel 10 m na krawędzi dachu jest i tak mieszany.
    ref_t = ndimage.binary_dilation(ref, iterations=tol_px)
    built = maps["built"][i]
    if core is not None:          # liczenie tylko w rdzeniu kampusu
        built = built & core
        ref = ref & core
        ref_t = ref_t & core
    nb = int(built.sum())
    return {
        "epoch": maps["epochs"][i],
        "ref_px": int(ref.sum()),
        "built_px": nb,
        "celnosc": float((built & ref_t).sum() / nb) if nb else float("nan"),
        "pokrycie": float((ref & ndimage.binary_dilation(built, iterations=tol_px)
                           ).sum() / ref.sum()),
    }
