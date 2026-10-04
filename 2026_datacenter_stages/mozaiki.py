# -*- coding: utf-8 -*-
"""Zrzuca wszystkie mozaiki map do PNG — bez notatnika.

    python mozaiki.py            # wszystkie obszary
    python mozaiki.py <id> ...   # wybrane

Po co osobny skrypt: notatnik bywa niewygodny (trzeba go wykonać, otworzyć
w Jupyterze), a mozaiki to jest to, co się ogląda najczęściej. Tu powstają jako
zwykłe pliki PNG, które otwiera się dwuklikiem.

Czyta wyłącznie to, co już policzył run.py (out/maps/*.npz, out/cache/*.nc),
więc nic nie pobiera i nie liczy modelu od nowa.
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")           # zapis do plików, bez ekranu
import matplotlib.pyplot as plt

import config as C
import viz

OUT = os.path.join(C.OUT_DIR, "mozaiki")


def _save(fig, path: str):
    fig.savefig(path, bbox_inches="tight", dpi=110)
    plt.close(fig)
    print(f"   {path}")


def main(argv: list) -> int:
    want = [a for a in argv if not a.startswith("-")]
    sites = [s for s in C.SITES if not want or s["id"] in want]
    os.makedirs(OUT, exist_ok=True)

    ready = []
    for s in sites:
        try:
            m = viz.load_maps(s["id"])
        except Exception as e:                          # noqa: BLE001
            print(f"   {s['id']}: pomijam ({type(e).__name__})")
            continue
        ready.append((s, m))
    if not ready:
        print("brak policzonych map — uruchom najpierw: python run.py")
        return 1

    eps = ready[0][1]["epochs"]

    # 1. Przegląd wszystkich obszarów: pierwsza i ostatnia epoka.
    try:
        _save(viz.overview([s for s, _ in ready], eps[0], eps[-1], ncols=4),
              os.path.join(OUT, "00_przeglad_przed_i_teraz.png"))
    except Exception as e:                              # noqa: BLE001
        print(f"   przegląd pominięty: {type(e).__name__}: {e}")

    # 2. Na obszar: barwy naturalne, SWIR, klasyfikacja, wzrost zabudowy.
    for s, m in ready:
        sid = s["id"]
        tag = "KONTROLNY_" if s.get("control") else ""
        for kind, nazwa in (("rgb", "1_barwy_naturalne"),
                            ("swir", "2_swir"),
                            ("cls", "3_klasyfikacja")):
            try:
                fig = viz.strip(s, m["epochs"], kind=kind, ncols=8,
                                title=f"{sid} — {s.get('place', '')}")
                _save(fig, os.path.join(OUT, f"{tag}{sid}_{nazwa}.png"))
            except Exception as e:                      # noqa: BLE001
                print(f"   {sid} {kind}: {type(e).__name__}: {e}")
        try:
            _save(viz.built_growth(s, m),
                  os.path.join(OUT, f"{tag}{sid}_4_wzrost_zabudowy.png"))
        except Exception as e:                          # noqa: BLE001
            print(f"   {sid} wzrost: {type(e).__name__}: {e}")
        try:
            _save(viz.collar_view(s, m),
                  os.path.join(OUT, f"{tag}{sid}_5_kolnierz_zieleni.png"))
        except Exception as e:                          # noqa: BLE001
            print(f"   {sid} kołnierz: {type(e).__name__}: {e}")

    print(f"\ngotowe: {len(os.listdir(OUT))} plików w {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
