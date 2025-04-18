// Zdefiniuj granice Florydy
var florida = ee.FeatureCollection('TIGER/2018/States')
  .filter(ee.Filter.eq('NAME', 'Florida'));

// Określ zakres dat (np. październik 2022)
var startDate = '2022-10-01';
var endDate = '2022-10-31';

// Załaduj kolekcję Sentinel-1 GRD
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .filter(ee.Filter.eq('resolution_meters', 10))
  .filterBounds(florida)
  .filterDate(startDate, endDate);

// Funkcja konwersji do skali dB
var toDb = function(image) {
  var db = ee.Image(10).multiply(image.log10()).rename(['VV_db', 'VH_db']);
  return image.addBands(db);
};

// Dodaj warstwy dB do obrazów
var s1 = s1.map(toDb);

// Automatyczna detekcja wody metodą Otsu (dla kompozytu medianowego)
var composite = s1.select('VV_db').median();
var otsuThreshold = composite.reduceRegion({
  reducer: ee.Reducer.otsu(),
  geometry: florida.geometry(),
  scale: 10,
  maxPixels: 1e13
}).get('VV_db');

var waterMask = composite.lt(otsuThreshold);

// Maksymalny zasięg wody w październiku
var maxWater = s1.select('VV_db').max().lt(otsuThreshold);

// Stałe zbiorniki wodne z bazy JRC
var jrc = ee.Image('JRC/GSW1_3/GlobalSurfaceWater');
var permanentWater = jrc.select('occurrence').gt(90);

// Oblicz strefę zalewową
var floodExtent = maxWater.subtract(permanentWater).clamp(0, 1);

// Wizualizacja
Map.centerObject(florida, 7);
Map.addLayer(floodExtent.selfMask(), {palette: 'red'}, 'Strefa zalewowa');
Map.addLayer(permanentWater.selfMask(), {palette: 'blue'}, 'Stałe zbiorniki');

// Eksport wyniku
Export.image.toDrive({
  image: floodExtent,
  description: 'Floryda_Zalew_2022-10',
  scale: 10,
  region: florida.geometry(),
  maxPixels: 1e13
});