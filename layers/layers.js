var wms_layers = [];


        var lyr_CartoDbPositron_0 = new ol.layer.Tile({
            'title': 'CartoDb Positron',
            'type': 'base',
            'opacity': 1.000000,
            
            
            source: new ol.source.XYZ({
    attributions: ' ',
                url: 'http://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'
            })
        });
var format_gridx_1 = new ol.format.GeoJSON();
var features_gridx_1 = format_gridx_1.readFeatures(json_gridx_1, 
            {dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857'});
var jsonSource_gridx_1 = new ol.source.Vector({
    attributions: ' ',
});
jsonSource_gridx_1.addFeatures(features_gridx_1);
var lyr_gridx_1 = new ol.layer.Vector({
                declutter: true,
                source:jsonSource_gridx_1, 
                style: style_gridx_1,
                interactive: true,
                title: '<img src="styles/legend/gridx_1.png" /> gridx'
            });
var format_PM_Pl_04_2 = new ol.format.GeoJSON();
var features_PM_Pl_04_2 = format_PM_Pl_04_2.readFeatures(json_PM_Pl_04_2, 
            {dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857'});
var jsonSource_PM_Pl_04_2 = new ol.source.Vector({
    attributions: ' ',
});
jsonSource_PM_Pl_04_2.addFeatures(features_PM_Pl_04_2);
var lyr_PM_Pl_04_2 = new ol.layer.Vector({
                declutter: true,
                source:jsonSource_PM_Pl_04_2, 
                style: style_PM_Pl_04_2,
                interactive: true,
    title: 'PM_Pl_04<br />\
    <img src="styles/legend/PM_Pl_04_2_0.png" /> 0,562 - 0,652<br />\
    <img src="styles/legend/PM_Pl_04_2_1.png" /> 0,652 - 0,683<br />\
    <img src="styles/legend/PM_Pl_04_2_2.png" /> 0,683 - 0,715<br />\
    <img src="styles/legend/PM_Pl_04_2_3.png" /> 0,715 - 0,764<br />\
    <img src="styles/legend/PM_Pl_04_2_4.png" /> 0,764 - 0,859<br />'
        });

lyr_CartoDbPositron_0.setVisible(true);lyr_gridx_1.setVisible(true);lyr_PM_Pl_04_2.setVisible(true);
var layersList = [lyr_CartoDbPositron_0,lyr_gridx_1,lyr_PM_Pl_04_2];
lyr_gridx_1.set('fieldAliases', {'fid': 'fid', 'id': 'id', 'left': 'left', 'top': 'top', 'right': 'right', 'bottom': 'bottom', 'xcoord': 'xcoord', 'ycoord': 'ycoord', 'label': 'label', });
lyr_PM_Pl_04_2.set('fieldAliases', {'pm10_1': 'pm10_1', 'pm25_1': 'pm25_1', 'lab': 'lab', });
lyr_gridx_1.set('fieldImages', {'fid': 'TextEdit', 'id': 'TextEdit', 'left': 'TextEdit', 'top': 'TextEdit', 'right': 'TextEdit', 'bottom': 'TextEdit', 'xcoord': 'TextEdit', 'ycoord': 'TextEdit', 'label': 'TextEdit', });
lyr_PM_Pl_04_2.set('fieldImages', {'pm10_1': 'TextEdit', 'pm25_1': 'TextEdit', 'lab': 'TextEdit', });
lyr_gridx_1.set('fieldLabels', {'fid': 'no label', 'id': 'no label', 'left': 'no label', 'top': 'header label', 'right': 'no label', 'bottom': 'no label', 'xcoord': 'inline label', 'ycoord': 'inline label', 'label': 'no label', });
lyr_PM_Pl_04_2.set('fieldLabels', {'pm10_1': 'no label', 'pm25_1': 'no label', 'lab': 'no label', });
lyr_PM_Pl_04_2.on('precompose', function(evt) {
    evt.context.globalCompositeOperation = 'normal';
});