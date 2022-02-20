var wms_layers = [];


        var lyr_OpenTopoMap_0 = new ol.layer.Tile({
            'title': 'OpenTopoMap',
            'type': 'base',
            'opacity': 1.000000,
            
            
            source: new ol.source.XYZ({
    attributions: ' ',
                url: 'https://tile.opentopomap.org/{z}/{x}/{y}.png'
            })
        });
var format_szczyty_1 = new ol.format.GeoJSON();
var features_szczyty_1 = format_szczyty_1.readFeatures(json_szczyty_1, 
            {dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857'});
var jsonSource_szczyty_1 = new ol.source.Vector({
    attributions: ' ',
});
jsonSource_szczyty_1.addFeatures(features_szczyty_1);
var lyr_szczyty_1 = new ol.layer.Vector({
                declutter: true,
                source:jsonSource_szczyty_1, 
                style: style_szczyty_1,
                interactive: true,
                title: '<img src="styles/legend/szczyty_1.png" /> szczyty'
            });
var format_trasy_szczyty_2 = new ol.format.GeoJSON();
var features_trasy_szczyty_2 = format_trasy_szczyty_2.readFeatures(json_trasy_szczyty_2, 
            {dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857'});
var jsonSource_trasy_szczyty_2 = new ol.source.Vector({
    attributions: ' ',
});
jsonSource_trasy_szczyty_2.addFeatures(features_trasy_szczyty_2);
var lyr_trasy_szczyty_2 = new ol.layer.Vector({
                declutter: true,
                source:jsonSource_trasy_szczyty_2, 
                style: style_trasy_szczyty_2,
                interactive: false,
                title: '<img src="styles/legend/trasy_szczyty_2.png" /> trasy_szczyty'
            });

lyr_OpenTopoMap_0.setVisible(true);lyr_szczyty_1.setVisible(true);lyr_trasy_szczyty_2.setVisible(true);
var layersList = [lyr_OpenTopoMap_0,lyr_szczyty_1,lyr_trasy_szczyty_2];
lyr_szczyty_1.set('fieldAliases', {'fid': 'fid', 'nazwa': 'nazwa', });
lyr_trasy_szczyty_2.set('fieldAliases', {'fid': 'fid', 'name': 'name', 'typ': 'typ', });
lyr_szczyty_1.set('fieldImages', {'fid': 'TextEdit', 'nazwa': 'TextEdit', });
lyr_trasy_szczyty_2.set('fieldImages', {'fid': 'TextEdit', 'name': 'TextEdit', 'typ': 'TextEdit', });
lyr_szczyty_1.set('fieldLabels', {'fid': 'header label', 'nazwa': 'no label', });
lyr_trasy_szczyty_2.set('fieldLabels', {'fid': 'no label', 'name': 'no label', 'typ': 'no label', });
lyr_trasy_szczyty_2.on('precompose', function(evt) {
    evt.context.globalCompositeOperation = 'normal';
});