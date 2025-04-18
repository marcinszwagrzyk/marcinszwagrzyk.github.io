// Define the date range for the ImageCollection
var startDate = '2024-01-01';
var endDate = '2024-12-31';

// Define the points of interest
var points = {
  'Laka': ee.Geometry.Point([-112.213216, 40.720848]),
  'Parking': ee.Geometry.Point([-112.215923, 40.722166]),
  'Smelter 1A': ee.Geometry.Point([-112.20487, 40.721762]),
  'Smelter 1B': ee.Geometry.Point([-112.2051097, 40.721769])
};

// Create a MultiPoint geometry for filtering
var multiPoint = ee.Geometry.MultiPoint([
  [-112.213216, 40.720848],
  [-112.215923, 40.722166],
  [-112.205461, 40.721979]
]);

// Load the Sentinel-2 ImageCollection
var sentinel2 = ee.ImageCollection('COPERNICUS/S2')
  .filterDate(startDate, endDate)
  .filterBounds(multiPoint)
  .map(function(image) {
    // Select and rename the SWIR bands
    return image.addBands(image.select('B11').rename('SWIR1'))
                .addBands(image.select('B12').rename('SWIR2'));
  });

// Function to extract average SWIR values for each point and convert to features
var getSWIRFeature = function(image, point, label) {
  var swir1Mean = ee.Number(image.select('SWIR1').reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: point,
    scale: 20  // Scale adjusted for Sentinel-2 resolution
  }).get('SWIR1')).float();

  var swir2Mean = ee.Number(image.select('SWIR2').reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: point,
    scale: 20  // Scale adjusted for Sentinel-2 resolution
  }).get('SWIR2')).float();

  return ee.Feature(null, {
    'date': ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'),
    'SWIR1': swir1Mean,
    'SWIR2': swir2Mean,
    'label': label
  });
};

// Extract SWIR time series for all points
var swirSeries = ee.FeatureCollection([]);

Object.keys(points).forEach(function(label) {
  var point = points[label];
  var series = sentinel2.map(function(image) {
    return getSWIRFeature(image, point, label);
  }).filter(ee.Filter.notNull(['SWIR1', 'SWIR2']));
 
  swirSeries = swirSeries.merge(series);
});

// Create and display the chart for SWIR
var swirChart = ui.Chart.feature.groups(swirSeries, 'date', 'SWIR1', 'label')
  .setChartType('LineChart')
  .setOptions({
    title: 'SWIR1 Time Series (2024)',
    vAxis: {title: 'Reflectance'},
    hAxis: {title: 'Date'},
    lineWidth: 2,
    pointSize: 3,
    series: {
      0: {color: '00FF00'}, // Laka
      1: {color: 'FFFF00'}, // Parking
      2: {color: 'FF00FF'}  // Smelter 1B
    }
  });

print(swirChart);

var swirChart2 = ui.Chart.feature.groups(swirSeries, 'date', 'SWIR2', 'label')
  .setChartType('LineChart')
  .setOptions({
    title: 'SWIR2 Time Series (2024)',
    vAxis: {title: 'Reflectance'},
    hAxis: {title: 'Date'},
    lineWidth: 2,
    pointSize: 3,
    series: {
      0: {color: '00FF00'}, // Laka
      1: {color: 'FFFF00'}, // Parking
      2: {color: 'FF00FF'}  // Smelter 1B
    }
  });

print(swirChart2);

// Add layers to the map for visual reference
Map.addLayer(points['Laka'], {color: 'green'}, 'Laka');
Map.addLayer(points['Parking'], {color: 'yellow'}, 'Parking');
Map.addLayer(points['Smelter 1B'], {color: 'magenta'}, 'Smelter 1B');
Map.setCenter(-112.204656, 40.721983, 13);
