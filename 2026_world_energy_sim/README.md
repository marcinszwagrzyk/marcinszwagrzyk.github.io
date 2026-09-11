# World Oil Routes

Interactive simulation of the seaborne oil trade. Cut a chokepoint or throttle a
route, let the clock run (1–30 days per second), and watch the deficit travel
through the system: first empty tankers, then draining stocks, then unmet demand
and a price spike.

**Run it:** open `index.html` in a browser. No build step, no server, no network —
the world geometry and every asset are embedded.

**Published:** https://claude.ai/code/artifact/a6be50c3-b82b-42d9-b9ec-c067a1077b3c

---

## What is modelled

| | Count | Scope |
|---|---|---|
| Countries | 34 | 15 net exporters, 17 net importers, 2 hybrids (USA, Mexico) |
| Routes | 51 | 46 seaborne + 5 pipelines, 33.9 mb/d combined |
| Chokepoints | 9 | Hormuz, Malacca, Suez, Bab el-Mandeb, Turkish Straits, Danish Straits, Panama, Cape of Good Hope, Gibraltar |
| Reroute variants | 28 | Cape, Lombok/Makassar, and the bypass pipelines |
| Bypass pipelines | 3 | Petroline 5.0, ADCOP 1.8, Kirkuk–Ceyhan 0.5 mb/d |
| Scenarios | 9 | from a Hormuz closure to Druzhba coming back |

Modelled routes carry **75% of the trade** across this set of countries. The rest
is dispersed spot trade, which the engine treats as background supply: it cannot
be severed by one cut, but it shrinks in a global shortage.

## Reading the map

Each country is one glyph — its entire energy balance in a single mark, so all 34
read at once without clicking:

- **disc size** — consumption (the US and China dominate; Angola is a dot)
- **wedges** — what covers *today's* demand:
  green own output · blue imports · amber drawn from stocks · red unmet
- **ring** — importer: days of cover left (full = 90+); exporter: share of exports
  actually moving
- **pulsing halo** — real shortfall, not merely thinning stocks

Routes are drawn as a **flow ribbon**: width is the volume itself, linear, so
2 mb/d reads as twice 1 mb/d. Each route has two bands — a dim one sized by the
baseline volume and a bright one sized by today's flow. The gap between them is
the loss. Pipelines are violet and dashed; idle ones stay hairlines and thicken
only when they start carrying oil.

**Click anything to trace it.** A country lights up its supply and export routes
and the partners on the other end. A chokepoint lights up every route through it
plus every country behind them, and the inspector ranks those countries by how
much of their demand (or exports) rides on that single passage.

## Mechanics that matter

**Transit time.** Crude from Ras Tanura to Ningbo sails 22 days. Closing Hormuz
today does not stop deliveries in China today — it stops them in three weeks.
Tankers already at sea arrive. This is the single most important property of the
model and the main reason to watch the clock.

**Diversions cost something.** Round the Cape is 12–16 extra days. Petroline
clears Hormuz but carries 5 mb/d against roughly 6 mb/d of Saudi traffic that
would need it, so every route on it gets about 83% and no more. ADCOP adds 1.8.
Shippers divert once passability drops below 50% and only return above 85%, so
the fleet does not flip-flop day to day.

**Exporters suffer too.** Oil with no buyer goes to storage; once storage fills,
wells get shut in, and shut-in output comes back slowly. Blocking the Baltic hits
Russia differently than it hits India, but it hits.

**Price from the supply gap.** Short-run price elasticity of oil demand is about
−0.05, so a 1% gap moves price roughly +20%. Deep stocks damp the shock, empty
ones amplify it, and a high price suppresses demand — the only brake in the model.

## Controls

| Action | Where |
|---|---|
| Play / pause | ▶ button or **space** |
| Speed 1/3/10/30 days per second | buttons or keys **1–4** |
| Throttle a chokepoint | slider in the Chokepoints tab, or click the diamond on the map |
| Throttle a route | Routes tab, or click the ribbon |
| Force a diversion | route inspector → Reroute |
| Release reserves | country inspector (importers only) |
| Preset crisis | Scenarios tab |

## Data

Reference year **2024**, unit **mb/d** (million barrels per day, total liquids).
Figures are deliberately rounded — this is a teaching model.

- **Production and consumption** — EI Statistical Review of World Energy 2025,
  EIA International Energy Statistics
- **Chokepoint throughput** — EIA *World Oil Transit Chokepoints* (2023):
  Malacca 23.7 · Hormuz 20.9 · Suez+SUMED 9.2 · Bab el-Mandeb 8.7 ·
  Turkish Straits 3.3 · Danish Straits 3.2 · Panama 1.0
- **Stocks** — the IEA 90-day net-import obligation plus commercial inventories,
  which is why Japan holds ~200 days and Nigeria ~15
- **Route directions and volumes** — published crude flow tabulations, rounded to
  0.05 mb/d
- **Country boundaries** — Natural Earth 1:50m admin-0, Douglas-Peucker simplified
  to 39k points (plus a 9.5k coarse level for the zoomed-out view) and packed as
  delta-encoded strings

The modelled world carries a +3.45 mb/d surplus, because 34 countries are not the
whole planet (the missing buyers sit outside the grid). Price is therefore
measured as the **deviation** from that equilibrium rather than in absolute terms —
otherwise small disruptions would fall into a dead zone and never move it.

## Structure

```
index.html               layout, and the map key that explains every mark
css/main.css             dark instrument theme
js/data/world-shapes.js  Natural Earth 1:50m country boundaries, packed, 152 KB
js/data/world.js         countries, chokepoints, 118 waypoints, bypass pipelines, model constants
js/data/routes.js        51 routes with paths and reroute variants
js/data/sea-detours.js   generated: the extra points that keep each leg at sea
js/data/scenarios.js     9 preset crises
js/engine.js             daily simulation (balance, transit, stocks, price)
js/mapview.js            Web Mercator renderer on two canvases, no mapping library
js/ui.js                 panels, balance table, chart, event log
js/app.js                simulation clock and animation loop
build.ps1 / build.py     inline everything into dist/ as one self-contained file
tools/build-shapes.ps1   regenerates world-shapes.js from Natural Earth
tools/build-detours.ps1  regenerates sea-detours.js and verifies every lane
tools/searoute.js        the offline A* sea router the generator runs
tools/shot.ps1           screenshots the app in headless Edge
```

## How the lanes are drawn

A route is authored as the waypoints it has to pass - load port, straits,
discharge port. Between two of them the line is a **great circle**, sampled every
1.5 degrees of arc, which is why the ocean crossings arc polewards the way a ship
actually steers; corners between two long legs are eased into a short arc, while a
waypoint sitting in a strait keeps its exact position.

A great circle is indifferent to coastlines, and the authored ones happily cut
across Yemen, Sumatra and Fujian. `tools/build-detours.ps1` rasterises the same
boundaries the map draws at 1/6 degree, runs A* through the water for every leg
that touches land - with a cost that buys clearance from the coast, and hand-cut
corridors for the lanes a raster loses (Suez, Bosphorus, Panama, the Danish
straits) - and bakes the result into `js/data/sea-detours.js`. The renderer
splices those points back in, so the data keeps its readable shape and the drawn
lane stays at sea. The generator verifies its own output: it redraws every route
exactly as the map does and reports any sample still on land.

Routes that share a corridor - the Mediterranean, the Red Sea, Malacca - are
then dealt **parallel lanes** rather than being stacked on one line, so the
bundle's thickness is the corridor's total flow and each route stays pickable.
Lanes are ordered by one global route order applied identically on every leg, so
two routes running together never swap sides; a route peels off smoothly where it
leaves the bundle. The sideways shift is in pixels and capped (13 px), because
fifteen routes share the Hormuz leg and the strait is 0.4 degrees wide - a lane
can therefore sit a little off its verified centreline at low zoom, where the
coastline is a few pixels wide anyway.

Every country's balance closes by construction:

```
supply = own output + route arrivals + off-model supply
use    = consumption + route departures + off-model sales
difference → stocks
```

Nothing appears from nowhere and nothing vanishes — if a country ships oil, it
had to produce or receive it first.

## Verification

There is no Node.js or Python on the development machine, so the JavaScript is
run through headless Edge instead:

- `tools/build-detours.ps1` loads the real renderer and the real data, redraws
  every route and every reroute variant, and reports any point that ends up on
  land. A clean run prints `VERIFY CLEAN`.
- `tools/shot.ps1` screenshots the running app (optionally after steering the
  view, e.g. `-Setup "w.app.view.flyTo(16, 68, 4.2)"`), which is how the map is
  checked without a browser open.

Both catch reference and structural errors as a side effect - the page cannot
load at all if something is broken - but not simulation behaviour; open the page
to confirm that.
