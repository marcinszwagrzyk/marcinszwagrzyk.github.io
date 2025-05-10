// 1) Kraków (bufor 5 km)
var krakow = ee.Geometry.Point([19.9450, 50.0647]).buffer(5000);

// 2) Zakres czasowy: 2018–2023
var start = ee.Date('2018-01-01');
var end   = ee.Date('2024-01-01');

// 3) Sentinel‑5P – dzienne NO₂
var no2Raw = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_NO2')
  .filterDate(start, end)
  .select('NO2_column_number_density')
  .filterBounds(krakow);

// 4) ERA5 – hourly PBLH
var pblhRaw = ee.ImageCollection("ECMWF/ERA5/HOURLY")
  .filterDate(start, end)
  .select('boundary_layer_height')
  .filterBounds(krakow);

// 5) Funkcja: miesięczne uśrednianie
function monthlyMean(collection, bandName) {
  var months = ee.List.sequence(0, end.difference(start, 'month').subtract(1));
  return ee.ImageCollection.fromImages(
    months.map(function(m) {
      var mStart = start.advance(m, 'month');
      var mEnd = mStart.advance(1, 'month');
      var mean = collection.filterDate(mStart, mEnd).mean();
      var safe = ee.Algorithms.If(
        mean.bandNames().size().gt(0),
        mean.unmask(0),
        ee.Image.constant(0).rename(bandName)
      );
      return ee.Image(safe).set('system:time_start', mStart.millis());
    })
  );
}

// 6) Stałe parametry chemiczne
var molarMass = 46.0055;
var mixingHeight = 1000;

// 7) NO₂ przeliczony na µg/m³ przy założonym PBLH = 1000 m
var no2Fixed = no2Raw.map(function(img) {
  return img.multiply(molarMass * 1e6)
            .divide(mixingHeight)
            .rename('NO2_ugm3_fixed')
            .copyProperties(img, ['system:time_start']);
});
var no2MonthlyFixed = monthlyMean(no2Fixed, 'NO2_ugm3_fixed');

// 8) Miesięczne PBLH
var pblhMonthly = monthlyMean(pblhRaw, 'PBLH');

// 9) Miesięczny NO₂ (mol/m²) – surowy
var no2MonthlyRaw = monthlyMean(no2Raw, 'NO2_column_number_density');

// 10) Łączenie NO₂ + PBLH miesięcznie za pomocą ee.List.zip
var zipped = ee.List(no2MonthlyRaw.toList(no2MonthlyRaw.size()))
  .zip(pblhMonthly.toList(pblhMonthly.size()));

var no2MonthlyDynamic = ee.ImageCollection(zipped.map(function(pair) {
  var no2 = ee.Image(ee.List(pair).get(0));
  var pblh = ee.Image(ee.List(pair).get(1));

  var fallback = ee.Image.constant(500).rename('PBLH');
  var usePBLH = ee.Algorithms.If(pblh.bandNames().size().gt(0), pblh, fallback);
  pblh = ee.Image(usePBLH);

  var ugm3 = no2.multiply(molarMass * 1e6)
                .divide(pblh)
                .rename('NO2_ugm3_dyn')
                .set('system:time_start', no2.get('system:time_start'));
  return ugm3;
}));

// 11) Wykres NO₂ przy PBLH = 1000 m
var chartFixed = ui.Chart.image.series({
  imageCollection: no2MonthlyFixed,
  region: krakow,
  reducer: ee.Reducer.mean(),
  scale: 1000,
  xProperty: 'system:time_start'
}).setChartType('ColumnChart').setOptions({
  title: '1) NO₂ – miesięczne średnie (µg/m³), PBLH = 1000 m',
  vAxis: {title: 'NO₂ [µg/m³]'},
  hAxis: {title: 'Miesiąc', format: 'YYYY-MM'},
  colors: ['#d62728']
});
print(chartFixed);

// 12) Wykres PBLH
var chartPBLH = ui.Chart.image.series({
  imageCollection: pblhMonthly,
  region: krakow,
  reducer: ee.Reducer.mean(),
  scale: 1000,
  xProperty: 'system:time_start'
}).setChartType('ColumnChart').setOptions({
  title: '2) PBLH – miesięczne średnie (m)',
  vAxis: {title: 'PBLH [m]'},
  hAxis: {title: 'Miesiąc', format: 'YYYY-MM'},
  colors: ['#1f77b4']
});
print(chartPBLH);

// 13) Wykres NO₂ z dynamiczną PBLH
var chartDynamic = ui.Chart.image.series({
  imageCollection: no2MonthlyDynamic,
  region: krakow,
  reducer: ee.Reducer.mean(),
  scale: 1000,
  xProperty: 'system:time_start'
}).setChartType('ColumnChart').setOptions({
  title: '3) NO₂ – miesięczne średnie (µg/m³), z dynamiczną PBLH (ERA5)',
  vAxis: {title: 'NO₂ [µg/m³]'},
  hAxis: {title: 'Miesiąc', format: 'YYYY-MM'},
  colors: ['#2ca02c']
});
print(chartDynamic);
