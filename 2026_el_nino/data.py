# -*- coding: utf-8 -*-
"""Data download with an on-disk cache.

    python data.py            # download whatever is missing
    python data.py --refresh  # re-download the current GDACS year and the ENSO indices

Every source lands in data/ in raw form. Downstream scripts read only from
disk, so the analysis is reproducible offline.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time

import pandas as pd
import requests

import config as C

# Note: the GDACS WAF rejects (403) unusual User-Agents, so keep the requests default.
UA: dict = {}
THIS_YEAR = dt.date.today().year


def _get(url, params=None, tries=4, timeout=120):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code == 204:          # GDACS: no events
                return r
        except requests.RequestException as e:
            err = e
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"failed to download {url} {params}")


# ------------------------------------------------------------------ ENSO
def fetch_index(url, name, refresh=False):
    p = C.DATA / f"{name}.txt"
    if refresh or not p.exists():
        p.write_text(_get(url).text, encoding="utf-8")
    return p


def read_index(name):
    """RONI/ONI -> DataFrame [season, year, anom, mid] (mid = middle month)."""
    p = C.DATA / f"{name}.txt"
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and re.fullmatch(r"[A-Z]{3}", parts[0]) and parts[1].isdigit():
            rows.append((parts[0], int(parts[1]), float(parts[-1])))
    df = pd.DataFrame(rows, columns=["season", "year", "anom"])
    order = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO",
             "SON", "OND", "NDJ"]
    # middle month of the season: DJF -> 1 (January), NDJ -> 12
    df["mid_month"] = df.season.map({s: i + 1 for i, s in enumerate(order)})
    df["date"] = pd.to_datetime(dict(year=df.year, month=df.mid_month, day=15))
    return df.sort_values("date").reset_index(drop=True)


# ------------------------------------------------------------------ GDACS
def fetch_gdacs_year(etype, year, refresh=False):
    p = C.DATA / "gdacs" / f"{etype}_{year}.json"
    p.parent.mkdir(exist_ok=True)
    if p.exists() and not refresh:
        return p
    feats, page = [], 1
    while True:
        r = _get(C.GDACS_URL, dict(eventlist=etype, fromDate=f"{year}-01-01",
                                   toDate=f"{year}-12-31",
                                   alertlevel="green;orange;red",
                                   pagesize=100, pagenumber=page))
        f = r.json().get("features", []) if r.text.strip() else []
        feats += f
        if len(f) < 100:
            break
        page += 1
    p.write_text(json.dumps(feats), encoding="utf-8")
    return p


_WIND = re.compile(r"maximum wind speed of\s*([\d.]+)\s*km/h", re.I)


def load_gdacs():
    """All downloaded events -> one DataFrame, one row per event."""
    rows = []
    for p in sorted((C.DATA / "gdacs").glob("*.json")):
        for f in json.loads(p.read_text(encoding="utf-8")):
            pr = f["properties"]
            lon, lat = f["geometry"]["coordinates"][:2]
            sev = pr.get("severitydata") or {}
            wind = None
            if pr["eventtype"] == "TC":
                m = _WIND.search(sev.get("severitytext") or "")
                wind = float(m.group(1)) if m else sev.get("severity")
            iso = {c["iso3"] for c in (pr.get("affectedcountries") or []) if c.get("iso3")}
            if pr.get("iso3"):
                iso |= {pr["iso3"]}
            rows.append(dict(
                type=pr["eventtype"], eventid=pr["eventid"],
                name=pr.get("eventname") or pr.get("name"),
                start=pd.to_datetime(pr["fromdate"][:10]),
                end=pd.to_datetime(pr["todate"][:10]),
                lon=lon, lat=lat,
                alert=(pr.get("alertlevel") or "").capitalize(),
                severity=sev.get("severity"), wind_kmh=wind,
                iso3=";".join(sorted(iso)), country=pr.get("country") or "",
                source=pr.get("source") or "",
            ))
    df = pd.DataFrame(rows)
    # the same event can come back from two yearly queries (e.g. it spans New Year)
    df = df.sort_values("start").drop_duplicates(["type", "eventid"], keep="first")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- IBTrACS
def fetch_ibtracs(refresh=False):
    p = C.DATA / "ibtracs_since1980.csv"
    if p.exists() and not refresh:
        return p
    with requests.get(C.IBTRACS_URL, headers=UA, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(p, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return p


def fetch_file(url, name, refresh=False):
    """Plain streamed download into data/ (GPCP, GHCN-CAMS)."""
    p = C.DATA / name
    if p.exists() and not refresh:
        return p
    with requests.get(url, headers=UA, stream=True, timeout=1800) as r:
        r.raise_for_status()
        with open(p, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return p


def fetch_naturalearth(refresh=False):
    p = C.DATA / "ne_110m_admin_0_countries.zip"
    if refresh or not p.exists():
        p.write_bytes(_get(C.NE_URL).content)
    return p


def main(refresh=False):
    for url, name in ((C.RONI_URL, "roni"), (C.ONI_URL, "oni")):
        fetch_index(url, name, refresh)
        print(f"{name}: last season {read_index(name).iloc[-1][['season','year','anom']].tolist()}")
    fetch_naturalearth()
    for t in C.GDACS_TYPES:
        n = 0
        for y in range(C.GDACS_DOWNLOAD_FROM, THIS_YEAR + 1):
            p = fetch_gdacs_year(t, y, refresh=refresh and y == THIS_YEAR)
            n += len(json.loads(p.read_text(encoding="utf-8")))
        print(f"GDACS {t}: {n} events {C.GDACS_DOWNLOAD_FROM}-{THIS_YEAR}", flush=True)
    p = fetch_ibtracs()
    print(f"IBTrACS: {p.stat().st_size/1e6:.0f} MB")
    for url, name in ((C.GPCP_URL, "gpcp_precip.mon.mean.nc"), (C.GHCN_URL, "ghcncams_air.mon.mean.nc")):
        p = fetch_file(url, name, refresh)
        print(f"{name}: {p.stat().st_size/1e6:.0f} MB")


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
