// 1) Definicja regionu: przybliżona Polska
var region = ee.Geometry.Rectangle([14.0, 49.0, 24.0, 55.0]);

// 2) Zakres zimowy: 1 grudnia 2023 – 1 marca 2024
var start = ee.Date('2023-12-01');
var end   = ee.Date('2024-03-01');

// 3) Wczytanie reanalizy GEOS‑CF – PM₂.₅ o 00:00 UTC (jedno ujęcie/dzień)
var pm25Winter = ee.ImageCollection('NASA/GEOS-CF/v1/rpl/htf')
  .filterDate(start, end)
  .filter(ee.Filter.calendarRange(0, 0, 'hour'))
  .select('PM25_RH35_GCC');

// 4) Obliczenie zimowej średniej i przycięcie do regionu
var pm25WinterMean = pm25Winter
  .mean()
  .clip(region);

// 5) Obliczenie progów kwantylowych (20%, 40%, 60%, 80%)
var quantiles = pm25WinterMean.reduceRegion({
  reducer: ee.Reducer.percentile([20, 40, 60, 80]),
  geometry: region,
  scale: 1000,
  maxPixels: 1e9
});
var q20 = ee.Number(quantiles.get('PM25_RH35_GCC_p20'));
var q40 = ee.Number(quantiles.get('PM25_RH35_GCC_p40'));
var q60 = ee.Number(quantiles.get('PM25_RH35_GCC_p60'));
var q80 = ee.Number(quantiles.get('PM25_RH35_GCC_p80'));

// 6) Klasyfikacja wartości do pięciu klas 0–4 wg progów
var pm25Class = pm25WinterMean.expression(
  "b('PM25_RH35_GCC') < q20    ? 0" +
  ": b('PM25_RH35_GCC') < q40  ? 1" +
  ": b('PM25_RH35_GCC') < q60  ? 2" +
  ": b('PM25_RH35_GCC') < q80  ? 3" +
  ": 4",
  { q20: q20, q40: q40, q60: q60, q80: q80 }
);

// 7) Paleta kolorów dla klas kwantylowych
var palette = ['blue', 'green', 'yellow', 'orange', 'red'];

// 8) Wyświetlenie na mapie
Map.setCenter(19.0, 52.0, 5);
Map.addLayer(
  pm25Class,
  { min: 0, max: 4, palette: palette },
  'PM₂.₅ – klasy kwantylowe (zima 2023/24)'
);
