// 1) Kraków (z buforem 5 km)
var krakow = ee.Geometry.Point([19.9450, 50.0647]).buffer(5000);

// 2) Zakres czasowy: cały 2023
var start = ee.Date('2023-01-01');
var end   = ee.Date('2024-01-01');

// 3) Sentinel‑5P – dzienne NO₂
var no2Daily = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_NO2')
  .select('NO2_column_number_density')
  .filterDate(start, end);

// 4) ERA5 – hourly PBLH
var pblhHourly = ee.ImageCollection("ECMWF/ERA5/HOURLY")
  .filterDate(start, end)
  .select('boundary_layer_height');

// 5) Funkcja: miesięczne uśrednianie z fallbackiem
function monthlyAverage(collection, bandName) {
  var months = ee.List.sequence(0, end.difference(start, 'month').subtract(1));
  return ee.ImageCollection.fromImages(months.map(function(m) {
    var mStart = start.advance(m, 'month');
    var mEnd = mStart.advance(1, 'month');
    var mean = collection.filterDate(mStart, mEnd).mean();
    var safe = ee.Algorithms.If(
      mean.bandNames().size().gt(0),
      mean.unmask(0),
      ee.Image.constant(0).rename(bandName)
    );
    return ee.Image(safe).rename(bandName).set('system:time_start', mStart.millis());
  }));
}

// ========== 1) NO₂ z PBLH = 1000 m ==========

var molarMass = 46.0055; // g/mol
var mixingHeight = 1000; // m

var no2Fixed = no2Daily.map(function(img) {
  return img.multiply(molarMass * 1e6)
            .divide(mixingHeight)
            .rename('NO2_ugm3_fixed')
            .set('system:time_start', img.date().millis());
});
var no2MonthlyFixed = monthlyAverage(no2Fixed, 'NO2_ugm3_fixed');

var chartNO2fixed = ui.Chart.image.series({
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
print(chartNO2fixed);

// ========== 2) PBLH z ERA5 ==========

var pblhDaily = ee.ImageCollection(
  ee.List.sequence(0, end.difference(start, 'day').subtract(1)).map(function(d) {
    var dStart = start.advance(d, 'day');
    var dEnd = dStart.advance(1, 'day');
    var mean = pblhHourly.filterDate(dStart, dEnd).mean();
    return ee.Image(mean).set('system:time_start', dStart.millis());
  })
);
var pblhMonthly = monthlyAverage(pblhDaily, 'PBLH');

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

// ========== 3) NO₂ z dynamiczną PBLH ==========

var no2WithDynamic = ee.ImageCollection(
  no2Daily.map(function(img) {
    var date = img.date();
    var pblhImg = pblhDaily.filterDate(date, date.advance(1, 'day')).first();

    var fallback = ee.Image.constant(500).rename('boundary_layer_height');
    var pblh = ee.Algorithms.If(pblhImg, ee.Image(pblhImg), fallback);
    pblh = ee.Image(pblh);

    var conc = img.multiply(molarMass * 1e6)
                  .divide(pblh)
                  .rename('NO2_ugm3_dyn')
                  .set('system:time_start', img.date().millis());
    return conc;
  })
);
var no2MonthlyDynamic = monthlyAverage(no2WithDynamic, 'NO2_ugm3_dyn');

var chartNO2dyn = ui.Chart.image.series({
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
print(chartNO2dyn);
