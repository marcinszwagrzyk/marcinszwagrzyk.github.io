# -*- coding: utf-8 -*-
"""Dobór progów potwierdzania zabudowy — z pomiaru, nie z gustu.

    python calibrate.py

MIN_P_ROOF i MIN_ROOF_PIXELS wpisałem początkowo „na oko" (0,60 i 25 pikseli).
Kontrola względem obrysów OSM pokazała, że na części obszarów połowa
„zabudowy potwierdzonej" nie leży na żadnym budynku:

    Los Lunas      celność  96%
    Taylor County  celność  57%
    Loudoun        celność  45%
    Papillion      celność  40%

Nie zależy to od definicji odniesienia (próg 2000 m2, wszystkie budynki, rdzeń
kampusu — wyniki te same co do punktu procentowego), więc nie jest artefaktem
pomiaru, tylko realnym naddetekcją.

Ten skrypt nie zgaduje poprawki. Przechodzi siatkę progów, liczy dla każdego
CELNOŚĆ i POKRYCIE względem obrysów OSM i pokazuje, czym się płaci za co.
Działa na zapisanych mapach p(DACH) z out/maps/*.npz, więc nie pobiera niczego
i liczy się w minutę — można go puścić po każdej zmianie modelu.
"""
from __future__ import annotations

import sys

import numpy as np
from scipy import ndimage

import classify
import config as C
import labels as L
import viz

# Siatka progów do sprawdzenia.
P_GRID = [0.50, 0.60, 0.70, 0.80, 0.90]
PX_GRID = [25, 50, 100]


def _built(p_roofs: list, p_th: float, px_th: int, persist: int) -> list:
    """To samo co classify.built_series, ale z progami podanymi wprost."""
    raw = [classify._despeckle(p >= p_th, px_th) for p in p_roofs]
    out, ratchet = [], np.zeros_like(raw[0])
    for t in range(len(raw)):
        acc = raw[t].copy()
        ok = t + 1 >= persist
        if ok:
            for j in range(1, persist):
                acc &= raw[t - j]
        else:
            acc[:] = False
        ratchet = ratchet | acc
        out.append(ratchet.copy())
    return out


def main(argv: list) -> int:
    sites = [s for s in C.SITES]
    rows = []

    # Odniesienie: obrysy budynków OSM na siatce ostatniej epoki, w rdzeniu
    # kampusu. Liczymy raz na obszar, bo rasteryzacja jest najdroższa.
    ref_cache = {}
    for s in sites:
        try:
            m = viz.load_maps(s["id"])
        except FileNotFoundError:
            continue
        ds = viz.composite(s["id"], m["epochs"][-1])
        if ds is None:
            continue
        import osm
        try:
            bld = osm.buildings(s, __import__("mpc").aoi_bbox(s, 2.0), verbose=False)
        except Exception:                               # noqa: BLE001
            continue
        ref = L._rasterize(bld, ds, shrink_m=0.0, min_area_m2=0.0)
        core, _ = L.campus_core(s, ds, verbose=False)
        if core is None:
            core = np.ones(ref.shape, bool)
        if not (ref & core).any():
            continue
        ref_cache[s["id"]] = (m, ref & core, core,
                              ndimage.binary_dilation(ref, iterations=1) & core)
        print(f"   odniesienie: {s['id']}")

    if not ref_cache:
        print("brak danych — uruchom najpierw run.py")
        return 1

    print(f"\n{'p_th':>5s} {'px':>4s} {'trw':>4s} "
          f"{'celność':>8s} {'pokrycie':>9s} {'F1':>6s}   (średnia po obszarach)")
    print("-" * 60)
    best = None
    for persist in (2, 3):
        for p_th in P_GRID:
            for px_th in PX_GRID:
                cs, rs = [], []
                for sid, (m, ref, core, ref_t) in ref_cache.items():
                    b = _built([x.astype("float32") for x in m["p_roof"]],
                               p_th, px_th, persist)[-1] & core
                    nb = int(b.sum())
                    if nb == 0:
                        cs.append(0.0)
                        rs.append(0.0)
                        continue
                    cs.append((b & ref_t).sum() / nb)
                    rs.append((ref & ndimage.binary_dilation(b, iterations=1)
                               ).sum() / ref.sum())
                c, r = float(np.mean(cs)), float(np.mean(rs))
                f1 = 2 * c * r / (c + r) if (c + r) else 0.0
                print(f"{p_th:5.2f} {px_th:4d} {persist:4d} "
                      f"{c*100:7.0f}% {r*100:8.0f}% {f1:6.3f}")
                if best is None or f1 > best[0]:
                    best = (f1, p_th, px_th, persist, c, r)

    f1, p_th, px_th, persist, c, r = best
    print(f"\nNAJLEPSZE: MIN_P_ROOF={p_th}  MIN_ROOF_PIXELS={px_th}  "
          f"BUILT_PERSISTENCE_EPOCHS={persist}")
    print(f"           celność {c*100:.0f}%, pokrycie {r*100:.0f}%, F1 {f1:.3f}")
    print(f"obecnie w config.py: MIN_P_ROOF={C.MIN_P_ROOF}, "
          f"MIN_ROOF_PIXELS={C.MIN_ROOF_PIXELS}, "
          f"BUILT_PERSISTENCE_EPOCHS={C.BUILT_PERSISTENCE_EPOCHS}")
    print("\nUWAGA: F1 traktuje celność i pokrycie równo, a w tym zadaniu NIE są")
    print("równe — fałszywe ogłoszenie etapu jest gorsze niż spóźnienie o epokę.")
    print("Dlatego patrz też na kolumnę celności osobno i wybieraj próg, przy")
    print("którym celność jest wysoka, a pokrycie jeszcze nie zapada się do zera.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
