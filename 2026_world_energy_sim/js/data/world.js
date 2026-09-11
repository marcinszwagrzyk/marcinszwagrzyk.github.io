/**
 * Baseline data for the world oil market.
 *
 * Unit everywhere: mb/d = million barrels per day (total liquids).
 * Reference year: 2024 (EI Statistical Review 2025 / EIA International Energy Statistics).
 * Stocks: commercial + strategic combined, expressed in days of own consumption.
 * Figures are deliberately rounded - this is a teaching model, not an accounting system.
 */

// --- Navigation waypoints used to draw the routes ---------------------------
const WP = {
  // Persian Gulf
  RAS_TANURA:   [26.65,  50.16],
  BASRA:        [29.60,  48.80],
  KUWAIT:       [29.08,  48.35],
  KHARG:        [29.25,  50.32],
  QATAR_T:      [25.55,  51.60],
  RUWAIS:       [24.15,  52.75],
  GULF_MID:     [26.20,  53.60],
  HORMUZ:       [26.57,  56.25],
  FUJAIRAH:     [25.15,  56.40],
  OMAN_SEA:     [24.00,  58.50],

  // Indian Ocean
  ARAB_SEA:     [18.00,  62.00],
  JAMNAGAR:     [22.30,  69.10],
  MUMBAI:       [18.60,  72.30],
  SRI_LANKA:    [ 5.00,  82.00],
  INDIAN_S:     [-8.00,  75.00],

  // South-East and East Asia
  MALACCA:      [ 2.50, 101.20],
  SINGAPORE:    [ 1.26, 104.05],
  LOMBOK:       [-8.75, 115.85],
  MAKASSAR:     [-2.00, 118.50],
  SCS_S:        [ 5.00, 108.80],
  SCS_N:        [16.50, 113.00],
  LUZON:        [20.50, 121.00],
  PHIL_SEA:     [22.00, 127.00],
  NINGBO:       [29.90, 122.30],
  QINGDAO:      [36.00, 120.60],
  ULSAN:        [35.40, 129.60],
  YOKOHAMA:     [34.90, 139.90],
  KAOHSIUNG:    [22.50, 120.20],
  MAP_TA_PHUT:  [12.60, 101.15],
  AUS_NW:       [-20.00, 116.00],
  KOZMINO:      [42.80, 133.00],
  SEA_JAPAN:    [40.00, 135.00],

  // Red Sea / Suez / Mediterranean
  BAB_MANDEB:   [12.58,  43.33],
  RED_SEA_S:    [15.50,  41.50],
  YANBU:        [24.05,  38.05],
  RED_SEA_N:    [27.50,  34.50],
  SUEZ:         [29.95,  32.55],
  PORT_SAID:    [31.40,  32.35],
  CEYHAN:       [36.85,  35.95],
  MED_E:        [33.50,  29.00],
  MED_C:        [35.00,  18.00],
  MED_W:        [37.50,   5.00],
  TRIESTE:      [45.60,  13.60],
  SICILY:       [37.00,  13.00],
  ES_SIDER:     [30.95,  18.35],
  SKIKDA:       [37.00,   6.90],
  AUGUSTA:      [37.20,  15.25],
  ALGECIRAS:    [36.10,  -5.40],
  GIBRALTAR:    [35.95,  -5.60],

  // Black Sea / Baltic / North Sea
  NOVOROSSIYSK: [44.70,  37.80],
  BOSPHORUS:    [41.10,  29.05],
  DARDANELLES:  [40.20,  26.30],
  AEGEAN:       [37.50,  25.00],
  IZMIT:        [40.75,  29.90],
  PRIMORSK:     [60.30,  28.70],
  GULF_FINLAND: [59.60,  25.00],
  BALTIC_C:     [55.80,  17.50],
  DANISH:       [55.90,  11.00],
  SKAGERRAK:    [57.80,   8.50],
  NORTH_SEA:    [56.50,   3.00],
  MONGSTAD:     [60.80,   5.00],
  SULLOM_VOE:   [60.45,  -1.30],
  ROTTERDAM:    [51.95,   4.05],
  WILHELMSHAVEN:[53.60,   8.10],
  GDANSK:       [54.45,  18.70],
  IMMINGHAM:    [53.63,  -0.18],
  CHANNEL:      [50.00,  -1.50],
  LE_HAVRE:     [49.48,   0.12],
  BISCAY:       [45.50,  -8.00],
  IBERIA_W:     [39.50, -10.50],

  // Atlantic / Africa
  CAPE:         [-35.20,  19.50],
  AGULHAS:      [-36.50,  27.00],
  MOZ_CHANNEL:  [-24.00,  38.00],
  BONNY:        [ 4.20,   7.10],
  CABINDA:      [-5.60,  11.80],
  GULF_GUINEA:  [ 2.00,   2.00],
  ATL_C:        [10.00, -25.00],
  ATL_N:        [40.00, -35.00],
  ATL_S:        [-20.00,  -5.00],

  // Americas
  HOUSTON:      [29.20, -94.50],
  CORPUS:       [27.60, -97.10],
  GULF_MEXICO:  [25.00, -88.00],
  FLORIDA_STR:  [24.20, -80.00],
  BAHAMAS:      [26.50, -75.00],
  JOSE_VEN:     [10.05, -64.70],
  CARIB_E:      [12.00, -61.00],
  BRAZIL_SE:    [-23.50, -43.00],
  PANAMA:       [ 9.00, -79.60],
  VANCOUVER:    [49.00, -123.60],
  HARDISTY:     [52.65, -111.30],
  CUSHING:      [35.98,  -96.77],

  // Trans-Pacific legs deliberately use longitudes outside [-180,180];
  // the renderer draws world copies, so the lines stay continuous when panning.
  PAC_MID_W:    [35.00, -175.00],
  PAC_MID_E:    [30.00, -150.00],
  PAC_ASIA:     [33.00, -215.00],   // = 145 E
  PAC_KOREA:    [35.40, -230.40],   // = 129.6 E
  PAC_CHINA:    [29.90, -237.70],   // = 122.3 E
  PAC_PANAMA_W: [ 7.00,  -80.00],
  PAC_S:        [ 10.00, -120.00],

  // Onshore pipelines
  ATASU:        [48.70,  71.60],
  ALASHANKOU:   [45.20,  82.60],
  XINJIANG:     [43.80,  87.60],
  LANZHOU:      [36.05, 103.80],
  SKOVORODINO:  [54.00, 123.90],
  MOHE:         [53.00, 122.30],
  DAQING:       [46.60, 125.00],
  TAISHET:      [55.95,  98.00],
  SAMARA:       [53.20,  50.15],
  MOZYR:        [52.05,  29.25],
  ADAMOWO:      [51.80,  23.60],
  PLOCK:        [52.55,  19.70],
  SCHWEDT:      [53.06,  14.28],
  ABQAIQ:       [25.93,  49.67],
  PETRO_MID1:   [25.30,  45.00],
  PETRO_MID2:   [24.60,  41.00],
  HABSHAN:      [23.70,  53.60],
  KIRKUK:       [35.47,  44.39],
  TENGIZ:       [46.30,  53.50],
  KEYSTONE_MID: [45.00, -101.00],
};

// --- Countries --------------------------------------------------------------
// prod  - total liquids production (mb/d)
// cons  - consumption (mb/d)
// stock - opening stocks in days of own consumption
// store - exporter storage capacity in mn bbl (buffer for oil with no buyer)
const COUNTRIES = [
  // --- Middle East exporters
  { id:'SAU', name:'Saudi Arabia',   lat:24.5, lon:45.0, prod:11.30, cons:3.90, stock:30,  store:330, group:'Middle East', role:'exporter' },
  { id:'IRQ', name:'Iraq',           lat:33.2, lon:43.7, prod: 4.30, cons:0.90, stock:20,  store: 60, group:'Middle East', role:'exporter' },
  { id:'ARE', name:'UAE',            lat:23.9, lon:54.3, prod: 4.20, cons:1.10, stock:25,  store:110, group:'Middle East', role:'exporter' },
  { id:'KWT', name:'Kuwait',         lat:29.4, lon:47.6, prod: 2.90, cons:0.50, stock:25,  store: 80, group:'Middle East', role:'exporter' },
  { id:'IRN', name:'Iran',           lat:32.0, lon:54.0, prod: 4.60, cons:2.00, stock:20,  store: 90, group:'Middle East', role:'exporter' },
  { id:'QAT', name:'Qatar',          lat:25.3, lon:51.2, prod: 1.90, cons:0.35, stock:25,  store: 45, group:'Middle East', role:'exporter' },

  // --- Eurasia
  { id:'RUS', name:'Russia',         lat:57.0, lon:52.0, prod:10.80, cons:3.70, stock:25,  store:250, group:'Eurasia',     role:'exporter' },
  { id:'KAZ', name:'Kazakhstan',     lat:48.2, lon:66.9, prod: 1.90, cons:0.35, stock:25,  store: 40, group:'Eurasia',     role:'exporter' },

  // --- Africa
  { id:'NGA', name:'Nigeria',        lat: 9.1, lon: 8.7, prod: 1.50, cons:0.50, stock:15,  store: 35, group:'Africa',      role:'exporter' },
  { id:'AGO', name:'Angola',         lat:-11.2,lon:17.9, prod: 1.10, cons:0.13, stock:15,  store: 25, group:'Africa',      role:'exporter' },
  { id:'LBY', name:'Libya',          lat:27.0, lon:17.3, prod: 1.30, cons:0.25, stock:15,  store: 30, group:'Africa',      role:'exporter' },
  { id:'DZA', name:'Algeria',        lat:28.0, lon: 2.6, prod: 1.50, cons:0.45, stock:20,  store: 30, group:'Africa',      role:'exporter' },

  // --- Americas
  { id:'USA', name:'United States',  lat:39.0, lon:-98.5,prod:20.10, cons:20.30,stock:80,  store:800, group:'Americas',    role:'hybrid'   },
  { id:'CAN', name:'Canada',         lat:54.0, lon:-112.0,prod:5.80, cons:2.40, stock:40,  store:120, group:'Americas',    role:'exporter' },
  { id:'BRA', name:'Brazil',         lat:-12.0,lon:-47.0,prod: 4.30, cons:3.20, stock:45,  store: 90, group:'Americas',    role:'exporter' },
  { id:'VEN', name:'Venezuela',      lat: 7.5, lon:-66.0,prod: 0.90, cons:0.40, stock:20,  store: 40, group:'Americas',    role:'exporter' },
  { id:'MEX', name:'Mexico',         lat:23.5, lon:-102.0,prod:1.90, cons:1.85, stock:30,  store: 40, group:'Americas',    role:'hybrid'   },

  // --- Europe
  { id:'NOR', name:'Norway',         lat:61.5, lon: 8.5, prod: 2.00, cons:0.23, stock:40,  store: 35, group:'Europe',      role:'exporter' },
  { id:'DEU', name:'Germany',        lat:51.0, lon:10.3, prod: 0.10, cons:2.20, stock:130, store:  0, group:'Europe',      role:'importer' },
  { id:'FRA', name:'France',         lat:47.0, lon: 2.4, prod: 0.05, cons:1.60, stock:120, store:  0, group:'Europe',      role:'importer' },
  { id:'ITA', name:'Italy',          lat:42.5, lon:12.5, prod: 0.10, cons:1.30, stock:110, store:  0, group:'Europe',      role:'importer' },
  { id:'ESP', name:'Spain',          lat:40.2, lon:-3.7, prod: 0.02, cons:1.30, stock:120, store:  0, group:'Europe',      role:'importer' },
  { id:'NLD', name:'Netherlands',    lat:52.2, lon: 5.4, prod: 0.03, cons:1.00, stock:140, store:  0, group:'Europe',      role:'importer' },
  { id:'GBR', name:'United Kingdom', lat:53.5, lon:-2.0, prod: 0.70, cons:1.60, stock: 75, store:  0, group:'Europe',      role:'importer' },
  { id:'POL', name:'Poland',         lat:52.1, lon:19.4, prod: 0.03, cons:0.75, stock: 95, store:  0, group:'Europe',      role:'importer' },
  { id:'TUR', name:'Turkey',         lat:39.0, lon:33.5, prod: 0.10, cons:1.15, stock: 90, store:  0, group:'Europe',      role:'importer' },

  // --- Asia-Pacific
  { id:'CHN', name:'China',          lat:35.0, lon:105.0,prod: 4.70, cons:16.40,stock: 90, store:  0, group:'Asia',        role:'importer' },
  { id:'IND', name:'India',          lat:22.0, lon:78.5, prod: 0.80, cons: 5.50,stock: 75, store:  0, group:'Asia',        role:'importer' },
  { id:'JPN', name:'Japan',          lat:36.5, lon:138.0,prod: 0.03, cons: 3.30,stock:200, store:  0, group:'Asia',        role:'importer' },
  { id:'KOR', name:'South Korea',    lat:36.4, lon:127.8,prod: 0.10, cons: 2.80,stock:190, store:  0, group:'Asia',        role:'importer' },
  { id:'SGP', name:'Singapore',      lat: 1.35,lon:103.8,prod: 0.00, cons: 1.40,stock: 60, store:  0, group:'Asia',        role:'importer' },
  { id:'TWN', name:'Taiwan',         lat:23.7, lon:121.0,prod: 0.00, cons: 1.00,stock: 90, store:  0, group:'Asia',        role:'importer' },
  { id:'THA', name:'Thailand',       lat:15.2, lon:101.0,prod: 0.35, cons: 1.45,stock: 55, store:  0, group:'Asia',        role:'importer' },
  { id:'AUS', name:'Australia',      lat:-25.0,lon:134.0,prod: 0.35, cons: 1.05,stock: 55, store:  0, group:'Asia',        role:'importer' },
];

// --- Chokepoints ------------------------------------------------------------
// cap = real daily throughput for crude and products (mb/d, EIA 2023)
const CHOKEPOINTS = [
  { id:'HORMUZ',  name:'Strait of Hormuz', short:'Hormuz', lat:26.57, lon:56.25, cap:20.9,
    note:'The only way out of the Persian Gulf. Bypasses: East-West pipeline (Saudi, 5 mb/d) and ADCOP (UAE, 1.8 mb/d) - together under a third of the traffic.' },
  { id:'MALACCA', name:'Strait of Malacca', short:'Malacca', lat: 2.50, lon:101.20, cap:23.7,
    note:'The gateway to East Asia. Bypasses: Lombok/Makassar (+3-4 days) and Sunda (+2 days).' },
  { id:'SUEZ',    name:'Suez Canal + SUMED', short:'Suez', lat:29.95, lon: 32.55, cap: 9.2,
    note:'The Asia-Europe shortcut. Bypass: Cape of Good Hope, at a cost of 12-16 extra days at sea.' },
  { id:'BAB',     name:'Bab el-Mandeb', short:'Bab el-Mandeb', lat:12.58, lon: 43.33, cap: 8.7,
    note:'The southern entrance to the Red Sea. Closing it effectively disables Suez as well.' },
  { id:'TURKISH', name:'Turkish Straits', short:'Turkish Straits', lat:41.10, lon: 29.05, cap: 3.3,
    note:'The only outlet for Caspian and Russian Black Sea crude. No practical maritime bypass.' },
  { id:'DANISH',  name:'Danish Straits', short:'Danish Straits', lat:55.90, lon: 11.00, cap: 3.2,
    note:'The exit from the Baltic - critical for Russian exports out of Primorsk and Ust-Luga.' },
  { id:'PANAMA',  name:'Panama Canal', short:'Panama', lat: 9.00, lon:-79.60, cap: 1.0,
    note:'Matters for LPG and products; VLCCs cannot transit anyway. Bypass: Cape Horn or Cape of Good Hope.' },
  { id:'CAPE',    name:'Cape of Good Hope', short:'Cape', lat:-35.20, lon:19.50, cap:12.0,
    note:'Not a strait but the bypass for Suez. Roomy, but it costs 12-16 days of sailing.' },
  { id:'GIBRALTAR',name:'Strait of Gibraltar', short:'Gibraltar', lat:35.95, lon: -5.60, cap: 6.5,
    note:'The Atlantic entrance to the Mediterranean.' },
];

// --- Bypass pipelines, drawn on the map as standing infrastructure ----------
const INFRASTRUCTURE = [
  { id:'PIPE_EW', name:'East-West Pipeline (Petroline)', owner:'SAU', cap:5.0,
    path:[WP.ABQAIQ, WP.PETRO_MID1, WP.PETRO_MID2, WP.YANBU],
    note:'Abqaiq to Yanbu on the Red Sea. The single most important way around Hormuz - but 5 mb/d against roughly 15 mb/d of Saudi traffic that would need it.' },
  { id:'PIPE_ADCOP', name:'ADCOP (Habshan-Fujairah)', owner:'ARE', cap:1.8,
    path:[WP.HABSHAN, WP.FUJAIRAH],
    note:'Takes UAE crude straight to the Gulf of Oman, clearing Hormuz completely. Only 1.8 mb/d.' },
  { id:'PIPE_ITP', name:'Kirkuk-Ceyhan Pipeline', owner:'IRQ', cap:0.5,
    path:[WP.KIRKUK, WP.CEYHAN],
    note:'Iraq\'s only non-Hormuz outlet, to the Turkish Mediterranean coast. Idle since 2023; force the reroute on the Basra-Augusta route to use it.' },
];

// --- Model parameters -------------------------------------------------------
const MODEL = {
  basePrice: 78,          // USD/bbl reference
  // Short-run price elasticity of oil demand is about -0.05:
  // a 1% supply gap moves price roughly +20% before stocks cushion it.
  demandElasticity: 0.05,
  stockCushion: 0.45,     // full tanks soften the shock, empty ones amplify it
  priceSmoothing: 0.12,   // daily smoothing (market inertia)
  maxPrice: 420,
  // Days-of-cover thresholds driving country status
  thresholds: { ok: 60, watch: 30, alert: 12 },
  shutInRate: 0.25,       // how fast unsold output turns into shut-in wells
  restartRate: 0.10,      // how fast output returns once the route reopens
  // Reroute hysteresis: divert below this passability, come back above the other
  rerouteBelow: 0.50,
  rerouteBack: 0.85,
};
