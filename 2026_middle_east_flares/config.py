"""
Configuration for Middle East Gas Flares project.
Uses NASA FIRMS API (VIIRS active fire data) to build a gas flare database.

Get your free MAP_KEY at: https://firms.modaps.eosdis.nasa.gov/api/area/
"""

# NASA FIRMS API key - register at https://firms.modaps.eosdis.nasa.gov/api/area/
FIRMS_MAP_KEY = ""

# VIIRS data sources (prefer SP = Standard Processing when available, NRT = Near Real Time)
VIIRS_SOURCES = [
    "VIIRS_SNPP_SP",
    "VIIRS_NOAA20_SP",
    "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
]

# Middle East bounding box (west, south, east, north)
MIDDLE_EAST_BBOX = "34,-2,63,42"

# Country bounding boxes for targeted queries
COUNTRY_BBOX = {
    "kuwait":          "46.5,28.5,48.5,30.1",
    "iraq":            "38.8,29.0,48.6,37.4",
    "iran":            "44.0,25.0,63.3,39.8",
    "saudi_arabia":    "34.5,16.3,55.7,32.2",
    "uae":             "51.5,22.6,56.4,26.1",
    "qatar":           "50.7,24.4,51.7,26.2",
    "bahrain":         "50.3,25.7,50.8,26.3",
    "oman":            "51.8,16.6,59.8,26.4",
    "yemen":           "42.5,12.1,54.5,19.0",
    "syria":           "35.7,32.3,42.4,37.3",
    "jordan":          "34.9,29.2,39.3,33.4",
    "israel_palestine": "34.2,29.4,35.9,33.3",
    "lebanon":         "35.1,33.0,36.6,34.7",
    "turkey_se":       "36.0,36.0,45.0,42.0",
    "egypt":           "24.7,22.0,36.9,31.7",
    "libya":           "9.3,19.5,25.2,33.2",
}

# Gas flare detection parameters
FLARE_FILTERS = {
    "min_frp_mw": 0.5,            # Minimum Fire Radiative Power (MW)
    "confidence_levels": ["n", "h", "nominal", "high"],  # FIRMS uses n/h/l codes
    "night_only": True,            # VNF methodology uses nighttime only
}

# Database
GPKG_PATH = "data/middle_east_flares.gpkg"
