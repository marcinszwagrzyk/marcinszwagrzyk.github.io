# -*- coding: utf-8 -*-
"""All downloads, from Microsoft Planetary Computer (no account needed).

    python download.py            # everything
    python download.py dem        # Copernicus DEM, SRTM (NASADEM), ALOS AW3D30
    python download.py geometry   # Sentinel-1 orbit choice + incidence angle and heading
    python download.py s1         # quarterly Sentinel-1 RTC composites
    python download.py s2         # quarterly Sentinel-2 L2A composites

Only the site window is read from each Cloud-Optimized GeoTIFF, so the whole
download is small. Composites are cached in data/, a rerun skips what exists.
"""
import collections
import json
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np
import planetary_computer as pc
import pystac_client
import requests
from odc.stac import stac_load

import config as C

DEMS = {"srtm": ("nasadem", "elevation"), "alos": ("alos-dem", "data"), "cop": ("cop-dem-glo-30", "data")}
S2_BANDS = ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"]
S2_BAD_SCL = [0, 1, 3, 8, 9, 10, 11]   # no data, defective, cloud shadow, clouds, cirrus, snow


def client():
    return pystac_client.Client.open(C.STAC_URL, modifier=pc.sign_inplace)


def _load(items, bands, res, **kw):
    for attempt in range(4):
        try:
            return stac_load(items, bands=bands, crs=C.CRS, resolution=res, x=(C.X0, C.X1), y=(C.Y0, C.Y1),
                             patch_url=pc.sign, **kw).compute()
        except Exception as e:      # Azure blobs occasionally drop the connection
            print("retrying:", e)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("download failed")


# --------------------------------------------------------------------------- DEM
def dems(cl):
    out = {}
    for k, (col, band) in DEMS.items():
        items = list(cl.search(collections=[col], bbox=C.BBOX_LL).items())
        ds = _load(items, [band], C.RES_DEM, resampling="bilinear", dtype="float32", nodata=-32768)
        z = ds[band].values.max(0)    # neighbouring tiles touch, they do not overlap
        z[z < -1000] = np.nan
        out[k] = z[:C.N30, :C.N30]
        print(k, out[k].shape)
    np.savez_compressed(C.DATA / "dems.npz", **out)


# ------------------------------------------------------------------ S1 geometry
def geometry(cl):
    """Pick the relative orbit with the most scenes (constant viewing geometry) and
    read incidence angle and platform heading at the site from a GRD annotation."""
    t0 = C.quarters()[0][1]
    t1 = C.quarters()[-1][2]
    items = list(cl.search(collections=["sentinel-1-rtc"], bbox=C.BBOX_LL, datetime=f"{t0}/{t1}").items())
    orbit = collections.Counter(i.properties["sat:relative_orbit"] for i in items).most_common(1)[0][0]
    pt = {"type": "Point", "coordinates": [C.SITE["lon"], C.SITE["lat"]]}
    grds = [i for i in cl.search(collections=["sentinel-1-grd"], intersects=pt, datetime=f"{t0}/{t1}",
                                 max_items=300).items() if i.properties["sat:relative_orbit"] == orbit]
    P = np.empty((0, 3))
    for grd in grds:   # some annotation files do not resolve; take the first one that parses
        try:
            root = ET.fromstring(requests.get(grd.assets["schema-product-vv"].href, timeout=60).text)
            P = np.array([(float(p.find("latitude").text), float(p.find("longitude").text),
                           float(p.find("incidenceAngle").text)) for p in root.iter("geolocationGridPoint")])
        except Exception:
            continue
        if len(P):
            break
    d = np.hypot(P[:, 0] - C.SITE["lat"], (P[:, 1] - C.SITE["lon"]) * np.cos(np.radians(C.SITE["lat"])))
    i = np.argsort(d)[:4]
    w = 1 / (d[i] + 1e-9)
    geo = dict(relative_orbit=int(orbit), orbit_state=items[0].properties["sat:orbit_state"],
               incidence_deg=float((P[i, 2] * w).sum() / w.sum()),
               heading_deg=float(root.find(".//platformHeading").text),
               look="right")
    json.dump(geo, open(C.DATA / "geometry.json", "w"), indent=2)
    print(geo)


# ------------------------------------------------------------------- Sentinel-1
def s1(cl):
    """Quarterly median of VV and VH (dB). The median suppresses speckle and single
    wet days (wet soil raises backscatter by several dB)."""
    orbit = C.geometry()["relative_orbit"]
    (C.DATA / "s1").mkdir(exist_ok=True)
    for lab, t0, t1 in C.quarters():
        out = C.DATA / "s1" / f"{lab}.npz"
        if out.exists():
            continue
        items = [i for i in cl.search(collections=["sentinel-1-rtc"], bbox=C.BBOX_LL, datetime=f"{t0}/{t1}").items()
                 if i.properties["sat:relative_orbit"] == orbit and i.datetime.strftime("%Y-%m-%d") < t1]
        if not items:
            print(lab, "no scenes"); continue
        ds = _load(items, ["vv", "vh"], C.RES_S1, groupby="solar_day")
        with np.errstate(divide="ignore", invalid="ignore"):
            vv = 10 * np.log10(ds.vv.where(ds.vv > 0).values)
            vh = 10 * np.log10(ds.vh.where(ds.vh > 0).values)
        np.savez_compressed(out, vv=np.nanmedian(vv, 0)[:C.N10, :C.N10].astype("float32"),
                            vh=np.nanmedian(vh, 0)[:C.N10, :C.N10].astype("float32"),
                            dates=np.array([str(t)[:10] for t in ds.time.values]))
        print(lab, len(ds.time), "scenes", flush=True)


# ------------------------------------------------------------------- Sentinel-2
def s2(cl):
    """Quarterly median of cloud-free reflectance.

    Since processing baseline 04.00 (January 2022) L2A files carry BOA_ADD_OFFSET
    = −1000. Without removing it the series gets an artificial brightness jump at
    the turn of 2021/2022, so scenes are loaded in two groups by baseline."""
    (C.DATA / "s2").mkdir(exist_ok=True)
    for lab, t0, t1 in C.quarters():
        out = C.DATA / "s2" / f"{lab}.npz"
        if out.exists():
            continue
        items = [i for i in cl.search(collections=["sentinel-2-l2a"], bbox=C.BBOX_LL, datetime=f"{t0}/{t1}",
                                      query={"eo:cloud_cover": {"lt": 60}}).items()
                 if i.datetime.strftime("%Y-%m-%d") < t1]
        groups = collections.defaultdict(list)
        for i in items:
            try:
                groups[float(i.properties.get("s2:processing_baseline", "99")) >= 4.0].append(i)
            except ValueError:
                groups[True].append(i)
        stacks = []
        for new_baseline, its in groups.items():
            ds = _load(its, S2_BANDS, C.RES_S1, groupby="solar_day")
            arr = np.stack([ds[b].values.astype("float32") for b in S2_BANDS[:-1]], -1)
            arr[arr == 0] = np.nan
            if new_baseline:
                arr -= 1000
            arr[np.isin(ds.SCL.values, S2_BAD_SCL)] = np.nan
            stacks.append(arr[:, :C.N10, :C.N10] / 10000)
        if not stacks:
            print(lab, "no scenes"); continue
        arr = np.concatenate(stacks, 0)
        arr = arr[np.isfinite(arr[..., 3]).mean((1, 2)) > 0.7]   # ≥ 70% clear over the window
        if not len(arr):
            print(lab, "no clear scenes"); continue
        np.savez_compressed(out, refl=np.nanmedian(arr, 0).astype("float32"), n=len(arr))
        print(lab, len(arr), "scenes", flush=True)


if __name__ == "__main__":
    what = sys.argv[1:] or ["dem", "geometry", "s1", "s2"]
    cl = client()
    for step in what:
        {"dem": dems, "geometry": geometry, "s1": s1, "s2": s2}[step](cl)
