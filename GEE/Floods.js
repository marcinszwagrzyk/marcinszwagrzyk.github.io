// 1. Obszar: np. Kłodzko i okolice
var region = ee.Geometry.Rectangle([16.5, 50.2, 17.5, 50.6]);

// 2. Zakres dat: powódź wrzesień 2024
var floodDate = ee.Date('2024-09-15');
var preStart = floodDate.advance(-20, 'day');
var preEnd   = floodDate.advance(-10, 'day');
var postStart = floodDate.advance(-2, 'day');
var postEnd   = floodDate.advance(4, 'day');

// 3. Sentinel-1 (średnia VV przed i po)
function getS1VV(start, end) {
  return ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(region)
    .filterDate(start, end)
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
    .select('VV')
    .mean();
}
var before = getS1VV(preStart, preEnd);
var after  = getS1VV(postStart, postEnd);

// 4. Różnica VV i maska: tylko duży spadek (1.0+)
var diff = before.subtract(after);

// 5. Maska terenu płaskiego: nachylenie < 5°
var dem = ee.Image('USGS/SRTMGL1_003');
var slope = ee.Terrain.slope(dem);
var slopeMask = slope.lt(5);

// 6. Maska zalania: tylko mocny spadek VV i na płaskim terenie
var floodMask = diff.gt(1.0)
  .updateMask(slopeMask)
  .selfMask();

// 7. Filtrowanie (usuń izolowane piksele)
var cleanMask = floodMask
  .focal_max(30, 'square', 'meters')
  .focal_min(30, 'square', 'meters');

// 8. Wektoryzacja
var floodVectors = cleanMask
  .multiply(1).rename('flood')
  .reduceToVectors({
    geometry: region,
    geometryType: 'polygon',
    scale: 50, // mniejsza rozdzielczość = szybsze i gładsze
    eightConnected: false,
    labelProperty: 'zone',
    maxPixels: 1e9
  });

// 9. Upraszczanie i odrzucenie małych plam
var floodClean = floodVectors.map(function(f) {
  var geom = f.geometry().simplify(20);
  var area = geom.area(1);
  return f.setGeometry(geom).set('area', area);
}).filter(ee.Filter.gt('area', 25000)); // tylko > 500 m²

// 10. Wizualizacja
Map.centerObject(region, 11);
Map.addLayer(diff, {min: -2, max: 2, palette: ['red', 'white', 'blue']}, 'Różnica VV');
Map.addLayer(cleanMask, {palette: ['#0000ff']}, 'Zalanie (czyszczone)');
Map.addLayer(floodClean, {color: 'red'}, 'Strefa zalania (wektor)');

// 11. Eksport wektora do GeoJSON
Export.table.toDrive({
  collection: floodClean,
  description: 'Powodz_Wrzesien2024_surowo',
  fileFormat: 'GeoJSON'
});
