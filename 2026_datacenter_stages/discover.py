# -*- coding: utf-8 -*-
"""Skąd się bierze lista dziesięciu obszarów — z pomiaru, nie z pamięci.

    python discover.py            # pobierz, policz, zapisz sites.json
    python discover.py --show     # tylko pokaż, co jest w sites.json

================================= PO CO TO JEST ================================
Pierwsza wersja listy obszarów pochodziła z mojej pamięci i była BŁĘDNA w sposób,
który psuł cały wynik. Dla Ashburn miałem 39.0437,-77.4875. Sprawdzenie obrysami
budynków pokazało, że w kwadracie o półboku 1,5 km wokół tego punktu jest
0,0% hal — zabudowa zajmuje tam 9,8% powierzchni, ale to domy jednorodzinne.
Punkt leżał w mieszkaniowej części Ashburn, kilka kilometrów od Data Center Alley.
Potok policzył wtedy „PRZED BUDOWĄ, zabudowa 1,6%" dla najgęstszego skupiska data
center na świecie — i był to wynik poprawny dla ZŁEGO KADRU.

Dlatego współrzędne bierzemy z OpenStreetMap, gdzie data center są otagowane:
    telecom=data_center, building=data_center
W CONUS daje to 1730 hal (0,67 MB zapytania o same środki, 17 s; z geometrią
2,26 MB, 96 s) z operatorami: AWS 253, Digital Realty 75, Google 71,
Microsoft 68, Meta 59, QTS 52, Equinix 51...

=========================== CO ZNACZY „NAJWIĘKSZE" =============================
To jest ranking po POWIERZCHNI HAL ZMAPOWANEJ W OSM — nie po nakładach.
Rankingu po nakładach nie mam skąd wziąć w sposób weryfikowalny, a wymyślanie
kwot byłoby zmyślaniem. Powierzchnia hal jest za to mierzalna, sprawdzalna
i skorelowana z wielkością inwestycji.
Ograniczenia, o których trzeba wiedzieć:
  * kompletność OSM jest nierówna — kampus niezmapowany nie istnieje w rankingu;
  * OSM pokazuje STAN DZISIEJSZY, w tym hale otagowane building=construction,
    więc dla kampusu w budowie powierzchnia jest bliska docelowej (to zaleta:
    daje nam cel, do którego porównujemy udział zabudowy);
  * jeden kampus to jedno skupisko hal, nie jedna działka ewidencyjna.
================================================================================
"""
from __future__ import annotations

import json
import os
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import Polygon
from sklearn.cluster import DBSCAN

import config as C

OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "geo-toolbox-datacenter-stages/1.0 (+github.com/geo-toolbox)"}
CONUS = "24.4,-125.0,49.6,-66.9"

# Promień skupiania hal w jeden kampus. 900 m: hale jednego kampusu stoją
# bliżej siebie, osobne kampusy zwykle dalej. Przy 2000 m całe Data Center
# Alley zlewa się w jedną plamę o rozpiętości 7,6 km i 173 halach z różnych
# dekad — a wtedy „etap budowy" takiego obszaru nic nie znaczy.
CLUSTER_EPS_M = 900

# Minimalna odległość między WYBRANYMI obszarami. Bez tego dziesiątka to byłoby
# dziesięć wycinków tego samego skupiska w Wirginii.
MIN_SEPARATION_M = 15_000

EQUAL_AREA = 5070        # EPSG:5070 — konforemnie równopowierzchniowa dla USA
SITES_JSON = "sites.json"


def fetch(verbose: bool = True) -> gpd.GeoDataFrame:
    """Wszystkie otagowane data center w CONUS, z geometrią."""
    q = (f'[out:json][timeout:300];('
         f'way["telecom"="data_center"]({CONUS});'
         f'way["building"="data_center"]({CONUS});'
         f');out geom;')
    t = time.time()
    r = None
    for att in range(6):
        r = requests.post(OVERPASS, data={"data": q}, headers=HEADERS, timeout=600)
        if r.status_code == 200:
            break
        if verbose:
            print(f"   Overpass {r.status_code} (zajęty), ponawiam...")
        time.sleep(8 * (att + 1))
    if r is None or r.status_code != 200:
        raise RuntimeError(f"Overpass nie oddał danych (ostatnio {r.status_code})")
    if verbose:
        print(f"   pobrano {len(r.content)/1e6:.2f} MB w {time.time()-t:.0f}s")

    rows = []
    for e in r.json()["elements"]:
        g = e.get("geometry") or []
        pts = [(p["lon"], p["lat"]) for p in g if p.get("lon") is not None]
        if len(pts) < 4:
            continue
        try:
            poly = Polygon(pts)
        except Exception:                               # noqa: BLE001
            continue
        if not poly.is_valid or poly.is_empty:
            continue
        t_ = e.get("tags", {})
        rows.append(dict(geometry=poly, name=t_.get("name", ""),
                         operator=t_.get("operator", ""),
                         # KLUCZOWE ROZRÓŻNIENIE — patrz komentarz w campuses().
                         is_building=int(bool(t_.get("building"))),
                         under_constr=int(t_.get("building") == "construction")))
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    if verbose:
        print(f"   hal z poprawną geometrią: {len(gdf)}")
    return gdf


def campuses(gdf: gpd.GeoDataFrame, verbose: bool = True) -> pd.DataFrame:
    """Skup hale w kampusy i policz ich powierzchnię oraz rozpiętość."""
    m = gdf.to_crs(EQUAL_AREA)
    gdf = gdf.copy()
    gdf["area_m2"] = m.area.values
    cen = m.geometry.centroid
    gdf["x"], gdf["y"] = cen.x.values, cen.y.values

    gdf["campus"] = DBSCAN(eps=CLUSTER_EPS_M, min_samples=1) \
        .fit_predict(np.c_[gdf.x, gdf.y])

    # ====================== OBRYS DACHU vs OBRYS DZIAŁKI ======================
    # `telecom=data_center` bywa w OSM przypięty do GRANICY TERENU, nie do hali.
    # Zmierzone na kampusie Google w Berkeley County (10 obiektów):
    #     77,2 ha  landuse=industrial, BEZ tagu building, "Google ... Data Center"
    #      6,5 ha  building=industrial
    #      2,3 ha  building=industrial
    #      ... (jeszcze 7 hal)
    #     SUMA 96,9 ha, ale z tagiem `building` tylko 19,7 ha
    # Liczenie tej 77-hektarowej działki jako "powierzchni hal" zawyżało cel
    # pięciokrotnie (27% zamiast 5,5% kadru) i sprawiało, że próg "bryła
    # zamknięta" był NIEOSIĄGALNY — w pierwszym biegu żaden z dziesięciu
    # kampusów nie doszedł dalej niż "zabudowa rośnie".
    # Dlatego: wszystkie obiekty SŁUŻĄ DO ZLOKALIZOWANIA kampusu, ale
    # POWIERZCHNIĘ HAL liczymy wyłącznie z obiektów mających tag `building`.
    gdf["bld_area"] = gdf.area_m2 * gdf.is_building

    agg = gdf.groupby("campus").agg(
        objects=("area_m2", "size"),
        halls=("is_building", "sum"),
        hall_area_m2=("bld_area", "sum"),
        site_area_m2=("area_m2", "sum"),
        x=("x", "mean"), y=("y", "mean"),
        under_constr=("under_constr", "sum")).reset_index()

    # Kampus bez ani jednej zmapowanej hali to sama granica terenu — nie da się
    # na nim orzekać o etapie zabudowy, bo nie wiadomo, ile tej zabudowy ma być.
    before = len(agg)
    agg = agg[agg.hall_area_m2 > 0].copy()
    if verbose and before > len(agg):
        print(f"   odrzucono {before - len(agg)} kampusów bez zmapowanych hal "
              f"(sama granica terenu)")

    def who(c: int) -> str:
        d = gdf[gdf.campus == c]
        ops = [o for o in d.operator if o]
        if ops:
            return pd.Series(ops).value_counts().index[0]
        nms = [n for n in d.sort_values("area_m2", ascending=False).name if n]
        return nms[0] if nms else "(bez nazwy)"

    agg["who"] = agg.campus.map(who)

    # rozpiętość = większy bok otoczki kampusu; stąd bierzemy promień AOI
    # Rozpiętość liczymy z SAMYCH HAL — działka bywa wielokrotnie większa
    # i rozdmuchiwałaby AOI, rozcieńczając udziały klas.
    ext = []
    for c in agg.campus:
        sel = (gdf.campus.values == c) & (gdf.is_building.values == 1)
        b = m[sel].total_bounds
        ext.append(float(max(b[2] - b[0], b[3] - b[1])))
    agg["extent_m"] = ext

    ll = gpd.GeoDataFrame(geometry=gpd.points_from_xy(agg.x, agg.y),
                          crs=EQUAL_AREA).to_crs(4326)
    agg["lon"], agg["lat"] = ll.geometry.x.values, ll.geometry.y.values

    agg = agg.sort_values("hall_area_m2", ascending=False).reset_index(drop=True)
    if verbose:
        print(f"   kampusów: {len(agg)}")
    return agg


def select(agg: pd.DataFrame, n: int = 10, verbose: bool = True) -> list:
    """Wybierz n największych kampusów, zachowując odstęp MIN_SEPARATION_M."""
    chosen = []
    for _, r in agg.iterrows():
        if len(chosen) >= n:
            break
        if any(np.hypot(r.x - c.x, r.y - c.y) < MIN_SEPARATION_M for c in chosen):
            continue
        chosen.append(r)
    if verbose and len(chosen) < n:
        print(f"   UWAGA: wybrano tylko {len(chosen)} z {n} "
              f"(za mało kampusów spełniających odstęp)")
    return chosen


def to_sites(chosen: list) -> list:
    """Zamień kampusy na wpisy obszarów dla potoku."""
    out = []
    for r in chosen:
        # Promień AOI: połowa rozpiętości kampusu + 400 m marginesu na kołnierz
        # zieleni, drogi i zbiorniki. Ograniczony, bo bardzo duży kadr rozcieńcza
        # udziały klas i psuje progi etapów.
        radius = float(np.clip(r.extent_m / 2.0 + 400.0, 700.0, 2500.0))
        area_aoi = (2 * radius) ** 2
        slug = "".join(ch if ch.isalnum() else "_" for ch in r.who.lower())
        slug = "_".join(p for p in slug.split("_") if p)[:28]
        out.append(dict(
            id=f"{slug}_{abs(int(r.lat*100)):04d}",
            name=f"{r.who} — {int(r.halls)} hal, {r.hall_area_m2/1e4:.0f} ha",
            lat=round(float(r.lat), 5), lon=round(float(r.lon), 5),
            radius_m=round(radius),
            halls=int(r.halls),
            hall_area_m2=round(float(r.hall_area_m2)),
            under_constr=int(r.under_constr),
            extent_m=round(float(r.extent_m)),
            # UDZIAŁ DOCELOWY: ile powierzchni AOI zajmują hale według OSM.
            # To jest cel, do którego potok porównuje udział zabudowy
            # potwierdzonej — patrz stages.py. Dzięki temu nie trzeba jednego
            # progu dla kampusu gęstego i rozrzuconego.
            target_built_frac=round(float(r.hall_area_m2 / area_aoi), 4),
            approx=False,
            source_note=("środek i zasięg z OSM (telecom/building=data_center), "
                         f"skupienie {CLUSTER_EPS_M} m"),
        ))
    return out


def save(sites: list, path: str = SITES_JSON):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%d"),
                   "source": "OpenStreetMap / Overpass",
                   "ranking": "powierzchnia hal zmapowanych w OSM (NIE nakłady)",
                   "cluster_eps_m": CLUSTER_EPS_M,
                   "min_separation_m": MIN_SEPARATION_M,
                   "sites": sites}, f, ensure_ascii=False, indent=1)
    print(f"\nzapisano {path} ({len(sites)} obszarów)")


def show(sites: list):
    print(f"\n{'#':>2s} {'id':30s} {'hal':>4s} {'pow.[ha]':>9s} "
          f"{'cel':>6s} {'R[m]':>6s} {'w budowie':>9s}  współrzędne")
    print("-" * 104)
    for i, s in enumerate(sites, 1):
        if s.get("place"):
            print(f"   {s['place']}")
        print(f"{i:2d} {s['id']:30s} {s['halls']:4d} "
              f"{s['hall_area_m2']/1e4:9.1f} {s['target_built_frac']*100:5.1f}% "
              f"{s['radius_m']:6d} {s['under_constr']:9d}  "
              f"{s['lat']:.4f}, {s['lon']:.4f}")
    print("\n   'cel' = udział AOI zajęty przez hale wg OSM. Potok porównuje do")
    print("   niego udział zabudowy POTWIERDZONEJ z Sentinela (stages.py).")


def main(argv: list) -> int:
    if "--controls" in argv:
        k = [a for a in argv if a.isdigit()]
        return add_controls(int(k[0]) if k else 2)
    if "--places" in argv:
        return add_places()
    if "--show" in argv:
        if not os.path.exists(SITES_JSON):
            print(f"brak {SITES_JSON} — uruchom: python discover.py")
            return 1
        show(json.load(open(SITES_JSON, encoding="utf-8"))["sites"])
        return 0

    n = C.N_SITES
    print(f"Szukam {n} największych kampusów data center w USA (OSM)...")
    gdf = fetch()
    agg = campuses(gdf)
    sites = to_sites(select(agg, n))
    save(sites)
    show(sites)
    return 0




# ============================ NAZWY MIEJSC ============================
# Część kampusów nie ma w OSM ani `name`, ani `operator` — sprawdzone na
# skupisku 40 hal pod Abilene w Teksasie: wszystkie 40 obiektów bez nazwy
# i bez operatora (typowe dla inwestycji świeżo zmapowanej). Zostaje wtedy
# identyfikator w rodzaju „bez_nazwy_3250", po którym nie widać, gdzie to jest.
#
# Nazwę operatora w takim wypadku ZMYŚLIŁBYM — natomiast POŁOŻENIE jest
# wyprowadzalne ze współrzędnych, więc dokładamy je przez geokodowanie wsteczne
# (Nominatim). „rejon Abilene, Texas" to fakt wynikający z danych; „Stargate"
# byłby moim domysłem i go tu nie ma.
def add_places(path: str = SITES_JSON, verbose: bool = True) -> int:
    """Dopisz `place` do sites.json. NIE rusza id ani współrzędnych, więc można
    to uruchomić obok trwającego biegu — cache i mapy zostają ważne."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    for s in doc["sites"]:
        if s.get("place"):
            continue
        try:
            r = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": s["lat"], "lon": s["lon"], "format": "json",
                        "zoom": 10, "accept-language": "en"},
                headers=HEADERS, timeout=30)
            a = r.json().get("address", {}) if r.status_code == 200 else {}
            part = [a.get(k) for k in ("city", "town", "village", "county")
                    if a.get(k)]
            place = ", ".join(filter(None, [part[0] if part else None,
                                            a.get("state")])) or "?"
        except Exception:                               # noqa: BLE001
            place = "?"
        s["place"] = place
        if verbose:
            print(f"   {s['id']:34s} -> {place}")
        time.sleep(1.1)        # Nominatim: najwyżej 1 zapytanie na sekundę

    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    if verbose:
        print(f"\nuzupełniono {path}")
    return 0




# ============================ GRUPA KONTROLNA ============================
# Po co: potok ma orzekać o etapie budowy, więc najmocniejszym sprawdzianem
# jest kampus, o którym z góry wiadomo, JAKI etap powinien pokazać. Kampus
# skończony i działający musi wyjść jako zabudowa dojrzała PŁASKO OD PIERWSZEJ
# EPOKI — bez robót ziemnych w środku szeregu. Jeśli potok dorobi mu budowę
# w 2022 roku, to znaczy, że myli sezonową zmienność z budową i nie wolno mu
# wierzyć również tam, gdzie budowa naprawdę trwa.
#
# Wybór kontrolnych NIE pochodzi z mojej pamięci: bierzemy największe kampusy,
# w których OSM nie zna ANI JEDNEJ hali otagowanej `building=construction`.
# Czy rzeczywiście stały przed 2018, rozstrzygnie sam Sentinel — i o to chodzi.
def add_controls(n_ctrl: int = 2, path: str = SITES_JSON,
                 verbose: bool = True) -> int:
    """Dopisz kampusy kontrolne do sites.json, NIE ruszając dotychczasowych
    wpisów (ich id są kluczem cache kompozytów — zmiana = ponowne pobranie)."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    have = [s for s in doc["sites"] if not s.get("control")]
    if verbose:
        print(f"   obszarów głównych: {len(have)}")

    agg = campuses(fetch(verbose), verbose)
    # Kandydaci: bez hal w budowie, z dala od już wybranych i od siebie.
    # Położenie już wybranych liczymy PRZELICZENIEM WSPÓŁRZĘDNYCH, a nie
    # wyszukiwaniem po zaokrąglonym lat/lon w tabeli kampusów. Ta druga metoda
    # cicho nie znalazła dopasowania i wskazała jako "kontrolny" obszar, który
    # był już na liście głównej — błąd, którego nie widać w wyniku, dopóki się
    # nie porówna identyfikatorów.
    import numpy as _np
    _pts = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy([x["lon"] for x in have],
                                    [x["lat"] for x in have]),
        crs=4326).to_crs(EQUAL_AREA)
    chosen_xy = [(float(g.x), float(g.y)) for g in _pts.geometry]
    have_ids = {x["id"] for x in have}

    out = []
    for _, r in agg[agg.under_constr == 0].iterrows():
        if len(out) >= n_ctrl:
            break
        if any(_np.hypot(r.x - x, r.y - y) < MIN_SEPARATION_M
               for x, y in chosen_xy):
            continue
        if to_sites([r])[0]["id"] in have_ids:          # pas bezpieczeństwa
            continue
        out.append(r)
        chosen_xy.append((float(r.x), float(r.y)))

    new = to_sites(out)
    for s in new:
        s["control"] = True
        s["source_note"] += "; GRUPA KONTROLNA (0 hal w budowie wg OSM)"
    doc["sites"] = have + new
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    if verbose:
        for s in new:
            print(f"   kontrolny: {s['id']:30s} {s['halls']:3d} hal, "
                  f"{s['hall_area_m2']/1e4:.0f} ha, cel {s['target_built_frac']*100:.1f}%"
                  f"   {s['lat']:.4f}, {s['lon']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
