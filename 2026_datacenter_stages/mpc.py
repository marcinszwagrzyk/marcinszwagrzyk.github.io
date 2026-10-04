# -*- coding: utf-8 -*-
"""Dostęp do Microsoft Planetary Computer: wyszukanie scen i złożenie kompozytu.

Dlaczego KOMPOZYT MEDIANOWY, a nie pojedyncze sceny: etap budowy zmienia się
w miesiącach, a chmury w dniach. Mediana z półrocza daje obraz bez chmur i bez
przypadkowego dnia z mgłą czy świeżym deszczem (mokra ziemia ma inny podpis
spektralny niż sucha, co samo w sobie przesuwałoby klasyfikację).

================= NAJWAŻNIEJSZA RZECZ W TYM PLIKU: OFFSET BOA =================
Sentinel-2 od "processing baseline" 04.00 (styczeń 2022) ma w metadanych
BOA_ADD_OFFSET = -1000. Liczby w plikach są przesunięte o +1000 względem
starszych scen. Sprawdzone na tym obszarze:
    2018 -> 02.12 | 2020 -> 02.12 | 2021 -> 03.00 | 2022 -> 04.00 | 2024 -> 05.11
Gdyby złożyć taki szereg bez poprawki, WSZYSTKIE wskaźniki (NDVI, NDBI, BSI)
dostałyby sztuczny uskok dokładnie na przełomie 2021/2022 — a potok uznałby go
za zmianę pokrycia terenu, czyli zgłosiłby "początek budowy" na każdym z
dziesięciu obszarów w tym samym kwartale. To jest ten rodzaj błędu, który daje
wyniki wyglądające sensownie i będące w całości nieprawdą.
Dlatego sceny ładujemy w DWÓCH GRUPACH wg baseline i offset odejmujemy tylko
tam, gdzie należy.
================================================================================
"""
from __future__ import annotations

import os
import time

import numpy as np
import planetary_computer as pc
import pystac_client
import xarray as xr
from odc.stac import stac_load

import config as C

# Ponowienia odczytu przez sieć (bloby Azure) — patrz komentarz w composite().
NET_RETRIES = 3
NET_BACKOFF_S = 10.0


def client() -> pystac_client.Client:
    """Katalog STAC z podpisywaniem URL-i (zasoby MPC wymagają tokenu)."""
    return pystac_client.Client.open(C.STAC_URL, modifier=pc.sign_inplace)


def aoi_bbox(site: dict, scale: float = 1.0) -> tuple[float, float, float, float]:
    """Kwadratowy bbox w stopniach wokół środka obszaru.

    `scale` > 1 poszerza bbox — używane przy próbkowaniu pól treningowych
    z otoczenia inwestycji.
    """
    r_m = site["radius_m"] * scale
    dlat = r_m / 111_320.0
    dlon = r_m / (111_320.0 * np.cos(np.radians(site["lat"])))
    return (site["lon"] - dlon, site["lat"] - dlat,
            site["lon"] + dlon, site["lat"] + dlat)


def epochs(start_year: int = None, end_year: int = None,
           per_year: int = None) -> list:
    """Lista epok jako (etykieta, data_od, data_do).

    H1 = marzec-sierpień (pełna wegetacja na półkuli północnej) — w tym okresie
    najlepiej widać zieleń urządzoną, bo trawnik jest zielony, a nie zeschnięty.
    H2 = wrzesień-luty — pokazuje gołą strukturę terenu bez listowia, co pomaga
    odróżnić wykop od łąki.
    """
    start_year = start_year or C.START_YEAR
    end_year = end_year or C.END_YEAR
    per_year = per_year or C.EPOCHS_PER_YEAR
    out = []
    for y in range(start_year, end_year + 1):
        out.append((f"{y}H1", f"{y}-03-01", f"{y}-08-31"))
        if per_year > 1:
            out.append((f"{y}H2", f"{y}-09-01", f"{y + 1}-02-28"))
    return out


# ------------------------------------------------------------------ offset BOA
def _needs_offset(item) -> bool:
    """Czy scena ma przesunięcie BOA (-1000), czyli baseline >= 04.00."""
    b = item.properties.get("s2:processing_baseline", "")
    try:
        return float(b) >= 4.0
    except (TypeError, ValueError):
        # Brak metadanej: zakładamy nowy format, bo takich scen jest dziś
        # większość. Fałszywe odjęcie 1000 od starej sceny widać od razu
        # (ujemne odbicie), fałszywe NIEodjęcie jest ciche — wybieramy błąd,
        # który sam się ujawnia.
        return True


def _select_items(items: list, max_n: int) -> list:
    """Ogranicz liczbę scen do kompozytu, ale NIE bierz najczystszych z jednego
    tygodnia — to dałoby "medianę" z jednego stanu terenu.

    Dzielimy okno czasu na `max_n` koszyków po dacie i z każdego bierzemy
    najmniej zachmurzoną scenę. Mediana z 12 scen rozłożonych po półroczu jest
    praktycznie tak samo odporna jak z 57, a pobiera się kilka razy krócej.
    """
    if len(items) <= max_n:
        return items
    items = sorted(items, key=lambda i: i.datetime)
    buckets = [[] for _ in range(max_n)]
    for k, it in enumerate(items):
        buckets[min(max_n - 1, k * max_n // len(items))].append(it)
    out = []
    for b in buckets:
        if b:
            out.append(min(b, key=lambda i: i.properties.get("eo:cloud_cover", 100)))
    return out


def _mask_clouds(ds: xr.Dataset) -> xr.Dataset:
    """Odrzuć piksele chmur, cieni i śniegu na podstawie SCL.

    Robimy to PRZED medianą, bo mediana z chmurami daje jasny, płaski obraz,
    który klasyfikator bierze za beton — czyli dokładnie najgorszy możliwy błąd
    w tym zadaniu.
    """
    if "SCL" not in ds:
        return ds
    bad = xr.zeros_like(ds["SCL"], dtype=bool)
    for v in C.SCL_DROP:
        bad = bad | (ds["SCL"] == v)
    bands = [b for b in ds.data_vars if b != "SCL"]
    return ds[bands].where(~bad)


def _load_group(items: list, bbox, offset: bool) -> xr.Dataset:
    """Wczytaj grupę scen o jednolitym formacie i przelicz na ODBICIE 0..1."""
    ds = stac_load(
        items,
        bands=C.S2_BANDS,
        bbox=bbox,
        resolution=C.RESOLUTION_M,
        crs="utm",             # lokalna strefa UTM = metry, bez zniekształceń
        groupby="solar_day",   # sceny z jednego przelotu w jedną warstwę
        chunks={},             # leniwie; mediana policzy się przy .compute()
    )
    ds = _mask_clouds(ds)
    # Liczby w plikach to DN. Odbicie = (DN + BOA_ADD_OFFSET) / 10000.
    shift = -1000.0 if offset else 0.0
    for b in list(ds.data_vars):
        ds[b] = (ds[b].astype("float32") + shift) / 10000.0
    return ds


def composite(site: dict, date_from: str, date_to: str,
              scale: float = 1.0, verbose: bool = True):
    """Kompozyt medianowy w jednostkach odbicia (0..1). None, gdy brak scen."""
    cat = client()
    bbox = aoi_bbox(site, scale)
    search = cat.search(
        collections=[C.S2_COLLECTION],
        bbox=bbox,
        datetime=f"{date_from}/{date_to}",
        query={"eo:cloud_cover": {"lt": C.MAX_CLOUD}},
    )
    items = list(search.items())
    if not items:
        if verbose:
            print(f"      brak scen (<{C.MAX_CLOUD}% chmur)")
        return None

    n_found = len(items)
    items = _select_items(items, C.MAX_SCENES_PER_EPOCH)

    old = [i for i in items if not _needs_offset(i)]
    new = [i for i in items if _needs_offset(i)]

    # PONAWIANIE. Odczyt leci przez sieć do blobów Azure i potrafi paść na
    # rzeczach przejściowych — w tym biegu zdarzyło się „Could not resolve host:
    # sentinel2l2a01.blob.core.windows.net" i „Chunk and warp failed".
    # Bez ponowienia pojedyncza czkawka DNS kosztuje cały obszar, a przy
    # 160 kompozytach na bieg jest prawie pewne, że coś takiego trafi.
    last = None
    for attempt in range(NET_RETRIES):
        try:
            parts = []
            if old:
                parts.append(_load_group(old, bbox, offset=False))
            if new:
                parts.append(_load_group(new, bbox, offset=True))
            ds = parts[0] if len(parts) == 1 else xr.concat(parts, dim="time")
            med = ds.median(dim="time", skipna=True).compute()
            break
        except Exception as e:                          # noqa: BLE001
            last = e
            if attempt + 1 >= NET_RETRIES:
                if verbose:
                    print(f"      odczyt nieudany po {NET_RETRIES} próbach: "
                          f"{type(e).__name__}")
                return None
            wait = NET_BACKOFF_S * (attempt + 1)
            if verbose:
                print(f"      błąd odczytu ({type(e).__name__}), "
                      f"ponawiam za {wait:.0f}s")
            time.sleep(wait)

    # Udział pikseli, które przeżyły maskowanie — miara zaufania do kompozytu.
    valid = float(np.isfinite(med["B04"]).mean())
    med.attrs.update(
        n_found=n_found, n_used=len(items), valid_frac=valid,
        baseline_mix=f"{len(old)} bez offsetu / {len(new)} z offsetem",
        epoch_from=date_from, epoch_to=date_to, site=site["id"],
    )
    if verbose:
        print(f"      scen: {len(items)}/{n_found}   ważnych pikseli: {valid*100:.0f}%"
              f"   z offsetem: {len(new)}/{len(items)}")
    return med


def grid(ds: xr.Dataset):
    """(CRS, transform) siatki kompozytu — potrzebne do rasteryzacji obrysów OSM
    dokładnie na te same piksele.

    Bierzemy to z koordynaty `spatial_ref`, którą odc.stac zapisuje i która
    przeżywa zapis do NetCDF (sprawdzone: `crs_wkt` + `GeoTransform`).
    Sam akcesor `ds.rio.crs` po odczycie z pliku zwraca None, więc nie na nim
    polegamy.
    """
    from rasterio.crs import CRS
    from rasterio.transform import Affine

    sr = ds.coords["spatial_ref"].attrs
    crs = CRS.from_wkt(sr["crs_wkt"])
    gt = [float(v) for v in sr["GeoTransform"].split()]
    return crs, Affine.from_gdal(*gt)


def cache_path(site_id: str, epoch: str, scale: float = 1.0) -> str:
    os.makedirs(C.CACHE_DIR, exist_ok=True)
    tag = "" if abs(scale - 1.0) < 1e-6 else f"_x{scale:g}"
    return os.path.join(C.CACHE_DIR, f"{site_id}_{epoch}{tag}.nc")


def composite_cached(site: dict, epoch: str, date_from: str, date_to: str,
                     scale: float = 1.0, verbose: bool = True):
    """Kompozyt z pamięci na dysku. Pobranie jednej epoki to kilkadziesiąt MB
    ruchu, a epok jest 16 na obszar — bez cache każda poprawka w klasyfikatorze
    oznaczałaby ponowne ściąganie wszystkiego."""
    path = cache_path(site["id"], epoch, scale)
    if os.path.exists(path):
        if verbose:
            print(f"      z cache: {os.path.basename(path)}")
        return xr.open_dataset(path)
    ds = composite(site, date_from, date_to, scale=scale, verbose=verbose)
    if ds is None:
        return None
    ds.to_netcdf(path)
    return ds
