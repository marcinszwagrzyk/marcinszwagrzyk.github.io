# -*- coding: utf-8 -*-
"""Paths, sources and definitions: the single place every script reads from."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"          # raw downloads (cache, not in git)
OUT = ROOT / "out"            # results: csv + png
for _d in (DATA, OUT):
    _d.mkdir(exist_ok=True)

# -------------------------------------------------------------------- sources
RONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
IBTRACS_URL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-"
               "for-climate-stewardship-ibtracs/v04r01/access/csv/"
               "ibtracs.since1980.list.v04r01.csv")
GPCP_URL = "https://downloads.psl.noaa.gov/Datasets/gpcp/precip.mon.mean.nc"
GHCN_URL = "https://downloads.psl.noaa.gov/Datasets/ghcncams/air.mon.mean.nc"
NE_URL = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"

# ------------------------------------------------------------------ ENSO year
# ENSO year = June of year Y .. May of year Y+1, labelled "Y/Y+1".
# Why not the calendar year: El Niño develops in April-June and peaks in
# November-January. A June-May window holds the whole Northern Hemisphere
# hurricane/typhoon season (Jun-Nov), the Indian monsoon (Jun-Sep), the ENSO
# peak (Dec-Feb) and the Southern Hemisphere cyclone season (Nov-Apr).
# A calendar year would cut every ENSO event in half.
ENSO_YEAR_START_MONTH = 6
ENSO_THRESHOLD = 0.5          # CPC threshold for RONI/ONI
ENSO_MIN_RUN = 5              # >= 5 consecutive overlapping seasons = episode

# First full ENSO year from which GDACS has each event type continuously
# (checked in the data: TC sporadic in 2008-10, continuous from Jul 2011, so
# the first FULL Jun-May year is 2012/13; DR from mid-2018; FL from 2000).
GDACS_TYPES = ("TC", "FL", "DR")
GDACS_FIRST_YEAR = {"TC": 2012, "FL": 2000, "DR": 2018}
GDACS_DOWNLOAD_FROM = 2000

# GDACS floods are three different catalogues: DFO (2000-2015), JRC (2016-2018,
# fragmentary: 2018/19 has only 33 events) and GloFAS (from 2019, ~4x more
# events). Transition years are dropped, counts are normalised per catalogue
# and every phase gets the same number of years from each catalogue.
FL_REGIMES = [(2000, 2015), (2019, 2100)]
FL_EXCLUDE = {2016, 2017, 2018}

# ------------------------------------------------------------ cyclone basins
BASIN_NAMES = {
    "NA": "North Atlantic",
    "EP": "East/Central Pacific",
    "WP": "West Pacific",
    "NI": "North Indian Ocean",
    "SI": "South Indian Ocean / W Australia",
    "SP": "South Pacific / E Australia",
}
# What the same physical storm is called in each basin
BASIN_GROUP = {
    "NA": "hurricanes", "EP": "hurricanes",
    "WP": "typhoons",
    "NI": "cyclones", "SI": "cyclones", "SP": "cyclones",
}

# Saffir-Simpson scale by maximum wind (km/h, 1-minute sustained)
SS_BINS = [0, 119, 154, 178, 209, 252, 1e9]
SS_LABELS = ["tropical storm", "cat. 1", "cat. 2", "cat. 3", "cat. 4", "cat. 5"]
MAJOR = ["cat. 3", "cat. 4", "cat. 5"]
CAT45 = ["cat. 4", "cat. 5"]

# ----------------------------------------- flood / drought regions (ISO3)
# Monsoons: floods in the countries of a given monsoon system, in ITS season.
MONSOONS = {
    "Indian monsoon (Jun–Sep)": dict(
        iso3={"IND", "PAK", "BGD", "NPL", "LKA", "BTN"}, months={6, 7, 8, 9}),
    "East Asian monsoon (Jun–Sep)": dict(
        iso3={"CHN", "JPN", "KOR", "PRK", "TWN", "VNM", "THA", "LAO", "KHM",
              "MMR", "PHL"}, months={6, 7, 8, 9}),
    "West African monsoon (Jul–Sep)": dict(
        iso3={"NGA", "NER", "MLI", "BFA", "TCD", "SDN", "SSD", "SEN", "GHA",
              "CMR", "GIN", "GMB", "MRT", "BEN", "TGO", "CIV", "SLE", "LBR"},
        months={7, 8, 9}),
    "Australian-Indonesian monsoon (Dec–Mar)": dict(
        iso3={"IDN", "AUS", "TLS", "PNG", "MYS"}, months={12, 1, 2, 3}),
}

# Heavy rain / floods where El Niño has a known, strong signal
RAIN_REGIONS = {
    "Peru and Ecuador": dict(iso3={"PER", "ECU"}, months=None),
    "East Africa (short rains Oct–Dec)": dict(
        iso3={"KEN", "SOM", "ETH", "TZA", "UGA", "RWA", "BDI"},
        months={10, 11, 12}),
    "SE South America": dict(iso3={"URY", "PRY", "ARG", "BRA"}, months=None),
    "Southern US and Mexico (Nov–Mar)": dict(iso3={"USA", "MEX"}, months={11, 12, 1, 2, 3}),
}

DROUGHT_REGIONS = {
    "Southern Africa": {"ZAF", "ZWE", "ZMB", "MWI", "MOZ", "BWA", "NAM", "LSO",
                        "SWZ", "MDG", "AGO"},
    "Australia, Indonesia, W Pacific": {"AUS", "IDN", "PNG", "TLS", "PHL",
                                        "MYS", "FJI", "SLB", "VUT"},
    "Central America and Caribbean": {"GTM", "HND", "SLV", "NIC", "CRI", "PAN",
                                      "MEX", "CUB", "HTI", "DOM", "JAM"},
    "South America (Amazon, NE Brazil)": {"BRA", "COL", "VEN", "GUY", "SUR",
                                          "BOL", "PER", "ECU"},
    "South Asia": {"IND", "PAK", "BGD", "NPL", "LKA"},
}

# -------------------------------------------------------------------- styling
NEUTRAL = "Neutral"
PHASES = ["El Niño", NEUTRAL, "La Niña"]
PHASE_COLORS = {"El Niño": "#e34948", NEUTRAL: "#8c8b85", "La Niña": "#2a78d6"}
INK = "#0b0b0b"; INK2 = "#52514e"; GRID = "#e4e3df"; SURFACE = "#fcfcfb"
MORE = "#c8312f"   # hex maps: more events than the benchmark
LESS = "#1d8a4a"   # hex maps: fewer events than the benchmark
