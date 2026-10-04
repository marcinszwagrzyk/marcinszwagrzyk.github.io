# -*- coding: utf-8 -*-
"""Pola treningowe z danych publicznych.

ŹRÓDŁA (wszystkie publiczne, bez logowania):
  * ESA WorldCover 10 m (2021) z Planetary Computer — klasy pokrycia terenu.
    Zmierzone nad Ashburn w kadrze 12×12 km: drzewa 46,5%, zabudowa 19,0%,
    trawa 17,8%, woda 3,0%, uprawy 1,6%, goły grunt 1,5%.
  * OpenStreetMap przez Overpass — obrysy budynków i nawierzchni (patrz osm.py).

PIĘĆ KLAS, I DLACZEGO AKURAT TE:
  0 ZIELEN  — stan „przed budową"; drzewa/krzewy/trawa/uprawy
  1 GRUNT   — goła ziemia: wykop, nasyp, zdarty humus. ETAP ROBÓT ZIEMNYCH.
  2 DACH    — jasna połać dachu hali. ETAP ZABUDOWY.
  3 ASFALT  — ciemna nawierzchnia: droga, plac, parking.
  4 WODA    — zbiorniki, też retencyjne.

Rozdzielenie DACHU i ASFALTU jest celowe i jest tym, co czyni klasyfikację
zabudowy ostrożną. Oba są nieprzepuszczalne i oba siedzą w klasie 50 WorldCover,
ale pojawiają się na RÓŻNYCH etapach: plac i droga dojazdowa powstają razem
z wykopem, hala rok lub dwa później. Klasyfikator, który ich nie rozdziela,
ogłasza „stoją budynki" na widok asfaltowego placu budowy.

GDZIE POBIERAMY PRÓBKI: z kadru 2× szerszego niż obszar inwestycji, Z WYŁĄCZENIEM
samego obszaru. Inaczej model uczyłby się na stanie inwestycji z roku etykiet
(2021) i potem „rozpoznawał" dokładnie to, co już widział — zamiast uczyć się,
jak w tej okolicy wygląda zieleń, grunt, dach i asfalt.
"""
from __future__ import annotations

import numpy as np
import xarray as xr
from odc.geo.geobox import GeoBox
from odc.stac import stac_load
from rasterio.features import rasterize

import config as C
import features as F
import mpc
import osm

ZIELEN, GRUNT, DACH, ASFALT, WODA = 0, 1, 2, 3, 4
CLASS_NAMES = {ZIELEN: "ZIELEŃ", GRUNT: "GRUNT", DACH: "DACH",
               ASFALT: "ASFALT", WODA: "WODA"}
NOLABEL = 255

# WorldCover: 10 drzewa, 20 krzewy, 30 trawa, 40 uprawy, 50 zabudowa,
# 60 goły/skąpo porośnięty grunt, 70 śnieg, 80 woda, 90 mokradła.
WC_VEG = (10, 20, 30, 40)
WC_BUILT = 50
WC_BARE = 60
WC_WATER = 80


def _geobox(ds: xr.Dataset) -> GeoBox:
    crs, tr = mpc.grid(ds)
    return GeoBox((ds.sizes["y"], ds.sizes["x"]), tr, crs)


def worldcover(ds: xr.Dataset, bbox, year: int = 2021,
               verbose: bool = True) -> np.ndarray | None:
    """WorldCover wczytany NA DOKŁADNIE TĘ SAMĄ SIATKĘ co kompozyt.

    Przez `geobox=`, nie przez bbox+resolution — bbox dałby siatkę „prawie taką
    samą", a przesunięcie o pół piksela przy obrysach budynków oznacza etykiety
    z krawędzi dachu, czyli mieszane piksele w polu treningowym.
    """
    cat = mpc.client()
    items = [it for it in cat.search(collections=[C.WORLDCOVER_COLLECTION],
                                     bbox=bbox).items()
             if str(year) in it.id]
    if not items:
        if verbose:
            print(f"      WorldCover {year}: brak kafli")
        return None
    wc = stac_load(items, bands=["map"], geobox=_geobox(ds), chunks={})
    if "time" in wc.dims:
        # Kilka kafli z tego samego roku: bierzemy pierwszą niepustą wartość,
        # bo kafle nie nachodzą na siebie poza brzegiem.
        wc = wc["map"].max(dim="time")
    else:
        wc = wc["map"]
    a = wc.compute().values.astype("uint8")
    if verbose:
        u, c = np.unique(a[a > 0], return_counts=True)
        top = ", ".join(f"{int(v)}:{n/a.size*100:.0f}%"
                        for v, n in sorted(zip(u, c), key=lambda t: -t[1])[:5])
        print(f"      WorldCover {year}: {top}")
    return a


def _rasterize(gdf, ds: xr.Dataset, shrink_m: float = 0.0,
               min_area_m2: float = 0.0) -> np.ndarray:
    """Obrysy -> maska bool na siatce kompozytu.

    `shrink_m` zwęża wielokąt do środka. Piksel Sentinela ma 10 m, więc piksel
    na krawędzi dachu jest w połowie dachem, a w połowie tym, co obok. Takie
    piksele mieszane w polu treningowym uczą model nieistniejącego materiału —
    dlatego bierzemy tylko wnętrze.
    """
    crs, tr = mpc.grid(ds)
    shape = (ds.sizes["y"], ds.sizes["x"])
    if gdf is None or not len(gdf):
        return np.zeros(shape, bool)
    g = gdf.to_crs(crs.to_epsg()).geometry
    if min_area_m2 > 0:
        g = g[g.area >= min_area_m2]
    if shrink_m > 0 and len(g):
        # Bufor ujemny zjada małe wielokąty całkowicie — i dobrze, bo mały
        # budynek to 1-2 piksele S2, w większości mieszane z otoczeniem.
        g = g.buffer(-shrink_m)
        g = g[~g.is_empty]
    if not len(g):
        return np.zeros(shape, bool)
    return rasterize(
        [(geom, 1) for geom in g if geom is not None and not geom.is_empty],
        out_shape=shape, transform=tr, fill=0, dtype="uint8", all_touched=False,
    ).astype(bool)


def _core_mask(ds: xr.Dataset, site: dict) -> np.ndarray:
    """Maska samego obszaru inwestycji (w metrach, na siatce kompozytu)."""
    crs, _ = mpc.grid(ds)
    import geopandas as gpd
    from shapely.geometry import Point
    p = gpd.GeoSeries([Point(site["lon"], site["lat"])], crs="EPSG:4326") \
        .to_crs(crs.to_epsg()).iloc[0]
    yy = ds.y.values[:, None]
    xx = ds.x.values[None, :]
    return (np.abs(xx - p.x) <= site["radius_m"]) & (np.abs(yy - p.y) <= site["radius_m"])


def build(site: dict, verbose: bool = True):
    """Zwróć (X, y) — cechy i etykiety pikseli treningowych dla jednego obszaru.

    Pusty wynik (0 próbek) jest dopuszczalny i nie jest błędem: obszar bez
    WorldCovera po prostu nie wnosi nic do puli treningowej.
    """
    lab, d0, d1 = next(e for e in mpc.epochs() if e[0] == C.TRAIN_EPOCH)
    if verbose:
        print(f"   {site['id']}: pola treningowe z epoki {lab}")

    bbox = mpc.aoi_bbox(site, C.TRAIN_SCALE)
    ds = mpc.composite_cached(site, lab, d0, d1, scale=C.TRAIN_SCALE, verbose=verbose)
    if ds is None:
        return np.empty((0, len(F.FEATURES)), "float32"), np.empty(0, "uint8")

    wc = worldcover(ds, bbox, C.WORLDCOVER_YEAR, verbose)
    if wc is None:
        return np.empty((0, len(F.FEATURES)), "float32"), np.empty(0, "uint8")

    X = F.stack(ds)
    ok = F.valid_mask(X)
    ndvi = X[:, :, F.FEATURES.index("NDVI")]
    ndwi = X[:, :, F.FEATURES.index("NDWI")]
    bsi = X[:, :, F.FEATURES.index("BSI")]

    # --- obrysy OSM; brak OSM nie zatrzymuje potoku, tylko zubaża etykiety
    bld = pav = None
    try:
        bld = osm.buildings(site, bbox, verbose)
        pav = osm.pavement(site, bbox, verbose)
    except osm.OsmUnavailable as e:
        if verbose:
            print(f"      UWAGA: OSM niedostępny ({e}). Dach i asfalt będą "
                  f"rozdzielone progiem jasności w klasie 50 WorldCover — "
                  f"słabiej niż po obrysach.")

    m_bld = _rasterize(bld, ds, shrink_m=C.ROOF_SHRINK_M, min_area_m2=C.ROOF_MIN_AREA)
    m_pav = _rasterize(pav, ds) & ~_rasterize(bld, ds)

    y = np.full(wc.shape, NOLABEL, "uint8")

    # ZIELEŃ: zgoda WorldCovera i NDVI. WorldCover ma kilka procent błędu,
    # a warunek NDVI kosztuje nas tylko trochę próbek.
    y[np.isin(wc, WC_VEG) & (ndvi > C.LBL_VEG_NDVI)] = ZIELEN

    # WODA: zgoda WorldCovera i NDWI.
    y[(wc == WC_WATER) & (ndwi > C.LBL_WATER_NDWI)] = WODA

    # GRUNT: klasa 60. Bywa jej mało (w Ashburn 1,5%) albo zero w wilgotnym
    # klimacie, więc dokładamy pola uprawne o niskim NDVI i wysokim BSI —
    # zorana rola to fizycznie to samo co zdarty humus na budowie.
    bare = (wc == WC_BARE)
    plough = (wc == 40) & (ndvi < C.LBL_BARE_NDVI) & (bsi > C.LBL_BARE_BSI)
    y[bare | plough] = GRUNT

    # DACH i ASFALT.
    if m_bld.any():
        y[m_bld & (ndvi < C.LBL_IMPERV_NDVI)] = DACH
        y[m_pav & (ndvi < C.LBL_IMPERV_NDVI)] = ASFALT
    else:
        # Zapas bez OSM: w obrębie klasy 50 dzielimy po jasności. Jest to
        # słabsze (po części definiuje klasę przez cechę, którą potem mierzymy),
        # dlatego używane tylko wtedy, gdy obrysów naprawdę nie ma.
        bright = X[:, :, F.FEATURES.index("BRIGHT")]
        imp = (wc == WC_BUILT) & (ndvi < C.LBL_IMPERV_NDVI) & ok
        if imp.any():
            hi = np.nanpercentile(bright[imp], 80)
            lo = np.nanpercentile(bright[imp], 35)
            y[imp & (bright >= hi)] = DACH
            y[imp & (bright <= lo)] = ASFALT

    # Obszar inwestycji WYCINAMY z puli treningowej (patrz nagłówek pliku).
    y[_core_mask(ds, site)] = NOLABEL
    y[~ok] = NOLABEL

    # Losujemy po równo z każdej klasy, żeby las nie nauczył się, że
    # „wszystko jest drzewem", bo drzew jest 46%.
    rng = np.random.default_rng(C.SEED)
    Xs, ys = [], []
    for cls in (ZIELEN, GRUNT, DACH, ASFALT, WODA):
        idx = np.flatnonzero(y.ravel() == cls)
        if len(idx) == 0:
            if verbose:
                print(f"      {CLASS_NAMES[cls]:7s}: 0 próbek")
            continue
        take = min(len(idx), C.SAMPLES_PER_CLASS)
        sel = rng.choice(idx, take, replace=False)
        Xs.append(X.reshape(-1, X.shape[-1])[sel])
        ys.append(np.full(take, cls, "uint8"))
        if verbose:
            print(f"      {CLASS_NAMES[cls]:7s}: {take:5d} próbek "
                  f"(dostępnych {len(idx)})")

    if not Xs:
        return np.empty((0, len(F.FEATURES)), "float32"), np.empty(0, "uint8")
    return np.vstack(Xs).astype("float32"), np.concatenate(ys)


def campus_core(site: dict, ds: xr.Dataset, verbose: bool = False):
    """Maska RDZENIA KAMPUSU i powierzchnia hal w jego obrębie.

    ================== DLACZEGO NIE CAŁY KWADRAT AOI ==================
    Pierwsza wersja liczyła udziały w całym kwadratowym kadrze i porównywała je
    do powierzchni hal otagowanych jako data center. To było porównanie jabłek
    z gruszkami: licznik („zabudowa potwierdzona") obejmował KAŻDY jasny dach
    w kadrze — magazyny, osiedle obok, inną fabrykę — a mianownik tylko hale
    data center. Skutek: postęp 120–672% przy medianie ~230%, czyli dziewięć
    kampusów „przekroczyło" swój cel. To nie była niekompletność OSM, tylko
    źle postawione pytanie.
    Teraz mierzymy w obrysie samej inwestycji: otoczka wypukła obiektów
    otagowanych jako data center, poszerzona o bufor na drogi, parkingi,
    podstację i zieleń urządzoną.
    ===================================================================

    Zwraca (maska, powierzchnia_hal_m2). (None, 0) gdy OSM nic tu nie zna —
    wtedy wywołujący zostaje przy całym kadrze.
    """
    try:
        dc = osm.datacenters(site, mpc.aoi_bbox(site, 1.4), verbose=verbose)
    except osm.OsmUnavailable:
        return None, 0.0
    if dc is None or not len(dc):
        return None, 0.0

    crs, tr = mpc.grid(ds)
    g = dc.to_crs(crs.to_epsg())
    hull = g.geometry.union_all().convex_hull.buffer(C.CAMPUS_BUFFER_M)
    if hull.is_empty:
        return None, 0.0

    mask = rasterize([(hull, 1)], out_shape=(ds.sizes["y"], ds.sizes["x"]),
                     transform=tr, fill=0, dtype="uint8").astype(bool)
    if mask.sum() < C.MIN_CAMPUS_PIXELS:
        return None, 0.0

    # Powierzchnia hal: tylko obiekty z tagiem `building` (patrz discover.py).
    if "is_building" in g.columns:
        halls = g[g.is_building == 1]
    else:
        halls = g
    return mask, float(halls.area.sum())
