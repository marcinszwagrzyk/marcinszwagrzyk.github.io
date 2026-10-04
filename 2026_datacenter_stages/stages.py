# -*- coding: utf-8 -*-
"""Maszyna etapów budowy: z serii klasyfikacji -> etap na każdą epokę.

PIĘĆ ETAPÓW (dokładnie w kolejności z zadania):
  0 PRZED BUDOWĄ      — teren w stanie wyjściowym
  1 ROBOTY ZIEMNE     — wykopy, zdjęty humus, nasypy, drogi technologiczne
  2 ZABUDOWA ROŚNIE   — potwierdzone pierwsze hale, wciąż duży udział gruntu
  3 BRYŁA ZAMKNIĘTA   — zabudowa osiągnęła docelowy udział, grunt maleje
  4 ZIELEŃ URZĄDZONA  — ostatni element budowy: zieleń WRÓCIŁA wokół hal

================== TRZY PUŁAPKI, KTÓRE TU OMIJAMY ==================

PUŁAPKA 0: JEDEN PRÓG ZABUDOWY NIE PASUJE DO DWÓCH KAMPUSÓW.
Pierwsza wersja miała „zabudowa >= 18% obszaru = bryła zamknięta". Pomiar
obrysami OSM pokazał, że to wartość wzięta z powietrza i zawyżona o rząd
wielkości dla dużego kadru: w kadrze 12×12 km nad Ashburn hale (budynki
> 10 000 m2) zajmują 1,6% powierzchni. Potok orzekł wtedy „PRZED BUDOWĄ"
dla Data Center Alley — mając udział zabudowy 1,6%, czyli DOKŁADNIE tyle,
ile wynosi prawda z OSM. Model miał rację, próg był bzdurą.
Dlatego progi zabudowy są teraz UŁAMKIEM CELU danego kampusu, a cel to
powierzchnia hal zmapowanych w OSM podzielona przez powierzchnię AOI
(`target_built_frac`, liczone w discover.py). Kampus gęsty ma cel 27%,
rozrzucony 11% — i jeden i drugi dostaje właściwą miarę „zamknięcia bryły".

PUŁAPKA 1: PRÓG GOŁEJ ZIEMI NIE MOŻE BYĆ BEZWZGLĘDNY.

W Mesa (Arizona) i Abilene (Teksas) goła ziemia to NATURALNY stan terenu —
udział 40% gołego gruntu w 2018 roku nie znaczy tam nic. Bezwzględny próg
„25% gruntu = ruszyły roboty" ogłosiłby roboty ziemne na pustyni w pierwszej
epoce szeregu. Dlatego roboty ziemne rozpoznajemy po PRZYROŚCIE względem
własnego poziomu wyjściowego obszaru, a nie po wartości bezwzględnej.
Z tego samego powodu etap 0 jest zdefiniowany negatywnie („nie spełnia
warunków etapu 1+"), a nie przez próg zieleni — w Arizonie nigdy nie będzie
55% zieleni, a obszar i tak jest przed budową.

PUŁAPKA 2: ZIELEŃ W PIERŚCIENIU WOKÓŁ DZIAŁKI NIE JEST ZIELENIĄ URZĄDZONĄ.
Przed budową cały obszar jest zielony — pole albo las. Sam fakt, że wokół hal
rośnie zieleń, nie odróżnia trawnika od nietkniętej łąki. Odróżnia je POWRÓT:
zieleń musi najpierw ZNIKNĄĆ (plac budowy, składowisko, droga technologiczna),
a potem wrócić. Dlatego mierzymy ją nie w pierścieniu o stałym promieniu, ale
w KOŁNIERZU WOKÓŁ POTWIERDZONEJ ZABUDOWY (dylatacja maski budynków), i liczymy
PRZYROST względem minimum, jakie ten kołnierz osiągnął w czasie budowy.
To jest dosłowne odwzorowanie „wzrostu zieleni urządzonej dookoła zabudowy".
====================================================================
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

import config as C
import labels as L

PRZED, ZIEMNE, ROSNIE, ZAMKNIETA, ZIELEN_U = 0, 1, 2, 3, 4
STAGE_NAMES = {
    PRZED: "PRZED BUDOWĄ",
    ZIEMNE: "ROBOTY ZIEMNE",
    ROSNIE: "ZABUDOWA ROŚNIE",
    ZAMKNIETA: "BRYŁA ZAMKNIĘTA",
    ZIELEN_U: "ZIELEŃ URZĄDZONA",
}
STAGE_SHORT = {PRZED: "0/przed", ZIEMNE: "1/ziemne", ROSNIE: "2/rośnie",
               ZAMKNIETA: "3/zamknięta", ZIELEN_U: "4/zieleń"}


def collar(built: np.ndarray, px_m: float = 10.0) -> np.ndarray:
    """Kołnierz wokół potwierdzonej zabudowy — tam szukamy zieleni urządzonej.

    Trawnik, szpaler i zbiornik retencyjny powstają PRZY hali, nie gdziekolwiek
    na działce. Dylatacja maski budynków trafia dokładnie w ten pas.
    """
    if not built.any():
        return np.zeros_like(built)
    r = max(1, int(round(C.LANDSCAPE_COLLAR_M / px_m)))
    grown = ndimage.binary_dilation(built, ndimage.generate_binary_structure(2, 2),
                                    iterations=r)
    return grown & ~built


def metrics(cls_maps: list, built_maps: list, core: np.ndarray) -> list:
    """Dla każdej epoki policz udziały klas w obszarze inwestycji.

    Zwraca listę słowników — jeden na epokę, w porządku czasu.
    """
    out = []
    for cls, built in zip(cls_maps, built_maps):
        ok = (cls != L.NOLABEL) & core
        n = int(ok.sum())
        col = collar(built) & core
        g = {
            "n_px": n,
            "veg": float(((cls == L.ZIELEN) & ok).sum() / n) if n else np.nan,
            "bare": float(((cls == L.GRUNT) & ok).sum() / n) if n else np.nan,
            "roof_raw": float(((cls == L.DACH) & ok).sum() / n) if n else np.nan,
            "pave": float(((cls == L.ASFALT) & ok).sum() / n) if n else np.nan,
            "water": float(((cls == L.WODA) & ok).sum() / n) if n else np.nan,
            # zabudowa POTWIERDZONA (pewność + spójność + trwałość)
            "built": float((built & ok).sum() / n) if n else np.nan,
        }
        nc = int(col.sum())
        g["collar_px"] = nc
        g["collar_green"] = float(((cls == L.ZIELEN) & col).sum() / nc) \
            if nc >= C.MIN_COLLAR_PIXELS else np.nan
        out.append(g)
    return out


def _baseline(series: list, key: str) -> float:
    """Poziom wyjściowy obszaru: mediana pierwszych BASELINE_EPOCHS epok.

    Mediana, nie pierwsza wartość — jedna epoka może trafić w suszę albo
    w śnieg, a wtedy cały obszar dostałby fałszywy punkt odniesienia.
    """
    v = [s[key] for s in series[:C.BASELINE_EPOCHS] if np.isfinite(s[key])]
    return float(np.median(v)) if v else np.nan


def built_thresholds(site: dict) -> tuple:
    """(próg „stoją hale", próg „bryła zamknięta") dla tego kampusu.

    Liczone jako ułamek CELU — powierzchni hal z OSM odniesionej do AOI.
    Podłogi bezwzględne są po to, żeby kampus o bardzo małym celu nie
    przechodził etapów na samym szumie klasyfikacji.
    """
    tgt = effective_target(site)
    th_s = max(C.TH_BUILT_FLOOR, C.TH_BUILT_REL_STRUCTURES * tgt)
    th_m = max(C.TH_BUILT_FLOOR * 2.0, C.TH_BUILT_REL_MATURE * tgt)
    return th_s, th_m


def effective_target(site: dict) -> float:
    """Cel skorygowany o POKRYCIE detektora.

    Detektor trafia w okolo DETECTOR_RECALL powierzchni budynkow znanych z OSM
    (zmierzone w calibrate.py). Kompletny kampus da wiec zabudowe potwierdzona
    rowna mniej wiecej pokrycie x cel, a nie caly cel. Gdyby porownywac go
    z pelnym celem, ten sam niedobor liczylby sie dwa razy - i tak wlasnie
    w pelni zabudowane Data Center Alley wychodzilo jako "zabudowa rosnie"
    przy postepie 64%.
    """
    tgt = float(site.get("target_built_frac") or 0.0)
    return tgt * float(getattr(C, "DETECTOR_RECALL", 1.0) or 1.0)


def classify_stages(series: list, site: dict, verbose: bool = False) -> list:
    """Przypisz etap każdej epoce. Wynik jest NIEMALEJĄCY.

    Dlaczego niemalejący: budowa nie cofa się. Jedna epoka z chmurami albo
    ze świeżym śniegiem potrafi zaniżyć udział zabudowy — bez zapadki obszar
    „wracałby" z etapu 3 na 1 i raport byłby nieczytelny. Cofnięcie etapu
    wymagałoby rozbiórki, czego na kampusie w budowie nie zakładamy.
    """
    bare0 = _baseline(series, "bare")
    th_struct, th_mature = built_thresholds(site)
    collar_min = np.inf
    stages, raw = [], []

    # Długość nieprzerwanej serii epok z podwyższonym gruntem, kończącej się na
    # danej epoce. Pole uprawne daje serie długości 1-2 i wraca do zieleni;
    # plac budowy daje serię, która sama się nie kończy. Zmierzone na Red Oak
    # przed budową: 16,5% -> 49,7% -> 19,3% -> 54,9% -> 61,2% -> 27,1%.
    elevated_run, _run = [], 0
    for _s in series:
        _b = _s["bare"]
        _hi = (np.isfinite(_b) and np.isfinite(bare0)
               and _b - bare0 >= C.TH_BARE_DELTA and _b >= C.TH_BARE_MIN)
        _run = _run + 1 if _hi else 0
        elevated_run.append(_run)

    for k_ep, s in enumerate(series):
        built, bare = s["built"], s["bare"]
        cg = s["collar_green"]

        # Minimum zieleni w kołnierzu w trakcie budowy — punkt odniesienia dla
        # POWROTU zieleni. Aktualizujemy tylko gdy kołnierz w ogóle istnieje.
        if np.isfinite(cg):
            collar_min = min(collar_min, cg)

        st = PRZED
        # ROBOTY ZIEMNE: grunt musi PRZYROSNĄĆ względem poziomu wyjściowego
        # obszaru (pułapka 1) ORAZ UTRZYMAĆ SIĘ przez kilka epok (pułapka 3).
        if elevated_run[k_ep] >= C.BARE_PERSISTENCE_EPOCHS:
            st = ZIEMNE
        if np.isfinite(built) and built >= th_struct:
            st = ROSNIE
        if np.isfinite(built) and built >= th_mature:
            st = ZAMKNIETA
        # ZIELEŃ URZĄDZONA: bryła zamknięta + zieleń w kołnierzu WRÓCIŁA
        # (patrz pułapka 2) + grunt już opadł.
        if st == ZAMKNIETA and np.isfinite(cg) and np.isfinite(collar_min) \
                and cg >= C.TH_COLLAR_GREEN \
                and cg - collar_min >= C.TH_COLLAR_RECOVERY \
                and np.isfinite(bare) and bare <= C.TH_BARE_SETTLED:
            st = ZIELEN_U
        raw.append(st)

    # zapadka
    cur = PRZED
    for st in raw:
        cur = max(cur, st)
        stages.append(cur)
    return stages


def first_reached(stages: list, epoch_labels: list) -> dict:
    """Etykieta epoki, w której etap osiągnięto po raz pierwszy."""
    out = {}
    for st, lab in zip(stages, epoch_labels):
        for s in range(PRZED, st + 1):
            out.setdefault(s, lab)
    return out


def summarize(site: dict, epoch_labels: list, series: list, stages: list) -> dict:
    """Jeden wiersz raportu na obszar."""
    fr = first_reached(stages, epoch_labels)
    last = series[-1]
    tgt = effective_target(site)
    th_s, th_m = built_thresholds(site)
    return {
        "id": site["id"],
        "name": site["name"],
        "target_built_frac": tgt,
        # Ile z docelowej powierzchni hal już stoi — liczba, która mówi
        # o postępie więcej niż sam udział zabudowy.
        "progress": float(last["built"] / tgt) if tgt > 0 else float("nan"),
        "th_structures": th_s,
        "th_mature": th_m,
        "stage": stages[-1],
        "stage_name": STAGE_NAMES[stages[-1]],
        "epoch_last": epoch_labels[-1],
        "built_frac": last["built"],
        "bare_frac": last["bare"],
        "veg_frac": last["veg"],
        "collar_green": last["collar_green"],
        "since": fr.get(stages[-1]),
        "t_earthworks": fr.get(ZIEMNE),
        "t_structures": fr.get(ROSNIE),
        "t_mature": fr.get(ZAMKNIETA),
        "t_green": fr.get(ZIELEN_U),
        "approx": site.get("approx", False),
    }
