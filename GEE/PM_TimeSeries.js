// 1) Definicja punktów: Kraków, Warszawa, Gdańsk
var cities = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Point([19.9450, 50.0647]), {name: 'Krakow'}),
  ee.Feature(ee.Geometry.Point([21.0122, 52.2297]), {name: 'Warszawa'}),
  ee.Feature(ee.Geometry.Point([18.6466, 54.3520]), {name: 'Gdansk'})
]);

// 2) Zakres zimowy: 1 grudnia 2023 – 1 marca 2024
var start = ee.Date('2023-12-01');
var end   = ee.Date('2024-05-01');

// 3) Wczytanie reanalizy GEOS‑CF – PM₂.₅ o 00:00 UTC
var pm25Daily = ee.ImageCollection('NASA/GEOS-CF/v1/rpl/htf')
  .filterDate(start, end)
  .filter(ee.Filter.calendarRange(0, 0, 'hour'))
  .select('PM25_RH35_GCC');

// 4) Funkcja tworząca uśrednione tygodniowe obrazy (rolling co 7 dni)
function weeklyMean(collection) {
  var weeks = ee.List.sequence(0, end.difference(start, 'week').subtract(1));
  return ee.ImageCollection.fromImages(
    weeks.map(function(w) {
      var wStart = start.advance(w, 'week');
      var wEnd = wStart.advance(1, 'week');
      return collection
        .filterDate(wStart, wEnd)
        .mean()
        .set('system:time_start', wStart.millis());
    })
  );
}

// 5) Oblicz średnie tygodniowe
var pm25Weekly = weeklyMean(pm25Daily);

// 6) Rysowanie wykresu: tygodniowe PM₂.₅ dla wybranych miast
var chart = ui.Chart.image.seriesByRegion({
  imageCollection: pm25Weekly,
  regions: cities,
  reducer: ee.Reducer.mean(),
  band: 'PM25_RH35_GCC',
  scale: 1000,
  xProperty: 'system:time_start'
}).setOptions({
  title: 'PM₂.₅ – tygodniowe średnie (µg/m³) [zima 2023/24]',
  vAxis: {title: 'PM₂.₅ [µg/m³]'},
  hAxis: {format: 'YYYY-MM-dd', title: 'Tydzień'},
  lineWidth: 2,
  pointSize: 4
});

print(chart);
