# -*- coding: utf-8 -*-
"""Coal stockpile: footprint, height and volume through time.

Three independent sources, each answering a different part of the question:

1. DEMs from 2000 / ~2008 / ~2012 (SRTM, ALOS AW3D30, Copernicus) — MEASURED
   height of the stockpile above the ground it was built on.
2. Sentinel-2 — footprint of black material, quarter by quarter. Coal has a
   flat, low spectrum; water is dark too, but not in the short-wave infrared.
3. Sentinel-1 — HEIGHT CHANGE after 2016 from the geocoding shift.
   RTC scenes are geocoded with Copernicus DEM (~2012). A surface that is Δh
   higher than the DEM is closer to the satellite than geocoding assumes, so it
   appears shifted towards the satellite by Δh · cot θ. The shift is measured
   with sub-pixel correlation in a network of quarter pairs and referenced to
   the median of stable control windows.
"""
import json

import numpy as np
import pandas as pd
from scipy import ndimage

import config as C

GEO = C.geometry()
THETA = GEO["incidence_deg"]
# Right-looking SAR: direction to the satellite = heading − 90° (azimuth, from north).
LOOK_AZ = (GEO["heading_deg"] - 90.0) % 360.0
COT = 1 / np.tan(np.radians(THETA))
U_E, U_S = np.sin(np.radians(LOOK_AZ)), -np.cos(np.radians(LOOK_AZ))   # east and south components

MIN_PEAK = 0.45   # minimum correlation peak; below it the texture no longer matches
MAX_SHIFT = 6     # px (60 m) — a stockpile does not change by ~47 m in a quarter
MAX_LAG = 4       # pairs of quarters 1–4 quarters apart
CUT_STABLE_M = 5  # |DEM difference| below this = stable ground for vertical alignment


# ----------------------------------------------------------------- footprint
def coal_water(s):
    coal = (s[..., 3] < 0.10) & (s[..., 2] < 0.09) & (s[..., 4] > 0.04) & (s[..., 4] < 0.17)
    water = (s[..., 3] < 0.04) & (s[..., 4] < 0.04)
    return coal, water


def footprint(labels):
    """Stockpile outline: black material or water in ≥ 30% of quarters, connected to
    the site centre. Settling ponds behind the bund are cut off by the opening."""
    freq, n = 0, 0
    for lab in labels:
        f = C.DATA / "s2" / f"{lab}.npz"
        if f.exists():
            c, w = coal_water(np.load(f)["refl"])
            freq, n = freq + (c | w), n + 1
    m = ndimage.binary_opening(freq / n >= 0.3, iterations=3)
    lab, _ = ndimage.label(m)
    m = lab == lab[C.N10 // 2, C.N10 // 2]
    return ndimage.binary_fill_holes(ndimage.binary_closing(m, iterations=3)), freq / n


# ------------------------------------------------------------------- DEMs
def aligned_dems():
    """SRTM and ALOS shifted vertically onto Copernicus (median difference over stable ground)."""
    d = dict(np.load(C.DATA / "dems.npz"))
    shifts = {}
    for k in ("srtm", "alos"):
        dd = d["cop"] - d[k]
        stable = np.abs(dd - np.nanmedian(dd)) < CUT_STABLE_M
        shifts[k] = float(np.nanmedian(dd[stable]))
        d[k] = d[k] + shifts[k]
    return d, shifts


def dem_history(m10):
    d, shifts = aligned_dems()
    m30 = m10.reshape(C.N30, 3, C.N30, 3).mean((1, 3)) > 0.5
    rows = []
    for k, yr in (("srtm", 2000.1), ("alos", 2008.5), ("cop", 2012.5)):
        dz = d[k] - d["srtm"]
        rows.append(dict(epoch=k, year=yr, volume_Mm3=float(dz[m30].sum() * C.RES_DEM ** 2 / 1e6),
                         mean_height_m=float(dz[m30].mean()), p98_height_m=float(np.percentile(dz[m30], 98))))
    return rows, d, m30, shifts


# ---------------------------------------------------- Sentinel-1 radargrammetry
def shift(ref, img, win):
    """Shift of the CONTENT of `img` relative to `ref` inside `win`, in metres
    (row = towards south, column = towards east), plus the correlation peak.

    Normalised cross-correlation evaluated directly for integer shifts within
    ±MAX_SHIFT, then a parabola through the peak and its neighbours (sub-pixel).
    Whole-image phase correlation can jump to a distant false peak once the
    stockpile texture changes after dumping — here such a jump is impossible."""
    r, c = win
    B = ref[r, c]
    B = (B - np.nanmean(B)) / np.nanstd(B)
    S = MAX_SHIFT
    cc = np.full((2 * S + 1, 2 * S + 1), -1.0)
    for i, dr in enumerate(range(-S, S + 1)):
        for j, dc in enumerate(range(-S, S + 1)):
            A = img[r.start + dr:r.stop + dr, c.start + dc:c.stop + dc]
            if A.shape != B.shape:
                continue
            A = (A - np.nanmean(A)) / np.nanstd(A)
            cc[i, j] = np.nanmean(A * B)
    i, j = np.unravel_index(np.argmax(cc), cc.shape)

    def par(m1, m0, p1):
        den = m1 - 2 * m0 + p1
        return 0.0 if den == 0 else 0.5 * (m1 - p1) / den
    di = par(cc[i - 1, j], cc[i, j], cc[i + 1, j]) if 0 < i < 2 * S else 0.0
    dj = par(cc[i, j - 1], cc[i, j], cc[i, j + 1]) if 0 < j < 2 * S else 0.0
    # content of img at (r + dr) matches ref at r  →  the content moved by +dr
    return np.array([i - S + di, j - S + dj]) * C.RES_S1, float(cc[i, j])


def to_height(s):
    """Shift vector (south, east) [m] → height change [m] along the look direction."""
    return (s[1] * U_E + s[0] * U_S) / COT


def network(I, win):
    """Δh series from a network of pairs (SBAS-like): shifts between quarters close
    in time (texture still matches), then weighted least squares (weight = peak²)
    with Δh(0) = 0. Quarters without a single good pair have no measurement."""
    Q = len(I)
    G, d, w = [], [], []
    for q in range(Q):
        for lag in range(1, MAX_LAG + 1):
            if q + lag >= Q:
                break
            s, p = shift(I[q], I[q + lag], win)
            if p < MIN_PEAK:
                continue
            g = np.zeros(Q); g[q + lag], g[q] = 1, -1
            G.append(g); d.append(to_height(s)); w.append(p)
    G, d, w = np.array(G), np.array(d), np.array(w)
    G = np.vstack([G, np.eye(Q)[0] * 10]); d = np.append(d, 0); w = np.append(w, 1)
    x, *_ = np.linalg.lstsq(G * w[:, None], d * w, rcond=None)
    x[np.abs(G[:-1]).sum(0) == 0] = np.nan
    return x, len(d) - 1


def s1_stack(labels):
    return np.array([np.load(C.DATA / "s1" / f"{l}.npz")["vv"] for l in labels])


def measurement_window(m10):
    rr, cc = np.where(ndimage.binary_erosion(m10, iterations=8))
    return slice(rr.min(), rr.max() + 1), slice(cc.min(), cc.max() + 1)


def gain():
    """Sensitivity of the method from the injection test (sensitivity.py): the part of
    a true height change that comes back out of the network. < 1 because the window
    also contains static edges. Without the test: 1 (no calibration)."""
    f = C.OUT / "sensitivity_test.json"
    if not f.exists():
        return 1.0
    return float(np.mean([r["recovered_after_m"] / r["injected_m"] for r in json.load(open(f))]))


def s1_heights(labels, m10):
    """Stockpile Δh relative to the first quarter.

    All windows shift TOGETHER by several metres at times (changes in Sentinel-1
    orbit processing, not terrain), so a reference is required. The median of
    the control windows is robust to one window that changes by itself."""
    I = s1_stack(labels)
    win = measurement_window(m10)
    h_raw, n_pairs = network(I, win)
    ctrl = np.array([network(I, w)[0] for w in C.CONTROL_WINDOWS])
    ref = np.nanmedian(ctrl, 0)
    g = gain()
    h = (h_raw - ref) / g
    # Noise of one window = spread of the control windows around their median
    # (sample std over 3 windows, pooled over all quarters); the stockpile has the same.
    sigma = float(np.sqrt(np.nanmean((ctrl - ref)[:, 1:] ** 2) * len(ctrl) / (len(ctrl) - 1))) / g
    return h, sigma, ctrl - ref, win, n_pairs


# ---------------------------------------------------------- Sentinel-2 / activity
def s2_cover(labels, m10):
    rows = []
    for lab in labels:
        f = C.DATA / "s2" / f"{lab}.npz"
        if not f.exists():
            rows.append(dict(quarter=lab)); continue
        z = np.load(f)
        s = z["refl"]
        coal, water = coal_water(s)
        ok = np.isfinite(s[..., 3]) & m10
        rows.append(dict(quarter=lab, n_scenes=int(z["n"]), coal_ha=float((coal & ok).sum() / 100),
                         water_ha=float((water & ok).sum() / 100),
                         brightness=float(np.nanmean(s[..., [2, 1, 0]][ok]))))
    return rows


def s1_activity(labels, m10):
    """Share of the stockpile whose radar signature changed since the previous quarter
    more than 99% of natural ground does (dumping, reclaiming, dozers)."""
    I = np.stack([ndimage.uniform_filter(np.nan_to_num(a, nan=-15), 3) for a in s1_stack(labels)])
    nat = np.zeros_like(m10)
    nat[C.NATURAL_WINDOW] = True
    out = [np.nan]
    for q in range(1, len(I)):
        d = np.abs(I[q] - I[q - 1])
        out.append(float((d[m10] > np.percentile(d[nat], 99)).mean() * 100))
    return out


def main():
    labels = [q[0] for q in C.quarters()]
    m10, freq = footprint(labels)
    area_km2 = m10.sum() * C.RES_S1 ** 2 / 1e6
    dem_rows, dems, m30, shifts = dem_history(m10)
    h, sigma, ctrl, win, n_pairs = s1_heights(labels, m10)
    tab = pd.DataFrame(s2_cover(labels, m10)).assign(
        dh_m=h, dv_Mm3=h * area_km2, dv_sigma_Mm3=sigma * area_km2, activity_pct=s1_activity(labels, m10))
    tab["year"] = tab.quarter.str[:4].astype(int)
    tab.to_csv(C.OUT / "stockpile_quarterly.csv", index=False)
    pd.DataFrame(dem_rows).to_csv(C.OUT / "stockpile_dem.csv", index=False)

    t = np.arange(len(h)) / 4
    ok = np.isfinite(h)
    trend = np.polyfit(t[ok], h[ok], 1)[0]
    trend_se = sigma / np.sqrt(((t[ok] - t[ok].mean()) ** 2).sum())
    summary = dict(
        name=C.NAME, quarters=[labels[0], labels[-1]], area_km2=area_km2,
        s1_geometry={k: GEO[k] for k in ("incidence_deg", "heading_deg", "orbit_state", "look")},
        shift_per_m_height=COT, method_sensitivity=gain(),
        dem_vertical_shifts_m=shifts, dem=dem_rows,
        s1_pairs=n_pairs, s1_sigma_m_per_quarter=sigma,
        s1_trend_m_per_year=float(trend), s1_trend_se_m_per_year=float(trend_se),
        s1_annual_median_dh_m={int(k): float(v) for k, v in tab.groupby("year").dh_m.median().items()},
        s1_window_px=[int(v) for v in (win[0].start, win[0].stop, win[1].start, win[1].stop)],
    )
    json.dump(summary, open(C.OUT / "stockpile_summary.json", "w", encoding="utf-8"), indent=2)
    np.savez_compressed(C.DATA / "results.npz", m10=m10, freq=freq, m30=m30, h=h, ctrl=ctrl,
                        **{f"z_{k}": v for k, v in dems.items()})
    print(json.dumps({k: v for k, v in summary.items() if k != "dem"}, indent=1))
    print(tab.round(2).to_string())


if __name__ == "__main__":
    main()
