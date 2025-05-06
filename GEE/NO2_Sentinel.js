// 1) Definicja miast (Europa + Azja)
var cities = ee.FeatureCollection([
  // Europa    // Indie
  ee.Feature(ee.Geometry.Point([74.3436, 31.5497]), {name: 'Lahore'})         // Pakistan
]);

// 2) Zakres czasowy
var startDate = ee.Date('2020-01-01');
var endDate   = ee.Date(Date.now());

// 3) Pobranie NO₂ z Sentinel‑5P
var no2Daily = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_NO2')
  .select('NO2_column_number_density')
  .filterDate(startDate, endDate);

// 4) Funkcja tworząca kolekcję miesięcznych średnich
function monthlyMean(collection) {
  var nMonths = endDate.difference(startDate, 'month').round();
  var months = ee.List.sequence(0, nMonths.subtract(1));
  var images = months.map(function(m) {
    var mStart = startDate.advance(ee.Number(m), 'month');
    var mEnd   = mStart.advance(1, 'month');
    return collection
      .filterDate(mStart, mEnd)
      .mean()
      .set('system:time_start', mStart.millis());
  });
  return ee.ImageCollection.fromImages(images);
}

// 5) Obliczenie miesięcznych średnich NO₂ (mol/m²)
var no2Monthly = monthlyMean(no2Daily);

// 6) Parametry konwersji
var mixingHeight = 1000;       // wysokość warstwy mieszania [m]
var molarMass    = 46.0055;    // masa molowa NO₂ [g/mol]

// 7) Konwersja kolumny (mol/m²) → µg/m³
var no2Monthly_ugm3 = no2Monthly.map(function(img) {
  var col = img.select('NO2_column_number_density');
  var conc = col
    .multiply(molarMass * 1e6)   // mol/m² → µg/m²
    .divide(mixingHeight)        // µg/m³
    .rename('NO2_ugm3');
  return conc.copyProperties(img, ['system:time_start']);
});

// 8) Rysowanie wykresu miesięcznych średnich NO₂ w µg/m³
var chart = ui.Chart.image.seriesByRegion({
  imageCollection: no2Monthly_ugm3,
  regions: cities,
  reducer: ee.Reducer.mean(),
  band: 'NO2_ugm3',
  scale: 1000,
  xProperty: 'system:time_start'
})
.setOptions({
  title: 'NO₂ – średnie miesięczne (µg/m³) od 2020-01 do dziś',
  vAxis: {title: 'NO₂ [µg/m³]'},
  hAxis: {format: 'YYYY-MM', title: 'Miesiąc'},
  lineWidth: 2,
  pointSize: 4,
  series: {

    7: {color: 'magenta'} // Lahore
  }
});
print(chart);
