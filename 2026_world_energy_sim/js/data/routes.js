/**
 * Oil export routes: seaborne + pipelines.
 *
 * vol   - baseline flow in mb/d (2024, rounded)
 * days  - transit time from loading to discharge (VLCC ~580 km/day + port time)
 * via   - chokepoints the route passes through
 * path  - WP points drawn as a polyline
 * alts  - reroute variants, picked automatically or forced by hand; each carries
 *         a time penalty and may be capped by a bypass pipeline (`requires`)
 *
 * Volumes do not add up to each country's full net trade - the remainder is
 * dispersed spot trade that the engine treats as "off-model supply", which
 * cannot be severed by cutting a single route.
 */

const P = (...keys) => keys.map(k => {
  if (!WP[k]) throw new Error('Unknown waypoint: ' + k);
  return WP[k];
});

// Saudi crude routed overland to Yanbu clears Hormuz entirely; every Saudi
// route gets this option, capped by Petroline's 5 mb/d against ~6 mb/d of demand.
const YANBU_ASIA = ['ABQAIQ','PETRO_MID1','PETRO_MID2','YANBU','RED_SEA_S','BAB_MANDEB','ARAB_SEA'];
const YANBU_EUR  = ['ABQAIQ','PETRO_MID1','PETRO_MID2','YANBU','RED_SEA_N','SUEZ','PORT_SAID','MED_E'];

const ROUTES = [
  // ============================= SAUDI ARABIA ==============================
  {
    id:'SAU-CHN', from:'SAU', to:'CHN', vol:1.80, days:22, mode:'sea',
    label:'Ras Tanura → Ningbo',
    via:['HORMUZ','MALACCA'],
    path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','NINGBO'),
    alts:[
      { id:'lombok', label:'Divert via Lombok / Makassar', addDays:4, via:['HORMUZ'],
        path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','INDIAN_S','LOMBOK','MAKASSAR','SCS_S','SCS_N','NINGBO') },
      { id:'petroline', label:'Petroline → Yanbu → Bab el-Mandeb', addDays:5, requires:'PIPE_EW',
        via:['BAB','MALACCA'],
        path:P(...YANBU_ASIA,'SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','NINGBO') },
    ],
  },
  {
    id:'SAU-IND', from:'SAU', to:'IND', vol:0.80, days:6, mode:'sea',
    label:'Ras Tanura → Jamnagar',
    via:['HORMUZ'],
    path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','JAMNAGAR'),
    alts:[
      { id:'petroline', label:'Petroline → Yanbu → Bab el-Mandeb', addDays:7, requires:'PIPE_EW', via:['BAB'],
        path:P(...YANBU_ASIA,'JAMNAGAR') },
    ],
  },
  {
    id:'SAU-JPN', from:'SAU', to:'JPN', vol:1.05, days:24, mode:'sea',
    label:'Ras Tanura → Yokohama',
    via:['HORMUZ','MALACCA'],
    path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','LUZON','PHIL_SEA','YOKOHAMA'),
    alts:[
      { id:'lombok', label:'Divert via Lombok / Makassar', addDays:4, via:['HORMUZ'],
        path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','INDIAN_S','LOMBOK','MAKASSAR','PHIL_SEA','YOKOHAMA') },
      { id:'petroline', label:'Petroline → Yanbu → Bab el-Mandeb', addDays:6, requires:'PIPE_EW',
        via:['BAB','MALACCA'],
        path:P(...YANBU_ASIA,'SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','LUZON','PHIL_SEA','YOKOHAMA') },
    ],
  },
  {
    id:'SAU-KOR', from:'SAU', to:'KOR', vol:0.90, days:23, mode:'sea',
    label:'Ras Tanura → Ulsan',
    via:['HORMUZ','MALACCA'],
    path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','LUZON','ULSAN'),
    alts:[
      { id:'lombok', label:'Divert via Lombok / Makassar', addDays:4, via:['HORMUZ'],
        path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','INDIAN_S','LOMBOK','MAKASSAR','PHIL_SEA','ULSAN') },
      { id:'petroline', label:'Petroline → Yanbu → Bab el-Mandeb', addDays:6, requires:'PIPE_EW',
        via:['BAB','MALACCA'],
        path:P(...YANBU_ASIA,'SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','LUZON','ULSAN') },
    ],
  },
  {
    id:'SAU-TWN', from:'SAU', to:'TWN', vol:0.35, days:22, mode:'sea',
    label:'Ras Tanura → Kaohsiung',
    via:['HORMUZ','MALACCA'],
    path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','KAOHSIUNG'),
    alts:[
      { id:'petroline', label:'Petroline → Yanbu → Bab el-Mandeb', addDays:6, requires:'PIPE_EW',
        via:['BAB','MALACCA'],
        path:P(...YANBU_ASIA,'SRI_LANKA','MALACCA','SINGAPORE','SCS_S','KAOHSIUNG') },
    ],
  },
  {
    id:'SAU-NLD', from:'SAU', to:'NLD', vol:0.55, days:20, mode:'sea',
    label:'Ras Tanura → Rotterdam (Suez)',
    via:['HORMUZ','BAB','SUEZ','GIBRALTAR'],
    path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','BAB_MANDEB','RED_SEA_S','RED_SEA_N','SUEZ','PORT_SAID','MED_E','MED_C','MED_W','GIBRALTAR','IBERIA_W','BISCAY','CHANNEL','ROTTERDAM'),
    alts:[
      { id:'cape', label:'Round the Cape of Good Hope', addDays:14, via:['HORMUZ','CAPE','GIBRALTAR'],
        path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','MOZ_CHANNEL','CAPE','ATL_S','ATL_C','ATL_N','IBERIA_W','BISCAY','CHANNEL','ROTTERDAM') },
      { id:'yanbu', label:'Petroline → Yanbu → Suez', addDays:2, requires:'PIPE_EW', via:['SUEZ','GIBRALTAR'],
        path:P(...YANBU_EUR,'MED_C','MED_W','GIBRALTAR','IBERIA_W','BISCAY','CHANNEL','ROTTERDAM') },
    ],
  },
  {
    id:'SAU-POL', from:'SAU', to:'POL', vol:0.25, days:24, mode:'sea',
    label:'Ras Tanura → Gdansk (Suez)',
    via:['HORMUZ','BAB','SUEZ','GIBRALTAR','DANISH'],
    path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','BAB_MANDEB','RED_SEA_S','RED_SEA_N','SUEZ','PORT_SAID','MED_E','MED_C','MED_W','GIBRALTAR','IBERIA_W','BISCAY','CHANNEL','NORTH_SEA','SKAGERRAK','DANISH','BALTIC_C','GDANSK'),
    alts:[
      { id:'yanbu', label:'Petroline → Yanbu → Suez', addDays:2, requires:'PIPE_EW', via:['SUEZ','GIBRALTAR','DANISH'],
        path:P(...YANBU_EUR,'MED_C','MED_W','GIBRALTAR','IBERIA_W','BISCAY','CHANNEL','NORTH_SEA','SKAGERRAK','DANISH','BALTIC_C','GDANSK') },
      { id:'cape', label:'Round the Cape of Good Hope', addDays:14, via:['HORMUZ','CAPE','DANISH'],
        path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','MOZ_CHANNEL','CAPE','ATL_S','ATL_C','ATL_N','CHANNEL','NORTH_SEA','SKAGERRAK','DANISH','BALTIC_C','GDANSK') },
    ],
  },
  {
    id:'SAU-USA', from:'SAU', to:'USA', vol:0.30, days:32, mode:'sea',
    label:'Ras Tanura → Houston (Suez)',
    via:['HORMUZ','BAB','SUEZ','GIBRALTAR'],
    path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','BAB_MANDEB','RED_SEA_S','RED_SEA_N','SUEZ','PORT_SAID','MED_E','MED_C','MED_W','GIBRALTAR','ATL_N','BAHAMAS','FLORIDA_STR','GULF_MEXICO','HOUSTON'),
    alts:[
      { id:'cape', label:'Round the Cape of Good Hope', addDays:12, via:['HORMUZ','CAPE'],
        path:P('RAS_TANURA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','MOZ_CHANNEL','CAPE','ATL_S','ATL_C','BAHAMAS','FLORIDA_STR','GULF_MEXICO','HOUSTON') },
      { id:'yanbu', label:'Petroline → Yanbu → Suez', addDays:2, requires:'PIPE_EW', via:['SUEZ','GIBRALTAR'],
        path:P(...YANBU_EUR,'MED_C','MED_W','GIBRALTAR','ATL_N','BAHAMAS','FLORIDA_STR','GULF_MEXICO','HOUSTON') },
    ],
  },

  // ================================= IRAQ ==================================
  {
    id:'IRQ-CHN', from:'IRQ', to:'CHN', vol:1.10, days:23, mode:'sea',
    label:'Basra → Qingdao',
    via:['HORMUZ','MALACCA'],
    path:P('BASRA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','QINGDAO'),
    alts:[
      { id:'lombok', label:'Divert via Lombok', addDays:4, via:['HORMUZ'],
        path:P('BASRA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','INDIAN_S','LOMBOK','MAKASSAR','SCS_S','SCS_N','QINGDAO') },
    ],
  },
  {
    id:'IRQ-IND', from:'IRQ', to:'IND', vol:0.90, days:7, mode:'sea',
    label:'Basra → Mumbai',
    via:['HORMUZ'],
    path:P('BASRA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','MUMBAI'),
    alts:[],
  },
  {
    id:'IRQ-ITA', from:'IRQ', to:'ITA', vol:0.70, days:21, mode:'sea',
    label:'Basra → Augusta (Suez)',
    via:['HORMUZ','BAB','SUEZ'],
    path:P('BASRA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','BAB_MANDEB','RED_SEA_S','RED_SEA_N','SUEZ','PORT_SAID','MED_E','AUGUSTA'),
    alts:[
      { id:'ceyhan', label:'Kirkuk-Ceyhan pipeline', addDays:-15, requires:'PIPE_ITP', via:[],
        path:P('KIRKUK','CEYHAN','MED_E','AUGUSTA') },
      { id:'cape', label:'Round the Cape of Good Hope', addDays:16, via:['HORMUZ','CAPE','GIBRALTAR'],
        path:P('BASRA','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','MOZ_CHANNEL','CAPE','ATL_S','ATL_C','IBERIA_W','GIBRALTAR','MED_W','AUGUSTA') },
    ],
  },

  // ================================== UAE ==================================
  {
    id:'ARE-CHN', from:'ARE', to:'CHN', vol:0.65, days:21, mode:'sea',
    label:'Ruwais → Ningbo',
    via:['HORMUZ','MALACCA'],
    path:P('RUWAIS','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','NINGBO'),
    alts:[
      { id:'adcop', label:'ADCOP → Fujairah (clears Hormuz)', addDays:1, requires:'PIPE_ADCOP', via:['MALACCA'],
        path:P('HABSHAN','FUJAIRAH','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','NINGBO') },
    ],
  },
  {
    id:'ARE-JPN', from:'ARE', to:'JPN', vol:0.75, days:23, mode:'sea',
    label:'Ruwais → Yokohama',
    via:['HORMUZ','MALACCA'],
    path:P('RUWAIS','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','LUZON','PHIL_SEA','YOKOHAMA'),
    alts:[
      { id:'adcop', label:'ADCOP → Fujairah (clears Hormuz)', addDays:1, requires:'PIPE_ADCOP', via:['MALACCA'],
        path:P('HABSHAN','FUJAIRAH','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','LUZON','PHIL_SEA','YOKOHAMA') },
    ],
  },
  {
    id:'ARE-IND', from:'ARE', to:'IND', vol:0.50, days:5, mode:'sea',
    label:'Ruwais → Jamnagar',
    via:['HORMUZ'],
    path:P('RUWAIS','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','JAMNAGAR'),
    alts:[
      { id:'adcop', label:'ADCOP → Fujairah (clears Hormuz)', addDays:1, requires:'PIPE_ADCOP', via:[],
        path:P('HABSHAN','FUJAIRAH','OMAN_SEA','ARAB_SEA','JAMNAGAR') },
    ],
  },
  {
    id:'ARE-SGP', from:'ARE', to:'SGP', vol:0.45, days:16, mode:'sea',
    label:'Fujairah → Singapore',
    via:['HORMUZ','MALACCA'],
    path:P('RUWAIS','GULF_MID','HORMUZ','FUJAIRAH','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE'),
    alts:[
      { id:'adcop', label:'ADCOP → Fujairah (clears Hormuz)', addDays:1, requires:'PIPE_ADCOP', via:['MALACCA'],
        path:P('HABSHAN','FUJAIRAH','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE') },
    ],
  },
  {
    id:'ARE-THA', from:'ARE', to:'THA', vol:0.30, days:18, mode:'sea',
    label:'Ruwais → Map Ta Phut',
    via:['HORMUZ','MALACCA'],
    path:P('RUWAIS','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','MAP_TA_PHUT'),
    alts:[
      { id:'adcop', label:'ADCOP → Fujairah (clears Hormuz)', addDays:1, requires:'PIPE_ADCOP', via:['MALACCA'],
        path:P('HABSHAN','FUJAIRAH','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','MAP_TA_PHUT') },
    ],
  },
  {
    id:'ARE-AUS', from:'ARE', to:'AUS', vol:0.25, days:17, mode:'sea',
    label:'Ruwais → North West Shelf',
    via:['HORMUZ'],
    path:P('RUWAIS','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','INDIAN_S','AUS_NW'),
    alts:[
      { id:'adcop', label:'ADCOP → Fujairah (clears Hormuz)', addDays:1, requires:'PIPE_ADCOP', via:[],
        path:P('HABSHAN','FUJAIRAH','ARAB_SEA','INDIAN_S','AUS_NW') },
    ],
  },

  // ================================ KUWAIT =================================
  {
    id:'KWT-KOR', from:'KWT', to:'KOR', vol:0.60, days:24, mode:'sea',
    label:'Mina al-Ahmadi → Ulsan',
    via:['HORMUZ','MALACCA'],
    path:P('KUWAIT','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','LUZON','ULSAN'),
    alts:[{ id:'lombok', label:'Divert via Lombok', addDays:4, via:['HORMUZ'],
      path:P('KUWAIT','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','INDIAN_S','LOMBOK','MAKASSAR','PHIL_SEA','ULSAN') }],
  },
  {
    id:'KWT-CHN', from:'KWT', to:'CHN', vol:0.50, days:23, mode:'sea',
    label:'Mina al-Ahmadi → Ningbo',
    via:['HORMUZ','MALACCA'],
    path:P('KUWAIT','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','NINGBO'),
    alts:[],
  },
  {
    id:'KWT-IND', from:'KWT', to:'IND', vol:0.35, days:7, mode:'sea',
    label:'Mina al-Ahmadi → Mumbai',
    via:['HORMUZ'],
    path:P('KUWAIT','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','MUMBAI'),
    alts:[],
  },

  // ================================= IRAN ==================================
  {
    id:'IRN-CHN', from:'IRN', to:'CHN', vol:1.40, days:24, mode:'sea',
    label:'Kharg → Shandong (shadow fleet)',
    via:['HORMUZ','MALACCA'],
    path:P('KHARG','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','QINGDAO'),
    alts:[{ id:'lombok', label:'Divert via Lombok', addDays:4, via:['HORMUZ'],
      path:P('KHARG','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','INDIAN_S','LOMBOK','MAKASSAR','SCS_S','SCS_N','QINGDAO') }],
  },

  // ================================= QATAR =================================
  {
    id:'QAT-KOR', from:'QAT', to:'KOR', vol:0.50, days:24, mode:'sea',
    label:'Ras Laffan → Ulsan',
    via:['HORMUZ','MALACCA'],
    path:P('QATAR_T','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','LUZON','ULSAN'),
    alts:[],
  },
  {
    id:'QAT-IND', from:'QAT', to:'IND', vol:0.35, days:6, mode:'sea',
    label:'Ras Laffan → Jamnagar',
    via:['HORMUZ'],
    path:P('QATAR_T','GULF_MID','HORMUZ','OMAN_SEA','ARAB_SEA','JAMNAGAR'),
    alts:[],
  },

  // ================================ RUSSIA =================================
  {
    id:'RUS-IND', from:'RUS', to:'IND', vol:1.60, days:22, mode:'sea',
    label:'Primorsk / Ust-Luga → Jamnagar (Suez)',
    via:['DANISH','SUEZ','BAB'],
    path:P('PRIMORSK','GULF_FINLAND','BALTIC_C','DANISH','SKAGERRAK','NORTH_SEA','CHANNEL','BISCAY','IBERIA_W','GIBRALTAR','MED_W','MED_C','MED_E','PORT_SAID','SUEZ','RED_SEA_N','RED_SEA_S','BAB_MANDEB','ARAB_SEA','JAMNAGAR'),
    alts:[
      { id:'cape', label:'Round the Cape of Good Hope', addDays:15, via:['DANISH','CAPE'],
        path:P('PRIMORSK','GULF_FINLAND','BALTIC_C','DANISH','SKAGERRAK','NORTH_SEA','CHANNEL','BISCAY','ATL_N','ATL_C','ATL_S','CAPE','MOZ_CHANNEL','ARAB_SEA','JAMNAGAR') },
    ],
  },
  {
    id:'RUS-CHN-SEA', from:'RUS', to:'CHN', vol:0.70, days:6, mode:'sea',
    label:'Kozmino → Shandong (ESPO blend)',
    via:[],
    path:P('KOZMINO','SEA_JAPAN','PHIL_SEA','NINGBO'),
    alts:[],
  },
  {
    id:'RUS-CHN-PIPE', from:'RUS', to:'CHN', vol:0.90, days:5, mode:'pipe',
    label:'ESPO pipeline: Taishet → Daqing',
    via:[],
    path:P('TAISHET','SKOVORODINO','MOHE','DAQING'),
    alts:[],
  },
  {
    id:'RUS-TUR', from:'RUS', to:'TUR', vol:0.35, days:5, mode:'sea',
    label:'Novorossiysk → Izmit',
    via:['TURKISH'],
    path:P('NOVOROSSIYSK','BOSPHORUS','IZMIT'),
    alts:[],
  },
  {
    id:'RUS-CHN-BALTIC', from:'RUS', to:'CHN', vol:0.55, days:38, mode:'sea',
    label:'Ust-Luga → Shandong (Suez + Malacca)',
    via:['DANISH','SUEZ','BAB','MALACCA'],
    path:P('PRIMORSK','GULF_FINLAND','BALTIC_C','DANISH','SKAGERRAK','NORTH_SEA','CHANNEL','BISCAY','IBERIA_W','GIBRALTAR','MED_W','MED_C','MED_E','PORT_SAID','SUEZ','RED_SEA_N','RED_SEA_S','BAB_MANDEB','ARAB_SEA','SRI_LANKA','MALACCA','SINGAPORE','SCS_S','SCS_N','QINGDAO'),
    alts:[],
  },
  {
    id:'RUS-POL-PIPE', from:'RUS', to:'POL', vol:0.00, days:4, mode:'pipe', disabled:true,
    label:'Druzhba: Samara → Plock → Schwedt (suspended since 2023)',
    via:[],
    path:P('SAMARA','MOZYR','ADAMOWO','PLOCK','SCHWEDT'),
    alts:[],
    note:'EU embargo. Run the "Druzhba returns" scenario to see the effect of restoring it.',
  },

  // ============================== KAZAKHSTAN ===============================
  {
    id:'KAZ-ITA', from:'KAZ', to:'ITA', vol:1.10, days:12, mode:'sea',
    label:'CPC: Tengiz → Novorossiysk → Augusta',
    via:['TURKISH'],
    path:P('TENGIZ','NOVOROSSIYSK','BOSPHORUS','DARDANELLES','AEGEAN','MED_C','AUGUSTA'),
    alts:[],
  },
  {
    id:'KAZ-CHN-PIPE', from:'KAZ', to:'CHN', vol:0.22, days:8, mode:'pipe',
    label:'Kazakhstan-China pipeline: Atasu → Lanzhou',
    via:[],
    path:P('TENGIZ','ATASU','ALASHANKOU','XINJIANG','LANZHOU'),
    alts:[],
  },
  {
    id:'KAZ-DEU', from:'KAZ', to:'DEU', vol:0.20, days:9, mode:'pipe',
    label:'Kazakh crude via Druzhba → Schwedt',
    via:[],
    path:P('TENGIZ','SAMARA','MOZYR','ADAMOWO','SCHWEDT'),
    alts:[],
  },

  // ================================ NORWAY =================================
  {
    id:'NOR-DEU', from:'NOR', to:'DEU', vol:0.85, days:3, mode:'sea',
    label:'Mongstad → Wilhelmshaven',
    via:[],
    path:P('MONGSTAD','NORTH_SEA','WILHELMSHAVEN'),
    alts:[],
  },
  {
    id:'NOR-GBR', from:'NOR', to:'GBR', vol:0.40, days:2, mode:'sea',
    label:'Sullom Voe → Immingham',
    via:[],
    path:P('MONGSTAD','SULLOM_VOE','IMMINGHAM'),
    alts:[],
  },
  {
    id:'NOR-POL', from:'NOR', to:'POL', vol:0.25, days:3, mode:'sea',
    label:'Mongstad → Naftoport Gdansk',
    via:['DANISH'],
    path:P('MONGSTAD','NORTH_SEA','SKAGERRAK','DANISH','BALTIC_C','GDANSK'),
    alts:[],
  },

  // ================================ AFRICA =================================
  {
    id:'NGA-FRA', from:'NGA', to:'FRA', vol:0.45, days:13, mode:'sea',
    label:'Bonny → Le Havre',
    via:[],
    path:P('BONNY','GULF_GUINEA','ATL_C','IBERIA_W','BISCAY','LE_HAVRE'),
    alts:[],
  },
  {
    id:'NGA-IND', from:'NGA', to:'IND', vol:0.35, days:26, mode:'sea',
    label:'Bonny → Jamnagar (Cape)',
    via:['CAPE'],
    path:P('BONNY','GULF_GUINEA','ATL_S','CAPE','AGULHAS','MOZ_CHANNEL','ARAB_SEA','JAMNAGAR'),
    alts:[],
  },
  {
    id:'AGO-CHN', from:'AGO', to:'CHN', vol:0.65, days:32, mode:'sea',
    label:'Cabinda → Ningbo (Cape + Malacca)',
    via:['CAPE','MALACCA'],
    path:P('CABINDA','ATL_S','CAPE','AGULHAS','INDIAN_S','MALACCA','SINGAPORE','SCS_S','SCS_N','NINGBO'),
    alts:[
      { id:'lombok', label:'Divert via Lombok', addDays:3, via:['CAPE'],
        path:P('CABINDA','ATL_S','CAPE','AGULHAS','INDIAN_S','LOMBOK','MAKASSAR','SCS_S','SCS_N','NINGBO') },
    ],
  },
  {
    id:'LBY-ITA', from:'LBY', to:'ITA', vol:0.60, days:3, mode:'sea',
    label:'Es Sider → Trieste',
    via:[],
    path:P('ES_SIDER','SICILY','TRIESTE'),
    alts:[],
  },
  {
    id:'DZA-ESP', from:'DZA', to:'ESP', vol:0.50, days:3, mode:'sea',
    label:'Skikda → Algeciras',
    via:[],
    path:P('SKIKDA','MED_W','ALGECIRAS'),
    alts:[],
  },

  // =============================== AMERICAS ================================
  {
    id:'CAN-USA-PIPE', from:'CAN', to:'USA', vol:3.80, days:4, mode:'pipe',
    label:'Enbridge / Keystone: Hardisty → Cushing → Houston',
    via:[],
    path:P('HARDISTY','KEYSTONE_MID','CUSHING','HOUSTON'),
    alts:[],
  },
  {
    id:'CAN-CHN', from:'CAN', to:'CHN', vol:0.30, days:17, mode:'sea',
    label:'TMX: Vancouver → Ningbo (Pacific)',
    via:[],
    path:P('VANCOUVER','PAC_MID_E','PAC_MID_W','PAC_ASIA','PAC_CHINA'),
    alts:[],
  },
  {
    id:'USA-NLD', from:'USA', to:'NLD', vol:1.50, days:15, mode:'sea',
    label:'Corpus Christi → Rotterdam',
    via:[],
    path:P('CORPUS','GULF_MEXICO','FLORIDA_STR','BAHAMAS','ATL_N','CHANNEL','ROTTERDAM'),
    alts:[],
  },
  {
    id:'USA-KOR', from:'USA', to:'KOR', vol:0.55, days:30, mode:'sea',
    label:'Houston → Ulsan (Panama / Pacific)',
    via:['PANAMA'],
    path:P('HOUSTON','GULF_MEXICO','PANAMA','PAC_PANAMA_W','PAC_S','PAC_MID_E','PAC_MID_W','PAC_KOREA'),
    alts:[],
  },
  {
    id:'USA-IND', from:'USA', to:'IND', vol:0.35, days:34, mode:'sea',
    label:'Houston → Jamnagar (Cape)',
    via:['CAPE'],
    path:P('HOUSTON','GULF_MEXICO','FLORIDA_STR','ATL_C','ATL_S','CAPE','AGULHAS','MOZ_CHANNEL','ARAB_SEA','JAMNAGAR'),
    alts:[],
  },
  {
    id:'USA-ESP', from:'USA', to:'ESP', vol:0.40, days:16, mode:'sea',
    label:'Corpus Christi → Algeciras',
    via:['GIBRALTAR'],
    path:P('CORPUS','GULF_MEXICO','FLORIDA_STR','BAHAMAS','ATL_N','IBERIA_W','GIBRALTAR','ALGECIRAS'),
    alts:[],
  },
  {
    id:'USA-GBR', from:'USA', to:'GBR', vol:0.35, days:14, mode:'sea',
    label:'Houston → Immingham',
    via:[],
    path:P('HOUSTON','GULF_MEXICO','FLORIDA_STR','BAHAMAS','ATL_N','CHANNEL','IMMINGHAM'),
    alts:[],
  },
  {
    id:'USA-POL', from:'USA', to:'POL', vol:0.15, days:17, mode:'sea',
    label:'Corpus Christi → Naftoport Gdansk',
    via:['DANISH'],
    path:P('CORPUS','GULF_MEXICO','FLORIDA_STR','BAHAMAS','ATL_N','CHANNEL','NORTH_SEA','SKAGERRAK','DANISH','BALTIC_C','GDANSK'),
    alts:[],
  },
  {
    id:'BRA-CHN', from:'BRA', to:'CHN', vol:0.80, days:35, mode:'sea',
    label:'Santos → Ningbo (Cape + Malacca)',
    via:['CAPE','MALACCA'],
    path:P('BRAZIL_SE','ATL_S','CAPE','AGULHAS','INDIAN_S','MALACCA','SINGAPORE','SCS_S','SCS_N','NINGBO'),
    alts:[
      { id:'lombok', label:'Divert via Lombok', addDays:3, via:['CAPE'],
        path:P('BRAZIL_SE','ATL_S','CAPE','AGULHAS','INDIAN_S','LOMBOK','MAKASSAR','SCS_S','SCS_N','NINGBO') },
    ],
  },
  {
    id:'VEN-CHN', from:'VEN', to:'CHN', vol:0.30, days:40, mode:'sea',
    label:'Jose → Shandong (Cape)',
    via:['CAPE','MALACCA'],
    path:P('JOSE_VEN','CARIB_E','ATL_C','ATL_S','CAPE','AGULHAS','INDIAN_S','MALACCA','SINGAPORE','SCS_S','SCS_N','QINGDAO'),
    alts:[],
  },
  {
    id:'MEX-USA', from:'MEX', to:'USA', vol:0.45, days:4, mode:'sea',
    label:'Gulf of Mexico → Houston',
    via:[],
    path:P('GULF_MEXICO','HOUSTON'),
    alts:[],
  },
];
