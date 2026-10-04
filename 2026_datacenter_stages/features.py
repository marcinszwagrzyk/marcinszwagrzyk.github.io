# -*- coding: utf-8 -*-
"""Cechy spektralne podawane klasyfikatorowi.

Zasada: podajemy i surowe odbicia, i wskaźniki. Wskaźniki (ilorazy) są odporne
na różnice oświetlenia między epokami, odbicia niosą informację o JASNOŚCI,
której iloraz z definicji gubi — a jasność jest tu tym, co odróżnia jasny dach
hali od czarnego asfaltu placu manewrowego.
"""
from __future__ import annotations

import numpy as np

# Kolejność cech jest kontraktem między treningiem i predykcją — nie zmieniać
# bez przetrenowania modelu.
FEATURES = [
    "B02", "B03", "B04", "B08", "B11", "B12",
    "NDVI",    # roślinność
    "NDBI",    # zabudowa/nieprzepuszczalne (SWIR vs NIR)
    "BSI",     # goła ziemia
    "NDWI",    # woda
    "BRIGHT",  # jasność — dach vs asfalt
    "SWIR_R",  # B12/B11 — rozróżnia materiały o podobnej jasności
]


def _nd(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Znormalizowana różnica, odporna na dzielenie przez zero."""
    return (a - b) / (a + b + 1e-6)


def stack(ds) -> np.ndarray:
    """Z kompozytu (xarray.Dataset w odbiciu 0..1) zrób tablicę (y, x, cecha)."""
    g = {b: ds[b].values.astype("float32") for b in
         ("B02", "B03", "B04", "B08", "B11", "B12")}

    ndvi = _nd(g["B08"], g["B04"])
    ndbi = _nd(g["B11"], g["B08"])
    # BSI (Bare Soil Index): goła ziemia jest wysoka w SWIR+czerwieni i niska
    # w NIR+niebieskim. To główny wskaźnik ETAPU ROBÓT ZIEMNYCH.
    bsi = _nd(g["B11"] + g["B04"], g["B08"] + g["B02"])
    ndwi = _nd(g["B03"], g["B08"])
    bright = (g["B02"] + g["B03"] + g["B04"] + g["B11"] + g["B12"]) / 5.0
    swir_r = g["B12"] / (g["B11"] + 1e-6)

    vals = {**g, "NDVI": ndvi, "NDBI": ndbi, "BSI": bsi,
            "NDWI": ndwi, "BRIGHT": bright, "SWIR_R": swir_r}
    return np.dstack([vals[f] for f in FEATURES]).astype("float32")


def valid_mask(X: np.ndarray) -> np.ndarray:
    """Piksele, w których wszystkie cechy są skończone."""
    return np.isfinite(X).all(axis=-1)
