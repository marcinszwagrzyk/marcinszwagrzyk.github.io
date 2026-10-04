# -*- coding: utf-8 -*-
"""Obrysy z OpenStreetMap jako pola treningowe — przez Overpass, bez osmnx.

DLACZEGO NIE microsoft/ms-buildings z Planetary Computer:
sprawdziłem tę kolekcję. Zasób to jeden GeoParquet na cały kraj:
    129 554 779 wierszy, jedna kolumna `geometry`, partycja "RegionName=United States",
    `msft:partition_info` = None
Nie ma kolumny quadkey ani bbox, więc nie da się przeczytać samego obszaru 6×6 km —
trzeba by pobrać cały zbiór dla USA. Dlatego obrysy budynków bierzemy z OSM (do
którego import MS Buildings trafił zresztą w dużej części).

DLACZEGO OSOBNO BUDYNKI I OSOBNO DROGI/PARKINGI — to jest sedno „ostrożnego
klasyfikowania zabudowy":
droga dojazdowa i plac manewrowy powstają na ETAPIE ROBÓT ZIEMNYCH, rok lub dwa
przed halą. ESA WorldCover wrzuca jedno i drugie do klasy 50 „built-up". Gdyby
klasyfikator uczył się „zabudowy" z klasy 50, to asfalt placu budowy uznałby za
halę i potok ogłosiłby „stoją budynki" o rok za wcześnie — czyli pomylił etap,
co jest dokładnie tym, czego mamy nie robić.
Rozdziela je JASNOŚĆ: dach hali (membrana TPO, blacha, jasny beton) jest jasny
w widzialnym i w SWIR; asfalt jest ciemny w obu. Dlatego uczymy klasyfikator
dwóch osobnych klas i dajemy mu prawdziwe przykłady jednej i drugiej.

JAK SIĘ ZACHOWUJE OVERPASS (zmierzone, nie założone):
    okno 1×1 km  -> HTTP 200,  0,37 MB,  1,5 s,    359 budynków
    kafel 3×3 km -> HTTP 504 po 8 s
    kafel 6×6 km -> HTTP 200, 13,43 MB,  2,6 s, 11 424 budynków
Czyli 504 NIE BIERZE SIĘ Z ROZMIARU ZAPYTANIA — mniejszy kafel dostał błąd,
większy przeszedł w 2,6 s. To chwilowe przeciążenie serwera. Wniosek dla kodu:
nie ma sensu drobić zapytań (więcej żądań = więcej okazji na 504), ma sens
PONAWIAĆ u tego hosta, który odpowiada. Dlatego kafle są duże (6 km), a 504
powoduje ponowienie z odczekaniem, nie przeskok na inne lustro.
Dwa zapasowe lustra są z tej maszyny nieosiągalne (ReadTimeout), więc raz
stwierdzona niedostępność jest pamiętana do końca uruchomienia — inaczej każdy
kafel płaciłby 50 s za pukanie do martwych adresów.
"""
from __future__ import annotations

import os
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Polygon

import config as C

# Kolejność ma znaczenie: z tej maszyny odpowiada tylko pierwszy adres, dwa
# pozostałe dają ReadTimeout (sprawdzone na zapytaniu, które overpass-api.de
# obsłużył w 1,5 s). Zostają jako zapas, ale z krótkim limitem czasu, żeby
# martwe lustro nie blokowało potoku na minuty.
MIRRORS = [
    ("https://overpass-api.de/api/interpreter", 90),
    ("https://overpass.kumi.systems/api/interpreter", 25),
    ("https://overpass.private.coffee/api/interpreter", 25),
]
# Overpass odrzuca domyślny User-Agent biblioteki `requests` kodem 406.
HEADERS = {"User-Agent": "geo-toolbox-datacenter-stages/1.0 (+github.com/geo-toolbox)"}

TILE_KM = 6.0        # bok kafla zapytania — patrz pomiary w nagłówku
PAUSE_S = 1.5        # przerwa między kaflami — nie zarzynamy usługi publicznej
# Ponowienia na 504/429 u tego samego hosta. Dlaczego AŻ TYLE: mały obszar to
# JEDEN kafel, więc jedna seria 504 zabiera cały obszar — a bez obrysów dach
# i asfalt rozdziela tylko próg jasności, czyli to, co najsłabsze w całym
# potoku. Zdarzyło się w biegu: "wszystkie 1 kafli nieudane". Przy 7 próbach
# czekamy w najgorszym razie ~3 min na kafel i to jest dobrze wydany czas.
RETRIES = 7
BACKOFF_S = 6.0      # odczekanie przed ponowieniem (rośnie liniowo)
SECOND_PASS_WAIT_S = 45.0   # pauza przed powtórką nieudanych kafli

_dead: set = set()   # lustra, które okazały się nieosiągalne w tym uruchomieniu


class OsmUnavailable(RuntimeError):
    """Overpass nie odpowiedział. Potok ma działać dalej bez OSM (patrz labels.py)."""


def _post(query: str, verbose: bool = False) -> dict | None:
    """Jedno zapytanie. 504/429 = serwer zajęty -> ponawiamy TUTAJ, z odczekaniem.
    Timeout/odmowa połączenia = lustro martwe -> zapamiętujemy i nie wracamy."""
    for url, tmo in MIRRORS:
        if url in _dead:
            continue
        for attempt in range(RETRIES):
            try:
                r = requests.post(url, data={"data": query},
                                  headers=HEADERS, timeout=tmo)
            except Exception as e:                      # noqa: BLE001
                _dead.add(url)
                if verbose:
                    print(f"      OSM {url.split('/')[2]} nieosiągalne "
                          f"({type(e).__name__}) — pomijam do końca biegu")
                break
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 504, 503):
                wait = BACKOFF_S * (attempt + 1)
                if verbose:
                    print(f"      OSM {r.status_code} (serwer zajęty), "
                          f"ponawiam za {wait:.0f}s")
                time.sleep(wait)
                continue
            break        # inny błąd: zapytanie jest złe, ponawianie nie pomoże
    return None


def _tiles(bbox, km: float = TILE_KM):
    """Podziel bbox na kafle o boku ~km stopniowo w stopniach."""
    w, s, e, n = bbox
    import numpy as np
    dlat = km / 111.32
    dlon = km / (111.32 * np.cos(np.radians((s + n) / 2)))
    ys = np.arange(s, n, dlat)
    xs = np.arange(w, e, dlon)
    for y0 in ys:
        for x0 in xs:
            yield (x0, y0, min(x0 + dlon, e), min(y0 + dlat, n))


def _bb(bbox) -> str:
    """Overpass chce kolejności (południe,zachód,północ,wschód)."""
    w, s, e, n = bbox
    return f"{s:.6f},{w:.6f},{n:.6f},{e:.6f}"


def _fetch_tiled(bbox, body_tpl: str, verbose: bool) -> list:
    """Zbierz elementy z wszystkich kafli. Pojedynczy nieudany kafel tylko
    zawęża pole treningowe; dopiero gdy padną wszystkie, zgłaszamy brak OSM."""
    tl = list(_tiles(bbox))
    out = []
    t0 = time.time()

    def pass_over(tiles: list) -> list:
        """Zwróć kafle, które się nie udały; udane dopisz do `out`."""
        miss = []
        for k, tb in enumerate(tiles):
            q = f"[out:json][timeout:90];({body_tpl.format(bb=_bb(tb))});out geom;"
            js = _post(q, verbose)
            if js is None:
                miss.append(tb)
            else:
                out.extend(js.get("elements", []))
            if k + 1 < len(tiles):
                time.sleep(PAUSE_S)
        return miss

    failed = pass_over(tl)
    # Druga tura po dłuższej pauzie. Przeciążenie Overpassa jest chwilowe,
    # a utrata obrysów kosztuje nas jakość rozdzielenia dachu od asfaltu.
    if failed:
        if verbose:
            print(f"      OSM: {len(failed)}/{len(tl)} kafli nieudanych, "
                  f"druga tura za {SECOND_PASS_WAIT_S:.0f}s")
        time.sleep(SECOND_PASS_WAIT_S)
        failed = pass_over(failed)

    if verbose:
        print(f"      OSM: {len(tl)} kafli, {len(failed)} nieudanych, "
              f"{len(out)} obiektów, {time.time()-t0:.0f}s")
    if len(failed) == len(tl):
        raise OsmUnavailable(f"wszystkie {len(tl)} kafli nieudane")
    return out


def _to_gdf(elements: list, as_lines: bool = False) -> gpd.GeoDataFrame:
    geoms = []
    for el in elements:
        g = el.get("geometry")
        if not g or len(g) < 2:
            continue
        pts = [(p["lon"], p["lat"]) for p in g if p.get("lon") is not None]
        if len(pts) < 2:
            continue
        try:
            if as_lines:
                geoms.append(LineString(pts))
            elif len(pts) >= 4:
                geoms.append(Polygon(pts))
        except Exception:                               # noqa: BLE001
            continue
    gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:4326")
    if len(gdf):
        gdf = gdf[gdf.is_valid & ~gdf.is_empty].reset_index(drop=True)
    return gdf


def _cache(name: str) -> str:
    os.makedirs(C.OSM_DIR, exist_ok=True)
    return os.path.join(C.OSM_DIR, name)


def _load_cached(path: str, verbose: bool):
    """Zwraca zapisany wynik albo None. Plik znacznikowy `.empty` oznacza
    „pytaliśmy, OSM nic tu nie ma" — to inna sytuacja niż „nie pytaliśmy"
    i nie wolno jej mylić z błędem."""
    if os.path.exists(path):
        if verbose:
            print(f"      z cache: {os.path.basename(path)}")
        return gpd.read_file(path)
    if os.path.exists(path + ".empty"):
        if verbose:
            print(f"      z cache: {os.path.basename(path)} (pusty)")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    return None


def _save(gdf: gpd.GeoDataFrame, path: str) -> gpd.GeoDataFrame:
    if len(gdf):
        gdf.to_file(path, driver="GPKG")
    else:
        open(path + ".empty", "w").close()
    return gdf


def buildings(site: dict, bbox, verbose: bool = True) -> gpd.GeoDataFrame:
    """Obrysy budynków — pole treningowe JASNEGO DACHU."""
    path = _cache(f"{site['id']}_buildings.gpkg")
    got = _load_cached(path, verbose)
    if got is not None:
        return got
    els = _fetch_tiled(bbox, 'way["building"]({bb});relation["building"]({bb});',
                       verbose)
    return _save(_to_gdf(els), path)


def pavement(site: dict, bbox, verbose: bool = True) -> gpd.GeoDataFrame:
    """Drogi i parkingi — pole treningowe CIEMNEJ NAWIERZCHNI.

    Drogi przychodzą jako linie, więc buforujemy je do pasa 6 m: chodzi o to,
    by trafić w środek jezdni, nie o odwzorowanie pasa drogowego.
    """
    path = _cache(f"{site['id']}_pavement.gpkg")
    got = _load_cached(path, verbose)
    if got is not None:
        return got

    tpl = ('way["highway"~"^(motorway|trunk|primary|secondary|tertiary|'
           'unclassified|residential|service)$"]({bb});'
           'way["amenity"="parking"]({bb});')
    els = _fetch_tiled(bbox, tpl, verbose)

    # Zamknięte obwody (parkingi) → wielokąty, otwarte (jezdnie) → linie z buforem.
    closed, open_ = [], []
    for e in els:
        g = e.get("geometry") or []
        (closed if len(g) >= 4 and g[0] == g[-1] else open_).append(e)

    parts = []
    poly = _to_gdf(closed)
    if len(poly):
        parts.append(poly.to_crs(3857))
    line = _to_gdf(open_, as_lines=True)
    if len(line):
        parts.append(gpd.GeoDataFrame(geometry=line.to_crs(3857).buffer(6.0),
                                      crs="EPSG:3857"))
    if not parts:
        gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    else:
        gdf = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True),
                               crs="EPSG:3857").to_crs("EPSG:4326")
    return _save(gdf, path)


def datacenters(site: dict, bbox, verbose: bool = True) -> gpd.GeoDataFrame:
    """Obrysy otagowane jako data center — do wyznaczenia RDZENIA KAMPUSU.

    To nie jest to samo co `buildings()`. Tamto daje wszystkie budynki w kadrze
    (również osiedle obok), a tu chodzi wyłącznie o to, gdzie jest sama
    inwestycja. Bierzemy też obiekty bez tagu `building` (granice terenu),
    bo one najlepiej wyznaczają zasięg kampusu.
    """
    path = _cache(f"{site['id']}_dc.gpkg")
    got = _load_cached(path, verbose)
    if got is not None:
        return got
    tpl = ('way["telecom"="data_center"]({bb});'
           'way["building"="data_center"]({bb});'
           'relation["telecom"="data_center"]({bb});')
    els = _fetch_tiled(bbox, tpl, verbose)
    gdf = _to_gdf(els)
    if len(gdf):
        # `is_building` rozstrzyga, co wchodzi do POWIERZCHNI HAL, a co służy
        # tylko do wyznaczenia zasięgu — patrz discover.py.
        gdf["is_building"] = [
            int(bool((e.get("tags") or {}).get("building")))
            for e in els if (e.get("geometry") and len(e["geometry"]) >= 4)
        ][:len(gdf)]
    return _save(gdf, path)
