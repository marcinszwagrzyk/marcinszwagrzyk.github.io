# -*- coding: utf-8 -*-
"""GDACS and IBTrACS events -> tables with basin, category and ENSO year.

One function per source; both return the same cyclone columns (basin, group,
ss_cat, enso_year) so the analysis does not need to know where a row came from.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
from data import load_gdacs

# Pacific coast of Central America (lon, lat): south/west of this line is the
# East Pacific, north/east of it the Atlantic (Caribbean, Gulf of Mexico).
_COAST = np.array([(-100.0, 19.0), (-97.0, 16.0), (-92.0, 14.5), (-87.0, 13.0),
                   (-85.0, 10.0), (-80.0, 7.5), (-77.0, 7.0)])


def basin(lon: float, lat: float) -> str:
    lon = ((lon + 180) % 360) - 180
    if lat >= 0:
        if lon < -100 or lon >= 180:
            return "EP"
        if -100 <= lon < -77:
            coast_lat = np.interp(lon, _COAST[:, 0], _COAST[:, 1])
            return "EP" if lat < coast_lat else "NA"
        if -77 <= lon < 30:
            return "NA"
        if 30 <= lon < 100:
            return "NI"
        return "WP"                      # 100°E .. 180°
    if 10 <= lon < 135:
        return "SI"
    return "SP"


def enso_year(ts: pd.Series) -> pd.Series:
    """Date -> ENSO year (Jun–May), e.g. 2016-02-03 -> 2015."""
    return ts.dt.year - (ts.dt.month < C.ENSO_YEAR_START_MONTH).astype(int)


def ss_category(wind_kmh: pd.Series) -> pd.Series:
    return pd.cut(wind_kmh, C.SS_BINS, labels=C.SS_LABELS, right=False)


# --------------------------------------------------------------------- GDACS
def gdacs() -> pd.DataFrame:
    df = load_gdacs()
    df["enso_year"] = enso_year(df.start)
    df["month"] = df.start.dt.month
    tc = df.type == "TC"
    df.loc[tc, "basin"] = [basin(x, y) for x, y in zip(df.lon[tc], df.lat[tc])]
    df["group"] = df.basin.map(C.BASIN_GROUP)
    df["ss_cat"] = ss_category(df.wind_kmh)
    df["iso_set"] = df.iso3.fillna("").str.split(";").map(lambda s: {x for x in s if x})
    df["severe"] = df.alert.isin(["Orange", "Red"])
    return df


def in_region(df: pd.DataFrame, iso3: set, months=None) -> pd.Series:
    m = df.iso_set.map(lambda s: bool(s & iso3))
    if months:
        m &= df.month.isin(months)
    return m


def in_monsoon(df: pd.DataFrame) -> pd.Series:
    """Flood inside any monsoon system, in that system's season."""
    m = pd.Series(False, index=df.index)
    for r in C.MONSOONS.values():
        m |= in_region(df, r["iso3"], r["months"])
    return m


def drought_months(dr: pd.DataFrame) -> pd.DataFrame:
    """Drought events -> one row per (event, month in which it was active)."""
    rows = []
    for _, e in dr.iterrows():
        for m in pd.period_range(e.start.to_period("M"), e.end.to_period("M"), freq="M"):
            rows.append((e.eventid, m, e.lon, e.lat, e.severe))
    return pd.DataFrame(rows, columns=["eventid", "month", "lon", "lat", "severe"])


# ------------------------------------------------------------------- IBTrACS
def ibtracs() -> pd.DataFrame:
    """One row per IBTrACS storm (since 1980): genesis basin, max wind, ACE.

    Wind: USA_WIND (1-min, knots; NHC/CPHC/JTWC), the same definition as the
    Saffir-Simpson scale and GDACS. A storm counts once it reached 34 kt.
    """
    cols = ["SID", "SEASON", "BASIN", "NAME", "ISO_TIME", "NATURE", "LAT", "LON",
            "USA_WIND", "TRACK_TYPE"]
    # keep_default_na=False: pandas would read basin code "NA" (Atlantic) as missing
    t = pd.read_csv(C.DATA / "ibtracs_since1980.csv", usecols=cols, skiprows=[1],
                    keep_default_na=False, low_memory=False)
    t = t[t.TRACK_TYPE == "main"]
    t["ISO_TIME"] = pd.to_datetime(t.ISO_TIME)
    t["wind"] = pd.to_numeric(t.USA_WIND.replace({"": np.nan, " ": np.nan}), errors="coerce")
    t["LAT"] = pd.to_numeric(t.LAT, errors="coerce")
    t["LON"] = pd.to_numeric(t.LON, errors="coerce")
    # ACE: sum of v^2 (kt) at synoptic times 00/06/12/18 UTC with v >= 35 kt
    syn = t.ISO_TIME.dt.hour.isin([0, 6, 12, 18]) & (t.ISO_TIME.dt.minute == 0)
    t["ace"] = np.where(syn & (t.wind >= 35), t.wind ** 2 / 1e4, 0.0)

    ts = t[t.wind >= 34]
    first = ts.sort_values("ISO_TIME").groupby("SID").first()
    g = ts.groupby("SID")
    s = pd.DataFrame({
        "name": first.NAME, "start": first.ISO_TIME,
        "lon": first.LON, "lat": first.LAT,
        "max_wind_kt": g.wind.max(),
        "ace": t.groupby("SID").ace.sum().reindex(first.index),
    })
    s["basin"] = [basin(x, y) for x, y in zip(s.lon, s.lat)]
    s["group"] = s.basin.map(C.BASIN_GROUP)
    s["wind_kmh"] = s.max_wind_kt * 1.852
    s["ss_cat"] = ss_category(s.wind_kmh)
    s["enso_year"] = enso_year(s.start)
    s["month"] = s.start.dt.month
    return s.reset_index()


def load_storms() -> pd.DataFrame:
    """IBTrACS storm table saved by analysis.py (much faster than parsing 145 MB)."""
    # keep_default_na=False: otherwise basin "NA" (Atlantic) loads as missing
    s = pd.read_csv(C.OUT / "ibtracs_storms.csv", parse_dates=["start"],
                    keep_default_na=False, na_values=[""])
    s["ss_cat"] = pd.Categorical(s.ss_cat, categories=C.SS_LABELS, ordered=True)
    return s


if __name__ == "__main__":
    d = gdacs()
    pd.set_option("display.width", 160)
    print(d.groupby(["type", "enso_year"]).size().unstack(0).tail(30))
    tc = d[d.type == "TC"]
    print(tc.groupby(["enso_year", "basin"]).size().unstack().tail(16))
    print(tc.ss_cat.value_counts())
    print(d[d.type == "FL"].source.value_counts().head(10))
