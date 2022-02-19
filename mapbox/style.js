
var styleJSON = {
    "version": 8,
    "name": "qgis2web export",
    "pitch": 0,
    "light": {
        "intensity": 0.2
    },
    "sources": {
        "OpenTopoMap_0": {
            "type": "raster",
            "tiles": ["https://tile.opentopomap.org/{z}/{x}/{y}.png"],
            "tileSize": 256
        },
        "szczyty_1": {
            "type": "geojson",
            "data": json_szczyty_1
        }
                    },
    "sprite": "",
    "glyphs": "https://glfonts.lukasmartinelli.ch/fonts/{fontstack}/{range}.pbf",
    "layers": [
        {
            "id": "background",
            "type": "background",
            "layout": {},
            "paint": {
                "background-color": "#ffffff"
            }
        },
        {
            "id": "lyr_OpenTopoMap_0_0",
            "type": "raster",
            "source": "OpenTopoMap_0"
        },
        {
            "id": "lyr_szczyty_1_0",
            "type": "circle",
            "source": "szczyty_1",
            "layout": {},
            "paint": {'circle-radius': ['/', 7.142857142857142, 2], 'circle-color': '#c43c39', 'circle-opacity': 1.0, 'circle-stroke-width': 1, 'circle-stroke-color': '#232323'}
        }
,
        {
            "id": "lyr_szczyty_1_1",
            "type": "symbol",
            "source": "szczyty_1",
            "layout": {'text-offset': [0.0, 0.0], 'text-field': ['get', 'nazwa'], 'text-size': '12.607142857142854', 'text-font': ['Open Sans Regular']},
            "paint": {'text-color': '#323232'}
        }
],
}