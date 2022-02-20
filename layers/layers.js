var wms_layers = [];


        var lyr_OpenStreetMap_0 = new ol.layer.Tile({
            'title': 'OpenStreetMap',
            'type': 'base',
            'opacity': 1.000000,
            
            
            source: new ol.source.XYZ({
    attributions: ' ',
                url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
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

lyr_OpenStreetMap_0.setVisible(true);lyr_szczyty_1.setVisible(true);
var layersList = [lyr_OpenStreetMap_0,lyr_szczyty_1];
lyr_szczyty_1.set('fieldAliases', {'fid': 'fid', 'nazwa': 'nazwa', });
lyr_szczyty_1.set('fieldImages', {'fid': 'TextEdit', 'nazwa': 'TextEdit', });
lyr_szczyty_1.set('fieldLabels', {'fid': 'no label', 'nazwa': 'no label', });
lyr_szczyty_1.on('precompose', function(evt) {
    evt.context.globalCompositeOperation = 'normal';
});