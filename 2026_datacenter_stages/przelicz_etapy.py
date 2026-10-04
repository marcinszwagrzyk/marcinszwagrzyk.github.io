# -*- coding: utf-8 -*-
"""Przelicz SAME ETAPY z zapisanych map, bez ponownej klasyfikacji.

    python przelicz_etapy.py

Po co: progi etapów (`TH_BUILT_*`, `DETECTOR_RECALL`, progi gruntu i kołnierza)
zmieniają się częściej niż model. Pełny bieg to godzina, a przeliczenie etapów
z `out/maps/*.npz` — kilkadziesiąt sekund, bo mapy klas i zabudowy już są.

Służy też do czegoś ważniejszego: po zmianie progu w trakcie biegu część
obszarów bywa policzona starym progiem, a część nowym. Taka tabela wygląda
poprawnie i jest wewnętrznie niespójna. Ten skrypt przelicza WSZYSTKIE obszary
jednym kompletem progów, więc przywraca porównywalność.

UWAGA: nie rusza `built` ani `cls` — te zależą od modelu i od progów
potwierdzania zabudowy (MIN_P_ROOF, MIN_ROOF_PIXELS, BUILT_PERSISTENCE_EPOCHS).
Zmiana tamtych wymaga pełnego biegu.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

import config as C
import labels as L
import stages as S
import viz


def main(argv: list) -> int:
    done, skipped = 0, []
    for site in C.SITES:
        sid = site["id"]
        try:
            m = viz.load_maps(sid)
        except FileNotFoundError:
            skipped.append((sid, "brak map"))
            continue

        ds = viz.composite(sid, m["epochs"][-1])
        if ds is None:
            skipped.append((sid, "brak kompozytu"))
            continue

        core, hall_m2 = L.campus_core(site, ds, verbose=False)
        if core is None:
            core = np.ones(m["cls"].shape[1:], bool)
            site_eff = dict(site)
        else:
            px = C.RESOLUTION_M ** 2
            site_eff = dict(site,
                            target_built_frac=hall_m2 / max(1.0, core.sum() * px))

        cls_maps = [m["cls"][i] for i in range(m["cls"].shape[0])]
        built = [m["built"][i] for i in range(m["built"].shape[0])]
        series = S.metrics(cls_maps, built, core)
        st = S.classify_stages(series, site_eff)
        summ = S.summarize(site_eff, m["epochs"], series, st)

        srs = [dict(id=sid, epoch=lab, stage=int(x),
                    stage_name=S.STAGE_NAMES[x], **g)
               for lab, g, x in zip(m["epochs"], series, st)]
        d = os.path.join(C.OUT_DIR, "rows")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{sid}.json"), "w", encoding="utf-8") as f:
            json.dump({"summary": summ, "series": srs}, f,
                      ensure_ascii=False, default=float)

        # Etapy trzymane w npz tez odswiezamy - z nich bierze podpisy mozaika
        # klasyfikacji. Inaczej mapa mowilaby co innego niz tabela.
        np.savez_compressed(
            os.path.join(C.OUT_DIR, "maps", f"{sid}.npz"),
            cls=m["cls"], built=m["built"], p_roof=m["p_roof"],
            epochs=np.array(m["epochs"]), stages=np.array(st, "uint8"))

        p = summ.get("progress", float("nan"))
        print(f"   {sid:32s} {S.STAGE_SHORT[st[-1]]:12s} "
              f"zabudowa {summ['built_frac']*100:5.1f}%  "
              f"cel_ef {summ['target_built_frac']*100:5.2f}%  "
              f"postep {p*100:4.0f}%")
        done += 1

    print(f"\nprzeliczono {done} obszarow"
          + (f", pominieto {len(skipped)}: {skipped}" if skipped else ""))
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
