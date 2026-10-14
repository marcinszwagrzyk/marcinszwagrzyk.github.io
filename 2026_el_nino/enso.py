# -*- coding: utf-8 -*-
"""ENSO year classification (Jun–May) and equal-size El Niño / Neutral / La Niña groups."""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
from data import read_index


def season_phases(idx: pd.DataFrame) -> pd.DataFrame:
    """Phase of every season by the CPC rule: episode = >= 5 consecutive seasons past the threshold."""
    idx = idx.copy()
    idx["phase"] = C.NEUTRAL
    for sign, name in ((1, "El Niño"), (-1, "La Niña")):
        over = (sign * idx.anom >= C.ENSO_THRESHOLD).to_numpy()
        i = 0
        while i < len(over):
            if over[i]:
                j = i
                while j < len(over) and over[j]:
                    j += 1
                if j - i >= C.ENSO_MIN_RUN:
                    idx.loc[i:j - 1, "phase"] = name
                i = j
            else:
                i += 1
    return idx


def strength(a: float) -> str:
    a = abs(a)
    if a >= 2.0:
        return "very strong"
    if a >= 1.5:
        return "strong"
    if a >= 1.0:
        return "moderate"
    if a >= 0.5:
        return "weak"
    return "—"


def enso_years(index: str = "roni") -> pd.DataFrame:
    """One row per ENSO year Y (Jun Y .. May Y+1).

    phase    : from the peak seasons OND(Y), NDJ(Y), DJF(Y+1); if any of them lies
               inside a CPC episode, the year takes that episode's phase;
    peak     : anomaly of the peak season with the largest magnitude;
    complete : whether all 12 months of the year have already passed.
    """
    idx = season_phases(read_index(index))
    rows = []
    last = idx.iloc[-1]
    for y in range(idx.year.min(), idx.year.max() + 1):
        peak = idx[((idx.season.isin(["OND", "NDJ"])) & (idx.year == y))
                   | ((idx.season == "DJF") & (idx.year == y + 1))]
        if peak.empty:
            continue
        ph = peak.phase.tolist()
        phase = ("El Niño" if "El Niño" in ph else
                 "La Niña" if "La Niña" in ph else C.NEUTRAL)
        pk = peak.anom.iloc[np.argmax(np.abs(peak.anom.to_numpy()))]
        complete = (last.year > y + 1) or (last.year == y + 1 and last.mid_month >= 5)
        jas = idx[(idx.season == "JAS") & (idx.year == y)].anom
        rows.append(dict(year=y, label=f"{y}/{str(y + 1)[2:]}", phase=phase, peak=pk,
                         strength=strength(pk) if phase != C.NEUTRAL else "—",
                         jas=jas.iloc[0] if len(jas) else np.nan,
                         n_peak_seasons=len(peak), complete=complete))
    return pd.DataFrame(rows)


def equal_groups(years: pd.DataFrame, avail, strata=None) -> dict[str, list[int]]:
    """Like _equal_groups, but optionally separately within each stratum (e.g. the
    DFO / GloFAS flood catalogue), so every phase gets as many years from each catalogue."""
    if not strata:
        return _equal_groups(years, avail)
    out = {ph: [] for ph in C.PHASES}
    for a, b in strata:
        g = _equal_groups(years, [y for y in avail if a <= y <= b])
        for ph in C.PHASES:
            out[ph] += g[ph]
    return {ph: sorted(v) for ph, v in out.items()}


def _equal_groups(years: pd.DataFrame, avail) -> dict[str, list[int]]:
    """Equal-size groups among the years `avail` (years in which the measure has data).

    n = size of the smallest phase. From the larger phases we take the "cleanest"
    years: El Niño and La Niña with the largest peak |anomaly|, Neutral with the
    smallest. That compares clear El Niño with clear La Niña and with a truly
    quiet Pacific, not with borderline years.
    """
    w = years[years.year.isin(list(avail)) & years.complete]
    n = w.phase.value_counts().reindex(C.PHASES).fillna(0).astype(int).min()
    out = {}
    for ph in C.PHASES:
        g = w[w.phase == ph].copy()
        g["key"] = g.peak.abs() if ph != C.NEUTRAL else -g.peak.abs()
        out[ph] = sorted(g.nlargest(n, "key").year.tolist())
    return out


def all_groups(years: pd.DataFrame, avail) -> dict[str, list[int]]:
    w = years[years.year.isin(list(avail)) & years.complete]
    return {ph: sorted(w[w.phase == ph].year.tolist()) for ph in C.PHASES}


def after_strong_el_nino(years: pd.DataFrame, thr: float = 1.5) -> pd.DataFrame:
    """What happened the year after a strong El Niño: analogues for the +12-month outlook."""
    y = years.set_index("year")
    rows = []
    for yr, r in y.iterrows():
        if r.phase == "El Niño" and r.peak >= thr and r.complete and (yr + 1) in y.index:
            nxt = y.loc[yr + 1]
            rows.append(dict(el_nino=r.label, peak=r.peak, next_label=nxt.label,
                             next_jas=nxt.jas, next_phase=nxt.phase,
                             next_peak=nxt.peak))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ys = enso_years()
    pd.set_option("display.width", 160)
    print(ys.tail(20).to_string(index=False))
    print(after_strong_el_nino(ys).to_string(index=False))
