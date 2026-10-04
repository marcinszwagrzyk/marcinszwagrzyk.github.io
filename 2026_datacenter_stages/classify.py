# -*- coding: utf-8 -*-
"""Klasyfikacja pikseli i OSTROŻNE uznawanie zabudowy.

Model: las losowy na cechach spektralnych (features.py), uczony RAZ na próbkach
ze wszystkich dziesięciu obszarów. Jeden model dla wszystkich, a nie dziesięć
osobnych — bo celem jest POWIEDZIEĆ, KTÓRA INWESTYCJA JEST NA KTÓRYM ETAPIE,
a to wymaga, by „udział zabudowy 25%" znaczył to samo na każdym obszarze.
Dziesięć lokalnych modeli dałoby dziesięć nieporównywalnych skal.

====================== OSTROŻNOŚĆ PRZY ZABUDOWIE ======================
Świeży jasny beton, blacha i przesuszona, jasna glina mają w sześciu pasmach
Sentinela podpisy, które zachodzą na siebie. Pojedyncza klasyfikacja pomyli je
na placu budowy w sposób nieunikniony. Dlatego zabudowa przechodzi trzy filtry,
z których żaden nie jest spektralny:

 1. PEWNOŚĆ. Piksel wchodzi do zabudowy tylko przy prawdopodobieństwie klasy
    DACH >= MIN_P_ROOF. Niepewne zostawiamy poza zabudową, bo w tym zadaniu
    fałszywy alarm (ogłoszenie etapu, który nie nastąpił) jest gorszy niż
    spóźnienie o jedną epokę.
 2. SPÓJNOŚĆ PRZESTRZENNA. Hala data center ma 10-50 tys. m2, czyli 100-500
    pikseli. Pojedynczy jasny piksel wśród gruntu to szum, nie budynek —
    otwarcie morfologiczne go usuwa.
 3. TRWAŁOŚĆ W CZASIE. To filtr najważniejszy i jedyny naprawdę rozstrzygający:
    JASNA GLINA WYSYCHA I MOKNIE, BUDYNEK NIE ZNIKA. Piksel uznajemy za
    zabudowę dopiero, gdy utrzyma klasę DACH w BUILT_PERSISTENCE_EPOCHS
    kolejnych epokach — i od tego momentu pozostaje zabudową (zapadka).
    Zapadka zakłada, że hal się nie rozbiera; na kampusach hiperskalowych w
    budowie to założenie prawdziwe, ale JEST założeniem i trzeba o nim wiedzieć.
=======================================================================
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

import config as C
import features as F
import labels as L


def train(X: np.ndarray, y: np.ndarray, verbose: bool = True):
    """Naucz las losowy i POKAŻ, ile naprawdę jest wart.

    Zwraca (model, ocena). Ocena wraca razem z modelem, a nie jest liczona
    drugi raz na żądanie — notatnik ma pokazywać ocenę DOKŁADNIE tego modelu,
    który policzył raport.

    Dzielimy na uczący i sprawdzający, bo dokładność na danych uczących w lasie
    losowym to prawie zawsze 99% i nie znaczy nic. Macierz pomyłek pokazuje
    rzecz, która nas tu najbardziej interesuje: jak często GRUNT bierze się za
    DACH.
    """
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.25, random_state=C.SEED, stratify=y)

    clf = RandomForestClassifier(
        n_estimators=C.RF_TREES,
        min_samples_leaf=C.RF_MIN_LEAF,
        max_features="sqrt",
        class_weight="balanced",   # klasy są zrównane w losowaniu, ale obszary
                                   # różnią się dostępnością gruntu
        n_jobs=-1,
        random_state=C.SEED,
    )
    clf.fit(Xtr, ytr)

    acc = float(clf.score(Xte, yte))
    present = sorted(set(np.unique(ytr)) | set(np.unique(yte)))
    cm = confusion_matrix(yte, clf.predict(Xte), labels=present)
    rep = {
        "accuracy": acc,
        "n_test": int(len(yte)),
        "n_train": int(len(ytr)),
        "classes": [int(c) for c in present],
        "class_names": [L.CLASS_NAMES[c] for c in present],
        "confusion": cm,
        "importances": dict(zip(F.FEATURES, clf.feature_importances_.astype(float))),
        "counts": {L.CLASS_NAMES[int(c)]: int((y == c).sum())
                   for c in np.unique(y)},
    }
    if L.GRUNT in present and L.DACH in present:
        gi, di = present.index(L.GRUNT), present.index(L.DACH)
        rep["bare_as_roof"] = float(cm[gi, di] / max(1, cm[gi].sum()))

    if verbose:
        print(f"\n   dokładność na danych sprawdzających: {acc*100:.1f}%"
              f"   ({len(yte)} pikseli)")
        names = rep["class_names"]
        print("\n   macierz pomyłek (wiersz = prawda, kolumna = model, %):")
        print("            " + "".join(f"{n:>9s}" for n in names))
        for i, n in enumerate(names):
            row = cm[i] / max(1, cm[i].sum()) * 100
            print(f"   {n:>8s}  " + "".join(f"{v:8.1f}%" for v in row))

        imp = sorted(rep["importances"].items(), key=lambda t: -t[1])
        print("\n   waga cech: " + ", ".join(f"{k} {v*100:.0f}%" for k, v in imp[:6]))

        # To jest liczba, dla której ta macierz tu jest.
        if "bare_as_roof" in rep:
            print(f"\n   GRUNT wzięty za DACH: {rep['bare_as_roof']*100:.1f}% "
                  f"— to błąd, który filtry czasowe mają dociąć")
    return clf, rep


def predict(clf, ds, verbose: bool = False):
    """Zwróć (klasa, p_dach) dla jednego kompozytu. Poza maską: NOLABEL / NaN."""
    X = F.stack(ds)
    h, w, nf = X.shape
    flat = X.reshape(-1, nf)
    ok = np.isfinite(flat).all(axis=1)

    cls = np.full(h * w, L.NOLABEL, "uint8")
    proba = np.full((h * w, len(clf.classes_)), np.nan, "float32")
    if ok.any():
        p = clf.predict_proba(flat[ok])
        proba[ok] = p
        cls[ok] = clf.classes_[p.argmax(axis=1)]

    ri = list(clf.classes_).index(L.DACH) if L.DACH in clf.classes_ else None
    p_roof = proba[:, ri].reshape(h, w) if ri is not None \
        else np.zeros((h, w), "float32")
    return cls.reshape(h, w), p_roof


def _despeckle(mask: np.ndarray, min_px: int) -> np.ndarray:
    """Usuń skupiska mniejsze niż `min_px`. Hala to setki pikseli."""
    if not mask.any():
        return mask
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = np.bincount(lab.ravel())
    keep = np.isin(lab, np.flatnonzero(sizes >= min_px))
    keep[lab == 0] = False
    return keep


def built_series(p_roofs: list, verbose: bool = True) -> list:
    """Z serii map p(DACH) zrób serię map ZABUDOWY POTWIERDZONEJ.

    Trzy filtry z nagłówka pliku, w kolejności: pewność, spójność, trwałość.
    Wejście i wyjście to listy tej samej długości, w porządku epok.
    """
    k = max(1, C.BUILT_PERSISTENCE_EPOCHS)

    # 1 + 2: pewność i spójność przestrzenna
    raw = [_despeckle(p >= C.MIN_P_ROOF, C.MIN_ROOF_PIXELS) for p in p_roofs]

    # 3a: trwałość — klasa DACH w k kolejnych epokach
    persistent = []
    for t in range(len(raw)):
        if t + 1 < k:
            persistent.append(np.zeros_like(raw[t]))
            continue
        acc = raw[t].copy()
        for j in range(1, k):
            acc &= raw[t - j]
        persistent.append(acc)

    # 3b: zapadka — raz potwierdzony budynek zostaje
    out, ratchet = [], np.zeros_like(raw[0])
    for p in persistent:
        ratchet = ratchet | p
        out.append(ratchet.copy())
    return out


def frac(mask: np.ndarray, within: np.ndarray) -> float:
    """Udział maski w obszarze `within`. NaN, gdy obszar pusty."""
    n = within.sum()
    return float((mask & within).sum() / n) if n else float("nan")
