/**
 * Preset scenarios - each one is a set of moves on chokepoints and routes.
 * apply() receives the engine; the UI appends a log entry afterwards.
 */
const SCENARIOS = [
  {
    id: 'baseline',
    name: 'Baseline',
    tag: 'reset',
    desc: 'All routes open. The world in equilibrium: supply ~ demand, price around 78 USD/bbl.',
    apply(e) {
      for (const k of Object.values(e.chokes)) k.userCap = 1;
      for (const r of Object.values(e.routes)) { r.userCap = r.disabled ? 0 : 1; r.altId = null; r.manualAlt = false; }
    },
  },
  {
    id: 'hormuz',
    name: 'Hormuz closed',
    tag: 'extreme',
    desc: 'Around 21 mb/d leaves the market in a single day. The only relief is Petroline (5 mb/d) and ADCOP (1.8 mb/d) - together under a third of what is needed.',
    apply(e) { e.setChokeCap('HORMUZ', 0); },
  },
  {
    id: 'hormuz_partial',
    name: 'Hormuz at 40%',
    tag: 'severe',
    desc: 'Insurers pull cover and traffic falls to 40%. Slower than a closure, but it drains Asian stocks relentlessly - and the bypass pipelines fill up.',
    apply(e) { e.setChokeCap('HORMUZ', 0.4); },
  },
  {
    id: 'redsea',
    name: 'Red Sea crisis',
    tag: 'realistic',
    desc: 'Bab el-Mandeb shut, Suez useless. Tankers go round the Cape of Good Hope: 12-16 extra days at sea and a gap in deliveries while the fleet repositions.',
    apply(e) { e.setChokeCap('BAB', 0); e.setChokeCap('SUEZ', 0.15); },
  },
  {
    id: 'malacca',
    name: 'Malacca blockade',
    tag: 'extreme',
    desc: 'The gateway to East Asia closes. Lombok and Makassar absorb the traffic at a cost of 3-4 days, but China, Japan and South Korea lose continuity of supply.',
    apply(e) { e.setChokeCap('MALACCA', 0); },
  },
  {
    id: 'russia',
    name: 'Hard sanctions on Russia',
    tag: 'geopolitical',
    desc: 'Baltic and Black Sea exports cut off, leaving only ESPO going east. Russia fills its tanks and starts shutting in wells.',
    apply(e) { ['RUS-IND', 'RUS-CHN-BALTIC', 'RUS-TUR'].forEach(id => e.setRouteCap(id, 0)); },
  },
  {
    id: 'turkish',
    name: 'Turkish Straits closed',
    tag: 'regional',
    desc: 'Caspian (CPC) and Russian Black Sea crude have no way out. There is no real maritime bypass - Italy and Turkey feel it immediately.',
    apply(e) { e.setChokeCap('TURKISH', 0); },
  },
  {
    id: 'gulf_war',
    name: 'War in the Gulf',
    tag: 'extreme',
    desc: 'Hormuz closed, Bab el-Mandeb at 30%, Iraqi and Iranian exports halted. The scenario that tests the limits of the model.',
    apply(e) {
      e.setChokeCap('HORMUZ', 0);
      e.setChokeCap('BAB', 0.3);
      ['IRQ-CHN', 'IRQ-IND', 'IRQ-ITA', 'IRN-CHN'].forEach(id => e.setRouteCap(id, 0));
    },
  },
  {
    id: 'druzhba',
    name: 'Druzhba returns',
    tag: 'reverse',
    desc: 'Russian pipeline deliveries to Poland and Germany restored (0.6 mb/d). Shows the model running the other way - surplus instead of deficit.',
    apply(e) { e.routes['RUS-POL-PIPE'].vol = 0.60; e.setRouteCap('RUS-POL-PIPE', 1); },
  },
];
