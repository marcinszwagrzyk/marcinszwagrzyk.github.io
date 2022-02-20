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
var format_Mesoregions2018_2 = new ol.format.GeoJSON();
var features_Mesoregions2018_2 = format_Mesoregions2018_2.readFeatures(json_Mesoregions2018_2, 
            {dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857'});
var jsonSource_Mesoregions2018_2 = new ol.source.Vector({
    attributions: ' ',
});
jsonSource_Mesoregions2018_2.addFeatures(features_Mesoregions2018_2);
var lyr_Mesoregions2018_2 = new ol.layer.Vector({
                declutter: true,
                source:jsonSource_Mesoregions2018_2, 
                style: style_Mesoregions2018_2,
                interactive: true,
                title: '<img src="styles/legend/Mesoregions2018_2.png" /> Mesoregions2018'
            });
var format_trasy_szczyty_3 = new ol.format.GeoJSON();
var features_trasy_szczyty_3 = format_trasy_szczyty_3.readFeatures(json_trasy_szczyty_3, 
            {dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857'});
var jsonSource_trasy_szczyty_3 = new ol.source.Vector({
    attributions: ' ',
});
jsonSource_trasy_szczyty_3.addFeatures(features_trasy_szczyty_3);
var lyr_trasy_szczyty_3 = new ol.layer.Vector({
                declutter: true,
                source:jsonSource_trasy_szczyty_3, 
                style: style_trasy_szczyty_3,
                interactive: true,
                title: '<img src="styles/legend/trasy_szczyty_3.png" /> trasy_szczyty'
            });
var format_activity_8322609317tracks_4 = new ol.format.GeoJSON();
var features_activity_8322609317tracks_4 = format_activity_8322609317tracks_4.readFeatures(json_activity_8322609317tracks_4, 
            {dataProjection: 'EPSG:4326', featureProjection: 'EPSG:3857'});
var jsonSource_activity_8322609317tracks_4 = new ol.source.Vector({
    attributions: ' ',
});
jsonSource_activity_8322609317tracks_4.addFeatures(features_activity_8322609317tracks_4);
var lyr_activity_8322609317tracks_4 = new ol.layer.Vector({
                declutter: true,
                source:jsonSource_activity_8322609317tracks_4, 
                style: style_activity_8322609317tracks_4,
                interactive: true,
                title: '<img src="styles/legend/activity_8322609317tracks_4.png" /> activity_8322609317 tracks'
            });

lyr_OpenTopoMap_0.setVisible(true);lyr_szczyty_1.setVisible(true);lyr_Mesoregions2018_2.setVisible(true);lyr_trasy_szczyty_3.setVisible(true);lyr_activity_8322609317tracks_4.setVisible(true);
var layersList = [lyr_OpenTopoMap_0,lyr_szczyty_1,lyr_Mesoregions2018_2,lyr_trasy_szczyty_3,lyr_activity_8322609317tracks_4];
lyr_szczyty_1.set('fieldAliases', {'fid': 'fid', 'nazwa': 'nazwa', });
lyr_Mesoregions2018_2.set('fieldAliases', {'k_MEZO': 'k_MEZO', 'n_MEZO': 'n_MEZO', 'n_MEZO_ENG': 'n_MEZO_ENG', 'k_MEZO_old': 'k_MEZO_old', 'n_MEZO_old': 'n_MEZO_old', 'k_MAKR': 'k_MAKR', 'n_MAKR': 'n_MAKR', 'k_PPRW': 'k_PPRW', 'n_PPRW': 'n_PPRW', 'k_PRW': 'k_PRW', 'n_PRW': 'n_PRW', 'k_MEGR': 'k_MEGR', 'n_MEGR': 'n_MEGR', 'POW_km': 'POW_km', });
lyr_trasy_szczyty_3.set('fieldAliases', {'fid': 'fid', 'name': 'name', 'typ': 'typ', });
lyr_activity_8322609317tracks_4.set('fieldAliases', {'name': 'name', 'cmt': 'cmt', 'desc': 'desc', 'src': 'src', 'link1_href': 'link1_href', 'link1_text': 'link1_text', 'link1_type': 'link1_type', 'link2_href': 'link2_href', 'link2_text': 'link2_text', 'link2_type': 'link2_type', 'number': 'number', 'type': 'type', });
lyr_szczyty_1.set('fieldImages', {'fid': 'TextEdit', 'nazwa': 'TextEdit', });
lyr_Mesoregions2018_2.set('fieldImages', {'k_MEZO': 'TextEdit', 'n_MEZO': 'TextEdit', 'n_MEZO_ENG': 'TextEdit', 'k_MEZO_old': 'TextEdit', 'n_MEZO_old': 'TextEdit', 'k_MAKR': 'TextEdit', 'n_MAKR': 'TextEdit', 'k_PPRW': 'TextEdit', 'n_PPRW': 'TextEdit', 'k_PRW': 'TextEdit', 'n_PRW': 'TextEdit', 'k_MEGR': 'TextEdit', 'n_MEGR': 'TextEdit', 'POW_km': 'TextEdit', });
lyr_trasy_szczyty_3.set('fieldImages', {'fid': 'TextEdit', 'name': 'TextEdit', 'typ': 'TextEdit', });
lyr_activity_8322609317tracks_4.set('fieldImages', {'name': '', 'cmt': '', 'desc': '', 'src': '', 'link1_href': '', 'link1_text': '', 'link1_type': '', 'link2_href': '', 'link2_text': '', 'link2_type': '', 'number': '', 'type': '', });
lyr_szczyty_1.set('fieldLabels', {'fid': 'header label', 'nazwa': 'no label', });
lyr_Mesoregions2018_2.set('fieldLabels', {'k_MEZO': 'no label', 'n_MEZO': 'no label', 'n_MEZO_ENG': 'no label', 'k_MEZO_old': 'no label', 'n_MEZO_old': 'no label', 'k_MAKR': 'no label', 'n_MAKR': 'no label', 'k_PPRW': 'no label', 'n_PPRW': 'no label', 'k_PRW': 'no label', 'n_PRW': 'no label', 'k_MEGR': 'no label', 'n_MEGR': 'no label', 'POW_km': 'no label', });
lyr_trasy_szczyty_3.set('fieldLabels', {'fid': 'no label', 'name': 'no label', 'typ': 'no label', });
lyr_activity_8322609317tracks_4.set('fieldLabels', {'name': 'no label', 'cmt': 'no label', 'desc': 'no label', 'src': 'no label', 'link1_href': 'no label', 'link1_text': 'no label', 'link1_type': 'no label', 'link2_href': 'no label', 'link2_text': 'no label', 'link2_type': 'no label', 'number': 'no label', 'type': 'no label', });
lyr_activity_8322609317tracks_4.on('precompose', function(evt) {
    evt.context.globalCompositeOperation = 'normal';
});