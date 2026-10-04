# -*- coding: utf-8 -*-
"""Analizator etapów budowy kampusów data center — przebieg całości.

    python run.py                 # wszystkie obszary z config.SITES
    python run.py ashburn_va      # wybrane obszary (po id)
    python run.py --no-osm        # bez obrysów OSM (szybciej, słabsze etykiety)

Kolejność: pola treningowe -> jeden model -> klasyfikacja wszystkich epok ->
ostrożne potwierdzanie zabudowy -> maszyna etapów -> raport.
Wszystko pobrane siedzi w out/cache i out/osm, więc drugie uruchomienie liczy
się w minutach.
"""
from __future__ import annotations

import os
import sys
import time

# KONSOLA. Windows domyslnie daje cp1250. Komunikat zawierajacy znak
# spoza tej strony kodowej rzucal UnicodeEncodeError, a ze byl w petli
# obszarow, ZABIJAL KAZDY OBSZAR PO KOLEI: bieg konczyl sie z 0
# policzonych obszarow, a komunikat wygladal na blad danych.
# Komunikat diagnostyczny nie ma prawa przerwac obliczen.
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import matplotlib
matplotlib.use("Agg")       # bieg wsadowy: rysujemy do plików, nie na ekran
import numpy as np
import pandas as pd

import classify
import config as C
import labels as L
import mpc
import stages as S


def gather_training(sites: list, verbose: bool = True):
    """Pula treningowa ze wszystkich obszarów (bez samych obszarów inwestycji)."""
    print("\n=== POLA TRENINGOWE " + "=" * 58)
    Xs, ys = [], []
    for site in sites:
        try:
            X, y = L.build(site, verbose=verbose)
        except Exception as e:                          # noqa: BLE001
            print(f"   {site['id']}: BŁĄD — {type(e).__name__}: {e}")
            continue
        if len(y):
            Xs.append(X)
            ys.append(y)
    if not Xs:
        raise RuntimeError("zero próbek treningowych — bez modelu nie ma analizy")
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    print(f"\n   razem {len(y)} próbek z {len(Xs)} obszarów")
    for cls in sorted(np.unique(y)):
        print(f"      {L.CLASS_NAMES[cls]:7s}: {int((y == cls).sum()):6d}")
    return X, y


def run_site(clf, site: dict, eps: list, verbose: bool = True, save: bool = True):
    """Przejdź obszar epoka po epoce. Zwraca (etykiety_epok, metryki, etapy).

    Mapy klas i zabudowy zapisujemy do out/maps/<id>.npz. Powód: notatnik ma
    RYSOWAĆ, a nie liczyć od nowa — predykcja 16 epok na obszar to minuty, a po
    zapisie wykresy robią się w sekundach i zawsze z tych samych liczb, które
    poszły do raportu.
    """
    cls_maps, p_roofs, used = [], [], []
    core = None
    for lab, d0, d1 in eps:
        # Każda epoka osobno: awaria jednej ma kosztować jedną epokę, a nie
        # cały obszar ani cały bieg. Przy 160 kompozytach na bieg to nie jest
        # ostrożność teoretyczna — w tym biegu padło „Could not resolve host"
        # i „Chunk and warp failed".
        try:
            ds = mpc.composite_cached(site, lab, d0, d1, verbose=False)
        except Exception as e:                          # noqa: BLE001
            if verbose:
                print(f"      {lab}: BŁĄD odczytu ({type(e).__name__}), pomijam")
            continue
        if ds is None:
            if verbose:
                print(f"      {lab}: brak danych, epoka pominięta")
            continue
        cls, p = classify.predict(clf, ds)
        if core is None:
            # RDZEŃ KAMPUSU, nie cały kwadrat. Kwadratowy kadr obejmuje też
            # magazyny i osiedla obok, więc „zabudowa potwierdzona" liczona
            # w nim rosła bez związku z inwestycją — postęp wychodził
            # 120-672%. Patrz labels.campus_core().
            core, hall_m2 = L.campus_core(site, ds, verbose=False)
            if core is None:
                core = np.ones(cls.shape, bool)
                if verbose:
                    print("      brak obrysów data center — rdzeniem jest "
                          "cały kadr (postęp będzie zaniżony względem celu)")
            else:
                px = C.RESOLUTION_M ** 2
                target = hall_m2 / max(1.0, core.sum() * px)
                site = dict(site, target_built_frac=target)
                if verbose:
                    print(f"      rdzeń kampusu: {core.sum()*px/1e6:.2f} km2, "
                          f"hale {hall_m2/1e4:.1f} ha, cel {target*100:.1f}%")
        cls_maps.append(cls)
        p_roofs.append(p)
        used.append(lab)

    if not cls_maps:
        return [], [], [], site

    built = classify.built_series(p_roofs)
    series = S.metrics(cls_maps, built, core)
    st = S.classify_stages(series, site)

    if save:
        d = os.path.join(C.OUT_DIR, "maps")
        os.makedirs(d, exist_ok=True)
        np.savez_compressed(
            os.path.join(d, f"{site['id']}.npz"),
            cls=np.stack(cls_maps),
            built=np.stack(built),
            p_roof=np.stack(p_roofs).astype("float16"),
            epochs=np.array(used),
            stages=np.array(st, "uint8"),
        )
    return used, series, st, site


ROWS_DIR = "rows"      # wyniki per obszar — dzięki nim bieg jest wznawialny


def _rows_path(sid: str) -> str:
    d = os.path.join(C.OUT_DIR, ROWS_DIR)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{sid}.json")


def assemble() -> int:
    """Złóż zapisane wyniki obszarów w tabelę, wykresy i raport.

    Dlaczego to jest osobny krok: bieg na dwunastu obszarach padał już trzy
    razy w połowie — na sieci, na pamięci i na moim własnym komunikacie
    z nieobsługiwanym znakiem — i za każdym razem tracone było wszystko.
    Teraz każdy obszar zapisuje swój wynik od razu, a ten krok tylko je skleja:
    można doliczyć pojedynczy obszar i złożyć raport bez powtarzania całości.
    """
    import glob
    import json as _json
    rows, long_rows = [], []
    for f in sorted(glob.glob(os.path.join(C.OUT_DIR, ROWS_DIR, "*.json"))):
        d = _json.load(open(f, encoding="utf-8"))
        rows.append(d["summary"])
        long_rows.extend(d["series"])
    if not rows:
        print("brak policzonych obszarów w out/rows — uruchom run.py")
        return 1

    df = pd.DataFrame(rows).sort_values("stage", ascending=False)
    dfl = pd.DataFrame(long_rows)
    df.to_csv(os.path.join(C.OUT_DIR, "etapy.csv"), index=False, encoding="utf-8")
    dfl.to_csv(os.path.join(C.OUT_DIR, "przebieg.csv"), index=False,
               encoding="utf-8")
    report(df, dfl)
    try:
        import plot
        plot.timeline(dfl, os.path.join(C.OUT_DIR, "etapy.png"))
        kr = os.path.join(C.OUT_DIR, "krzywe")
        os.makedirs(kr, exist_ok=True)
        for sid in dfl["id"].unique():
            plot.site_curves(dfl, sid, os.path.join(kr, f"{sid}.png"))
        print(f"\nwykres: {os.path.join(C.OUT_DIR, 'etapy.png')}   krzywe: {kr}")
    except Exception as e:                              # noqa: BLE001
        print(f"\n(wykresy pominięte: {type(e).__name__}: {e})")
    print(f"\nzłożono {len(rows)} obszarów")
    return 0


def main(argv: list):
    t_all = time.time()
    if "--assemble" in argv:
        return assemble()
    want = [a for a in argv if not a.startswith("--")]
    sites = [s for s in C.SITES if not want or s["id"] in want]
    if not sites:
        print(f"nie znam takich obszarów: {want}")
        print("dostępne:", ", ".join(s["id"] for s in C.SITES))
        return 2
    if "--no-osm" in argv:
        import osm
        osm.MIRRORS = []        # wymuś ścieżkę zapasową w labels.py

    os.makedirs(C.OUT_DIR, exist_ok=True)
    eps = mpc.epochs()
    print(f"obszary: {len(sites)}   epoki: {len(eps)} "
          f"({eps[0][0]}..{eps[-1][0]})")

    import joblib
    mpath = os.path.join(C.OUT_DIR, "model.joblib")
    if "--use-model" in argv:
        # Klasyfikacja pojedynczego obszaru w osobnym procesie: model wczytujemy
        # z dysku. Dzieki temu kazdy obszar liczy sie w stalej, malej pamieci,
        # a WSZYSTKIE obszary uzywaja TEGO SAMEGO modelu - inaczej udzialy
        # miedzy obszarami nie bylyby porownywalne.
        if not os.path.exists(mpath):
            print(f"brak {mpath} - najpierw: python run.py --train-only")
            return 2
        clf = joblib.load(mpath)["clf"]
        print(f"model wczytany z {mpath}")
    else:
        X, y = gather_training(sites)
        print("\n=== MODEL " + "=" * 68)
        clf, rep = classify.train(X, y)
        import features as FT
        joblib.dump({"clf": clf, "features": FT.FEATURES, "report": rep}, mpath)
        if "--train-only" in argv:
            print(f"\nmodel zapisany: {mpath}")
            return 0

    print("\n=== KLASYFIKACJA I ETAPY " + "=" * 53)
    rows, long_rows = [], []
    for site in sites:
        t0 = time.time()
        print(f"\n   {site['id']}  ({site['name']})")
        try:
            used, series, st, site = run_site(clf, site, eps)
        except Exception as e:                          # noqa: BLE001
            print(f"      BŁĄD obszaru — {type(e).__name__}: {e}")
            continue
        if not used:
            print("      brak jakichkolwiek danych — pomijam")
            continue
        for lab, m, s in zip(used, series, st):
            long_rows.append(dict(id=site["id"], epoch=lab, stage=s,
                                  stage_name=S.STAGE_NAMES[s], **m))
        summ = S.summarize(site, used, series, st)
        rows.append(summ)
        # Zapis NATYCHMIAST po obszarze — bieg ma być wznawialny. Trzy razy
        # padł w połowie (sieć, pamięć, mój własny komunikat z nieobsługiwanym
        # znakiem) i za każdym razem tracone było wszystko.
        import json as _json
        srs = [dict(id=site["id"], epoch=lab, stage=int(x),
                    stage_name=S.STAGE_NAMES[x], **m)
               for lab, m, x in zip(used, series, st)]
        with open(_rows_path(site["id"]), "w", encoding="utf-8") as fh:
            _json.dump({"summary": summ, "series": srs}, fh,
                       ensure_ascii=False, default=float)

        line = "".join(str(s) for s in st)
        print(f"      przebieg etapów: {line}   ({time.time()-t0:.0f}s)")
        print(f"      stan na {used[-1]}: {S.STAGE_NAMES[st[-1]]}"
              f"   zabudowa {series[-1]['built']*100:.1f}%"
              f"   grunt {series[-1]['bare']*100:.1f}%")

    if not rows:
        print("\nnic nie policzono")
        return 1

    df = pd.DataFrame(rows).sort_values("stage", ascending=False)
    dfl = pd.DataFrame(long_rows)
    df.to_csv(os.path.join(C.OUT_DIR, "etapy.csv"), index=False, encoding="utf-8")
    dfl.to_csv(os.path.join(C.OUT_DIR, "przebieg.csv"), index=False, encoding="utf-8")

    report(df, dfl)
    try:
        import plot
        plot.timeline(dfl, os.path.join(C.OUT_DIR, "etapy.png"))
        print(f"\nwykres: {os.path.join(C.OUT_DIR, 'etapy.png')}")
        # Krzywe per obszar — po nich widać, CZY etap wynika z danych, czy
        # z progu. Bez tego raport trzeba brać na wiarę.
        kr = os.path.join(C.OUT_DIR, "krzywe")
        os.makedirs(kr, exist_ok=True)
        for sid in dfl["id"].unique():
            plot.site_curves(dfl, sid, os.path.join(kr, f"{sid}.png"))
        print(f"krzywe per obszar: {kr}")
    except Exception as e:                              # noqa: BLE001
        print(f"\n(wykres pominięty: {type(e).__name__}: {e})")

    print(f"\nłącznie {time.time()-t_all:.0f}s")
    return 0


def report(df: pd.DataFrame, dfl: pd.DataFrame):
    print("\n=== NA JAKIM ETAPIE JEST KTÓRA INWESTYCJA " + "=" * 36)
    print(f"\n{'obszar':20s} {'etap':18s} {'od':8s} {'zabud.':>7s} "
          f"{'grunt':>7s} {'zieleń':>7s}  {'kołnierz':>8s}")
    print("-" * 86)
    for _, r in df.iterrows():
        cg = r["collar_green"]
        print(f"{r['id']:20s} {S.STAGE_SHORT[r['stage']]:18s} "
              f"{str(r['since'] or '-'):8s} {r['built_frac']*100:6.1f}% "
              f"{r['bare_frac']*100:6.1f}% {r['veg_frac']*100:6.1f}% "
              f"{(f'{cg*100:.0f}%' if np.isfinite(cg) else '  -'):>8s}")

    print("\n   daty wejścia w kolejne etapy:")
    print(f"   {'obszar':20s} {'ziemne':>9s} {'rośnie':>9s} "
          f"{'zamknięta':>10s} {'zieleń':>9s}")
    for _, r in df.iterrows():
        print(f"   {r['id']:20s} {str(r['t_earthworks'] or '-'):>9s} "
              f"{str(r['t_structures'] or '-'):>9s} "
              f"{str(r['t_mature'] or '-'):>10s} {str(r['t_green'] or '-'):>9s}")

    print("\n   JAK TO CZYTAĆ:")
    print("   * Etap to stan NA KOŃCU szeregu; kolumna 'od' mówi, kiedy ten")
    print("     etap osiągnięto po raz pierwszy.")
    print("   * 'zabud.' to udział zabudowy POTWIERDZONEJ — po filtrze pewności,")
    print("     spójności przestrzennej i trwałości w czasie. Jest z zasady")
    print("     mniejszy niż to, co widać na obrazie w jednej epoce.")
    print("   * 'postęp' = zabudowa potwierdzona / cel, gdzie cel to powierzchnia")
    print("     hal z OSM odniesiona do kadru. Mówi więcej niż sam udział")
    print("     zabudowy, bo uwzględnia, jak gęsty jest dany kampus.")
    print("   * Obszary i ich środki pochodzą z OSM (discover.py), nie z ręki.")
    print("     Ranking jest po POWIERZCHNI HAL ZMAPOWANYCH W OSM — nie po")
    print("     nakładach; takiego rankingu nie da się tu zweryfikować.")
    print("   * Kampus niezmapowany w OSM nie istnieje w tym zestawieniu, a cel")
    print("     zaniżony przez braki w OSM przyspiesza 'bryłę zamkniętą'.")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
