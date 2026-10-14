# -*- coding: utf-8 -*-
"""Long-record hazard classification from raw measurements (not from an event catalogue).

GDACS starts in 2000 (floods), 2011 (cyclones) and 2018 (droughts). For the hex
maps we classify hazards ourselves from physical data with 45-75 years of record:

  cyclones   IBTrACS 6-hourly winds (1980-): days with tropical-storm-force wind
             (>= 34 kt) and with major-hurricane wind (>= 96 kt, cat. 3-5) per hex;
  drought    GPCP v2.3 monthly precipitation (1979-), 2.5°: months with SPI-6 <= -1.0;
  monsoon    GPCP rainfall of the local summer season in monsoon domains, % of normal
             (shown as a deficit: monsoon drought);
  heat       GHCN-CAMS monthly 2 m temperature over land (1948-), 0.5° -> 2.5°:
             months above the 90th percentile of the DETRENDED anomaly
             (otherwise global warming alone would make recent phases look hotter).

Every measure is reduced to one value per (ENSO year Jun-May, 2.5° cell).
SPI is computed non-parametrically: for every cell and calendar month the
running sum is ranked against all years and the rank is mapped to a z-score.
"""
from __future__ import annotations

from functools import lru_cache

import h5py
import numpy as np
import pandas as pd
from scipy.stats import norm
from shapely import contains_xy
from shapely.ops import unary_union

import basemap as B
import config as C

GPCP = C.DATA / "gpcp_precip.mon.mean.nc"
GHCN = C.DATA / "ghcncams_air.mon.mean.nc"
IBT_POINTS = C.DATA / "ibtracs_points.csv"


# ------------------------------------------------------------------ readers
def _times(h, unit_hours=False):
    t = h["time"][:]
    base = pd.Timestamp("1800-01-01")
    td = pd.to_timedelta(t, unit="h" if unit_hours else "D")
    return (base + td).to_period("M")


def _flip_lon(lon, arr):
    """0..360 -> -180..180 along the last axis."""
    lon = np.where(lon > 180, lon - 360, lon)
    order = np.argsort(lon)
    return lon[order], arr[..., order]


@lru_cache(maxsize=1)
def gpcp():
    with h5py.File(GPCP) as h:
        p = h["precip"][:].astype("float32")
        lat, lon = h["lat"][:], h["lon"][:]
        months = _times(h)
    p[p < -1e30] = np.nan
    lon, p = _flip_lon(lon, p)
    return months, lat, lon, p


@lru_cache(maxsize=1)
def ghcn_25():
    """GHCN-CAMS 0.5° -> 2.5° (mean of the 5x5 land cells), read in time chunks."""
    with h5py.File(GHCN) as h:
        lat, lon = h["lat"][:], h["lon"][:]
        months = _times(h, unit_hours=True)
        ds = h["air"]
        nt = ds.shape[0]
        out = np.empty((nt, 72, 144), "float32")
        for i in range(0, nt, 60):
            a = ds[i:i + 60].astype("float32")
            a[a < -1e30] = np.nan
            a = a.reshape(a.shape[0], 72, 5, 144, 5)
            with np.errstate(all="ignore"):
                out[i:i + 60] = np.nanmean(a, axis=(2, 4))
    lat25 = lat.reshape(72, 5).mean(1)
    lon25 = lon.reshape(144, 5).mean(1)
    lon25, out = _flip_lon(lon25, out)
    return months, lat25, lon25, out


@lru_cache(maxsize=4)
def land_mask(lat_t: tuple, lon_t: tuple) -> np.ndarray:
    land = unary_union(B.world().geometry.values)
    gx, gy = np.meshgrid(np.array(lon_t), np.array(lat_t))
    return contains_xy(land, gx, gy)


# ------------------------------------------------------------ classifiers
def spi(p: np.ndarray, months: pd.PeriodIndex, k: int) -> np.ndarray:
    """Non-parametric SPI-k: rank of the k-month running sum within its calendar month."""
    s = pd.DataFrame(p.reshape(len(p), -1)).rolling(k, min_periods=k).sum().to_numpy()
    z = np.full_like(s, np.nan)
    mon = np.asarray(months.month)
    for m in range(1, 13):
        idx = np.where(mon == m)[0]
        block = s[idx]
        ok = ~np.isnan(block)
        r = pd.DataFrame(block).rank(axis=0, method="average").to_numpy()
        n = ok.sum(0)
        with np.errstate(all="ignore"):
            q = (r - 0.44) / (n + 0.12)          # Gringorten plotting position
        z[idx] = np.where(ok, norm.ppf(q), np.nan)
    return z.reshape(p.shape)


def enso_year_of(months: pd.PeriodIndex) -> np.ndarray:
    return np.asarray(months.year) - (np.asarray(months.month) < C.ENSO_YEAR_START_MONTH)


def per_year(flag: np.ndarray, months: pd.PeriodIndex, first: int, last: int) -> dict[int, np.ndarray]:
    """Monthly 0/1 flags -> count of flagged months in each complete ENSO year."""
    ey = enso_year_of(months)
    out = {}
    for y in range(first, last + 1):
        sel = ey == y
        if sel.sum() == 12:
            with np.errstate(all="ignore"):
                out[y] = np.nansum(flag[sel], axis=0) * np.where(np.isnan(flag[sel]).all(0), np.nan, 1)
    return out


def heavy_rain_months(first, last):
    months, lat, lon, p = gpcp()
    z = spi(p, months, 3)
    flag = np.where(np.isnan(z), np.nan, (z >= 1.5).astype("float32"))
    return lat, lon, per_year(flag, months, first, last)


def drought_months(first, last):
    months, lat, lon, p = gpcp()
    z = spi(p, months, 6)
    flag = np.where(np.isnan(z), np.nan, (z <= -1.0).astype("float32"))
    return lat, lon, per_year(flag, months, first, last)


def monsoon_rain(first, last):
    """Local-summer rainfall in monsoon domains, % of the 1980-2025 mean.

    Domain (after Wang & Ding 2008): summer-minus-winter rain > 2.5 mm/day and the
    summer half-year bringing > 55% of the annual total. Summer = May-Sep in the
    north, Nov-Mar in the south. The JJAS (north) and DJFM (south) totals both fall
    inside one Jun-May ENSO year.
    """
    months, lat, lon, p = gpcp()
    mon = np.asarray(months.month)
    nh = lat[:, None] > 0
    clim = np.stack([np.nanmean(p[mon == m], 0) for m in range(1, 13)])
    mjjas, ndjfm = clim[[4, 5, 6, 7, 8]].sum(0), clim[[10, 11, 0, 1, 2]].sum(0)
    summer, winter = np.where(nh, mjjas, ndjfm), np.where(nh, ndjfm, mjjas)
    domain = ((summer - winter) / 5 > 2.5) & (summer / clim.sum(0) > 0.55)
    ey = enso_year_of(months)
    vals = {}
    for y in range(first, last + 1):
        jjas = (ey == y) & np.isin(mon, [6, 7, 8, 9])
        djfm = (ey == y) & np.isin(mon, [12, 1, 2, 3])
        if jjas.sum() == 4 and djfm.sum() == 4:
            v = np.where(nh, p[jjas].mean(0), p[djfm].mean(0))
            vals[y] = np.where(domain, v, np.nan)
    mean = np.nanmean(np.stack(list(vals.values())), 0)
    with np.errstate(all="ignore"):
        pct = {y: 100 * v / mean for y, v in vals.items()}
    return lat, lon, pct, mean


def heat_months(first, last):
    """Months with detrended temperature anomaly above the cell's 90th percentile."""
    months, lat, lon, t = ghcn_25()
    mon = np.asarray(months.month)
    sel = (np.asarray(months.year) >= first) & (np.asarray(months.year) <= last + 1)
    months, t, mon = months[sel], t[sel], mon[sel]
    anom = np.empty_like(t)
    for m in range(1, 13):
        anom[mon == m] = t[mon == m] - np.nanmean(t[mon == m], 0)
    # remove the linear warming trend, cell by cell
    x = np.arange(len(t), dtype="float32")
    a2 = anom.reshape(len(t), -1)
    ok = ~np.isnan(a2)
    xm = np.where(ok, x[:, None], np.nan)
    with np.errstate(all="ignore"):
        xbar, ybar = np.nanmean(xm, 0), np.nanmean(a2, 0)
        slope = np.nansum((xm - xbar) * (a2 - ybar), 0) / np.nansum((xm - xbar) ** 2, 0)
    det = (a2 - (ybar + slope * (x[:, None] - xbar))).reshape(t.shape)
    flag = np.full(t.shape, np.nan, "float32")
    for m in range(1, 13):
        d = det[mon == m]
        q90 = np.nanpercentile(d, 90, axis=0)
        flag[mon == m] = np.where(np.isnan(d), np.nan, (d > q90).astype("float32"))
    return lat, lon, per_year(flag, months, first, last)


# ------------------------------------------------------------ cyclone winds
def ibtracs_points(refresh=False) -> pd.DataFrame:
    """6-hourly IBTrACS fixes with tropical-storm-force wind (>= 34 kt)."""
    if IBT_POINTS.exists() and not refresh:
        return pd.read_csv(IBT_POINTS, parse_dates=["time"])
    cols = ["SID", "ISO_TIME", "LAT", "LON", "USA_WIND", "TRACK_TYPE"]
    t = pd.read_csv(C.DATA / "ibtracs_since1980.csv", usecols=cols, skiprows=[1],
                    keep_default_na=False, low_memory=False)
    t = t[t.TRACK_TYPE == "main"]
    t["time"] = pd.to_datetime(t.ISO_TIME)
    t = t[t.time.dt.hour.isin([0, 6, 12, 18]) & (t.time.dt.minute == 0)]
    t["wind"] = pd.to_numeric(t.USA_WIND, errors="coerce")
    t = t[t.wind >= 34]
    out = pd.DataFrame({"sid": t.SID, "time": t.time,
                        "lat": pd.to_numeric(t.LAT, errors="coerce"),
                        "lon": pd.to_numeric(t.LON, errors="coerce"), "wind": t.wind})
    out.to_csv(IBT_POINTS, index=False)
    return out
