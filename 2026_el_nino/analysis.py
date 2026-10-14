# -*- coding: utf-8 -*-
"""ENSO phase comparison on GDACS events (+ IBTrACS as a long-history check).

    python analysis.py      # -> out/yearly.csv, out/comparison.csv, ...

Design: for every measure take the window of years in which GDACS has it
continuously, classify ENSO years (Jun–May) and compare EQUAL-SIZE groups:
n El Niño years vs n Neutral years vs n La Niña years (n = smallest phase).
On top of that, a permutation test on all years of the window (not cut to n).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

import config as C
import enso
import events

RNG = np.random.default_rng(42)
N = C.NEUTRAL
EN_VS_N, LN_VS_N, P_COL = "El Niño vs Neutral [%]", "La Niña vs Neutral [%]", "p (EN vs LN, all years)"


@dataclass
class Metric:
    section: str
    label: str
    source: str                      # "GDACS" / "IBTrACS"
    first: int                       # first ENSO year with continuous data
    fn: Callable[[pd.DataFrame], pd.Series]   # events -> value per ENSO year
    unit: str = "events / year"
    adjust: str | None = None        # None | "share" | "regime"


def _count(mask_fn):
    return lambda d: d[mask_fn(d)].groupby("enso_year").size()


def _sum(col, mask_fn):
    return lambda d: d[mask_fn(d)].groupby("enso_year")[col].sum()


def metrics() -> list[Metric]:
    M = []
    TC0, FL0 = C.GDACS_FIRST_YEAR["TC"], C.GDACS_FIRST_YEAR["FL"]
    tc = lambda d: d.type == "TC"
    fl = lambda d: d.type == "FL"

    # 1. Monsoons: floods in the countries and season of a monsoon, as % of world floods
    for name, r in C.MONSOONS.items():
        M.append(Metric("Monsoons", name, "GDACS", FL0,
                        _count(lambda d, r=r: fl(d) & events.in_region(d, r["iso3"], r["months"])),
                        "% of world floods", "share"))

    # 2-3. Hurricanes (Atlantic + East Pacific), typhoons (West Pacific), other cyclones
    for src, first in (("GDACS", TC0), ("IBTrACS", 1980)):
        base = tc if src == "GDACS" else (lambda d: d.index == d.index)
        for sec, lab, bas in (("Hurricanes", "North Atlantic", {"NA"}),
                              ("Hurricanes", "East/Central Pacific", {"EP"}),
                              ("Typhoons", "West Pacific", {"WP"}),
                              ("Cyclones", "North Indian Ocean", {"NI"}),
                              ("Cyclones", "Southern Hemisphere (Indian + Pacific)", {"SI", "SP"})):
            M.append(Metric(sec, f"{lab} — all storms", src, first,
                            _count(lambda d, b=bas, base=base: base(d) & d.basin.isin(b)),
                            "storms / season"))
            M.append(Metric("Categories (Saffir-Simpson)", f"{sec}: {lab} — cat. 3–5", src, first,
                            _count(lambda d, b=bas, base=base: base(d) & d.basin.isin(b)
                                   & d.ss_cat.isin(C.MAJOR)), "storms / season"))
            M.append(Metric("Categories (Saffir-Simpson)", f"{sec}: {lab} — cat. 4–5", src, first,
                            _count(lambda d, b=bas, base=base: base(d) & d.basin.isin(b)
                                   & d.ss_cat.isin(C.CAT45)), "storms / season"))
            if src == "IBTrACS":
                M.append(Metric(sec, f"{lab} — ACE energy", src, first,
                                _sum("ace", lambda d, b=bas: d.basin.isin(b)),
                                "ACE (10⁴ kt²)"))
        if src == "GDACS":
            M.append(Metric("Hurricanes", "Orange/red alerts (all basins)", src, first,
                            _count(lambda d: tc(d) & d.severe), "storms / season"))

    # 4. Heavy rain / floods
    M.append(Metric("Heavy rain", "World floods (normalised within catalogue)", "GDACS", FL0,
                    _count(fl), "events / year (DFO+GloFAS scale)", "regime"))
    M.append(Metric("Heavy rain", "Floods with orange/red alert", "GDACS", FL0,
                    _count(lambda d: fl(d) & d.severe), "% of world floods", "share"))
    for name, r in C.RAIN_REGIONS.items():
        M.append(Metric("Heavy rain", name, "GDACS", FL0,
                        _count(lambda d, r=r: fl(d) & events.in_region(d, r["iso3"], r["months"])),
                        "% of world floods", "share"))
    return M


# ----------------------------------------------------------------- statistics
def perm_p(a, b, n=20000):
    """Two-sided permutation test of the difference in means."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2:
        return np.nan
    obs = abs(a.mean() - b.mean())
    pool = np.concatenate([a, b])
    cnt = 0
    for _ in range(n):
        RNG.shuffle(pool)
        cnt += abs(pool[:len(a)].mean() - pool[len(a):].mean()) >= obs - 1e-12
    return (cnt + 1) / (n + 1)


def yearly(ev_gdacs, ev_ib, last) -> tuple[pd.DataFrame, list[Metric]]:
    """Table: ENSO year x measure (after the share/regime adjustment)."""
    ms = metrics()
    years = range(min(m.first for m in ms), last + 1)
    fl_total = ev_gdacs[ev_gdacs.type == "FL"].groupby("enso_year").size().reindex(years)
    cols = {}
    for m in ms:
        d = ev_gdacs if m.source == "GDACS" else ev_ib
        s = m.fn(d).reindex(range(m.first, last + 1)).fillna(0).astype(float)
        if m.adjust == "share":
            s = 100 * s / fl_total.reindex(s.index)
        elif m.adjust == "regime":
            # value / mean of its catalogue * overall mean: GloFAS sees ~4x more
            # floods than DFO, so raw counts would measure the catalogue
            parts = []
            for a, b in C.FL_REGIMES:
                r = s[(s.index >= a) & (s.index <= b)]
                parts.append(r / r.mean())
            s = pd.concat(parts).reindex(s.index) * s[~s.index.isin(C.FL_EXCLUDE)].mean()
        if m.adjust in ("share", "regime"):
            s[s.index.isin(C.FL_EXCLUDE)] = np.nan
        cols[(m.section, m.label, m.source)] = s
    return pd.DataFrame(cols), ms


def _label(y):
    return f"{y}/{str(y + 1)[2:]}"


def compare(tab, ms, years) -> pd.DataFrame:
    rows = []
    for m in ms:
        s = tab[(m.section, m.label, m.source)].dropna()
        last = int(s.index.max())
        flood = m.adjust in ("share", "regime")
        eq = enso.equal_groups(years, s.index, C.FL_REGIMES if flood else None)
        al = enso.all_groups(years, s.index)
        mean = {ph: s.reindex(eq[ph]).mean() for ph in C.PHASES}
        ref = mean[N]
        rows.append({
            "section": m.section, "measure": m.label, "source": m.source, "unit": m.unit,
            "period": f"{_label(m.first)}–{_label(last)}" + (" excl. 2016–18" if flood else ""),
            "n per phase": len(eq["El Niño"]),
            **{f"years {ph}": " ".join(_label(y) for y in eq[ph]) for ph in C.PHASES},
            **{ph: mean[ph] for ph in C.PHASES},
            EN_VS_N: 100 * (mean["El Niño"] / ref - 1) if ref else np.nan,
            LN_VS_N: 100 * (mean["La Niña"] / ref - 1) if ref else np.nan,
            P_COL: perm_p(s.reindex(al["El Niño"]), s.reindex(al["La Niña"])),
            "all years EN/N/LN": "/".join(str(len(al[ph])) for ph in C.PHASES),
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------- droughts: by month
DROUGHT_LAG = 3   # drought builds up after the rainfall deficit: ENSO phase 3 months earlier


def drought_months(g: pd.DataFrame) -> pd.DataFrame:
    """Month x measure: number of droughts ACTIVE in that month (globally and by region).

    GDACS has droughts only since 2018: 8 ENSO years, one of them neutral, so a
    year-by-year comparison would have n = 1. There are ~99 months, and a drought
    is a state lasting months anyway, so the month is the natural unit.
    """
    dr = g[g.type == "DR"]
    months = pd.period_range("2018-06", pd.Timestamp.today().to_period("M") - 1, freq="M")
    sel = {"Active droughts worldwide": lambda d: d.index == d.index,
           "Active droughts with orange/red alert": lambda d: d.severe}
    for name, iso in C.DROUGHT_REGIONS.items():
        sel[name] = lambda d, iso=iso: events.in_region(d, iso)
    out = {}
    for name, f in sel.items():
        d = dr[f(dr)]
        sp, ep = d.start.dt.to_period("M"), d.end.dt.to_period("M")
        out[name] = [int(((sp <= m) & (ep >= m)).sum()) for m in months]
    tab = pd.DataFrame(out, index=months)
    idx = enso.season_phases(enso.read_index("roni"))
    ph = pd.Series(idx.phase.values, index=idx.date.dt.to_period("M"))
    an = pd.Series(idx.anom.values, index=idx.date.dt.to_period("M"))
    tab.insert(0, "phase", ph.reindex(months - DROUGHT_LAG).values)
    tab.insert(1, "anom", an.reindex(months - DROUGHT_LAG).values)
    tab.index.name = "month"
    return tab.dropna(subset=["phase"])


def drought_month_groups(tab: pd.DataFrame) -> dict[str, pd.Index]:
    """Equal-size groups of months, the same "cleanest first" rule as for years."""
    n = tab.phase.value_counts().reindex(C.PHASES).min()
    out = {}
    for ph in C.PHASES:
        t = tab[tab.phase == ph]
        key = t.anom.abs() if ph != N else -t.anom.abs()
        out[ph] = key.nlargest(n).index
    return out


def compare_drought(tab: pd.DataFrame) -> pd.DataFrame:
    grp = drought_month_groups(tab)
    n = len(grp["El Niño"])
    rows = []
    for col in tab.columns[2:]:
        mean = {ph: tab.loc[grp[ph], col].mean() for ph in C.PHASES}
        ref = mean[N]
        rows.append({
            "section": "Droughts", "measure": col, "source": "GDACS",
            "unit": "active droughts / month",
            "period": f"{tab.index.min()}–{tab.index.max()} (months, ENSO phase −{DROUGHT_LAG} mo.)",
            "n per phase": n,
            **{f"years {ph}": f"{n} months" for ph in C.PHASES},
            **mean,
            EN_VS_N: 100 * (mean["El Niño"] / ref - 1) if ref else np.nan,
            LN_VS_N: 100 * (mean["La Niña"] / ref - 1) if ref else np.nan,
            # months are strongly autocorrelated: a test assuming independence would be falsely confident
            P_COL: np.nan,
            "all years EN/N/LN": "/".join(str((tab.phase == ph).sum()) for ph in C.PHASES) + " months",
        })
    return pd.DataFrame(rows)


def run():
    years = enso.enso_years()
    last = int(years[years.complete].year.max())
    g = events.gdacs()
    ib = events.ibtracs()
    tab, ms = yearly(g, ib, last)
    dm = drought_months(g)
    cmp_ = pd.concat([compare(tab, ms, years), compare_drought(dm)], ignore_index=True)

    years.to_csv(C.OUT / "enso_years.csv", index=False)
    dm.to_csv(C.OUT / "droughts_monthly.csv")
    flat = tab.copy()
    flat.columns = [f"{s} | {l} | {src}" for s, l, src in tab.columns]
    flat.insert(0, "phase", years.set_index("year").phase.reindex(flat.index))
    flat.index.name = "enso_year"
    flat.to_csv(C.OUT / "yearly.csv", float_format="%.3f")
    cmp_.to_csv(C.OUT / "comparison.csv", index=False, float_format="%.3f")
    g.drop(columns=["iso_set"]).to_csv(C.OUT / "gdacs_events.csv", index=False)
    ib.to_csv(C.OUT / "ibtracs_storms.csv", index=False, float_format="%.2f")
    return years, g, ib, tab, cmp_, dm


if __name__ == "__main__":
    years, g, ib, tab, cmp_, dm = run()
    pd.set_option("display.width", 220, "display.max_colwidth", 60, "display.max_rows", 200)
    print(cmp_[["section", "measure", "source", "period", "n per phase", *C.PHASES,
                EN_VS_N, P_COL]].round(2).to_string(index=False))
