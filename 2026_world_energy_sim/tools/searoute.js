/**
 * Offline sea router - build tooling, not part of the page.
 *
 * The route data names the waypoints a lane has to pass (ports, straits); the
 * line between two of them is a great circle, and a great circle happily cuts
 * across Yemen, Sumatra or Fujian. This finds the shortest *water* path for the
 * legs that do, and tools/build-detours.ps1 bakes the result into
 * js/data/sea-detours.js, which the renderer splices back in.
 *
 * Land comes from the same LAND rings the map draws, rasterised at 1/6 deg.
 * Straits narrower than a cell are painted back in by hand (CORRIDORS) - the
 * Bosphorus and the Suez canal are real sea lanes and a raster loses them.
 */

const RES = 6;                       // cells per degree
const GW = 360 * RES, GH = 180 * RES;
const CLEAR = 5;                     // cells of coastal clearance we aim for
const ENDPOINT_FREE = 0.5;          // deg around a waypoint where land is tolerated (ports, canals)
const MAX_SPAN = 3.4;                // deg between emitted detour points

// Sea lanes that a 1/6 deg raster closes off. Painted as water, ~2 cells wide.
const CORRIDORS = [
  [[31.40, 32.35], [30.60, 32.35], [29.95, 32.55]],                       // Suez canal
  [[29.95, 32.55], [29.40, 32.70], [28.50, 33.20], [27.70, 33.90]],       // Gulf of Suez
  [[41.10, 29.05], [40.95, 28.90], [40.60, 27.30], [40.20, 26.30], [39.90, 25.90]], // Bosphorus + Dardanelles
  [[9.40, -79.90], [9.00, -79.60], [8.85, -79.50], [8.40, -79.20]],       // Panama canal
  [[57.60, 10.60], [56.60, 11.00], [55.90, 11.00], [55.60, 12.70], [55.00, 13.40]], // Danish straits
  [[1.35, 103.55], [1.20, 104.05], [1.05, 104.60]],                       // Singapore strait
  [[35.95, -5.75], [35.95, -5.55], [36.00, -5.30]],                       // Gibraltar
  [[12.70, 43.10], [12.58, 43.33], [12.40, 43.60]],                       // Bab el-Mandeb
  [[26.57, 56.25], [26.30, 56.45], [26.00, 56.50]],                       // Hormuz
  [[40.90, 28.00], [40.70, 27.00]],                                       // Sea of Marmara
  [[49.00, -123.60], [48.65, -123.25], [48.30, -124.10], [48.42, -125.00], [48.50, -125.80]], // Juan de Fuca
];

// Legs that are meant to run overland: the bypass pipelines inside a sea route.
const ONSHORE = new Set([
  'ABQAIQ|PETRO_MID1', 'PETRO_MID1|PETRO_MID2', 'PETRO_MID2|YANBU',
  'HABSHAN|FUJAIRAH', 'KIRKUK|CEYHAN', 'TENGIZ|NOVOROSSIYSK',
]);

// --- raster -----------------------------------------------------------------
function buildMask() {
  const cv = document.createElement('canvas');
  cv.width = GW; cv.height = GH;
  const g = cv.getContext('2d', { willReadFrequently: true });
  g.fillStyle = '#000'; g.fillRect(0, 0, GW, GH);
  g.fillStyle = '#fff';
  for (const { ring } of LAND) {
    g.beginPath();
    for (let i = 0; i < ring.length; i++) {
      const x = (ring[i][0] + 180) * RES, y = (90 - ring[i][1]) * RES;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.closePath(); g.fill();
  }
  // carve the narrow lanes back out
  g.strokeStyle = '#000'; g.lineWidth = 3.6; g.lineJoin = 'round'; g.lineCap = 'round';
  for (const c of CORRIDORS) {
    g.beginPath();
    for (let i = 0; i < c.length; i++) {
      const x = (c[i][1] + 180) * RES, y = (90 - c[i][0]) * RES;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.stroke();
  }
  const px = g.getImageData(0, 0, GW, GH).data;
  const land = new Uint8Array(GW * GH);
  for (let i = 0; i < land.length; i++) land[i] = px[i * 4] > 100 ? 1 : 0;
  return land;
}

/** Cells to the nearest land cell, capped - the cost function uses it to keep
 *  lanes off the beach instead of scraping along every headland. */
function distanceField(land) {
  const d = new Uint8Array(GW * GH).fill(255);
  let frontier = [];
  for (let i = 0; i < land.length; i++) if (land[i]) { d[i] = 0; frontier.push(i); }
  for (let step = 1; step <= CLEAR + 1 && frontier.length; step++) {
    const next = [];
    for (const i of frontier) {
      const x = i % GW, y = (i / GW) | 0;
      for (let dy = -1; dy <= 1; dy++) {
        const ny = y + dy;
        if (ny < 0 || ny >= GH) continue;
        for (let dx = -1; dx <= 1; dx++) {
          const j = ny * GW + ((x + dx + GW) % GW);
          if (d[j] === 255) { d[j] = step; next.push(j); }
        }
      }
    }
    frontier = next;
  }
  return d;
}

// --- grid helpers -----------------------------------------------------------
const wrapLon = l => { let v = l; while (v < -180) v += 360; while (v >= 180) v -= 360; return v; };
const cellOf = (lat, lon) => {
  const x = Math.min(GW - 1, Math.max(0, Math.floor((wrapLon(lon) + 180) * RES)));
  const y = Math.min(GH - 1, Math.max(0, Math.floor((90 - lat) * RES)));
  return y * GW + x;
};
const latOfCell = i => 90 - (((i / GW) | 0) + 0.5) / RES;
const lonOfCell = i => (i % GW + 0.5) / RES - 180;

// --- binary heap ------------------------------------------------------------
class Heap {
  constructor() { this.k = []; this.v = []; }
  get size() { return this.v.length; }
  push(key, val) {
    this.k.push(key); this.v.push(val);
    let i = this.v.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this.k[p] <= this.k[i]) break;
      this._swap(p, i); i = p;
    }
  }
  pop() {
    const top = this.v[0], n = this.v.length - 1;
    this.k[0] = this.k[n]; this.v[0] = this.v[n];
    this.k.pop(); this.v.pop();
    let i = 0;
    while (true) {
      const l = 2 * i + 1, r = l + 1;
      let s = i;
      if (l < n && this.k[l] < this.k[s]) s = l;
      if (r < n && this.k[r] < this.k[s]) s = r;
      if (s === i) break;
      this._swap(s, i); i = s;
    }
    return top;
  }
  _swap(a, b) {
    const k = this.k[a]; this.k[a] = this.k[b]; this.k[b] = k;
    const v = this.v[a]; this.v[a] = this.v[b]; this.v[b] = v;
  }
}

// --- router -----------------------------------------------------------------
class SeaRouter {
  constructor() {
    this.land = buildMask();
    this.dist = distanceField(this.land);
    this.g = new Float32Array(GW * GH);
    this.from = new Int32Array(GW * GH);
    this.stamp = new Int32Array(GW * GH);
    this.closed = new Int32Array(GW * GH);
    this.run = 0;
  }

  /** true where the raster says land and no endpoint exemption applies */
  blocked(lat, lon, free) {
    if (!this.land[cellOf(lat, lon)]) return false;
    for (const f of free) if (arcDeg([lat, lon], f) < ENDPOINT_FREE) return false;
    return true;
  }

  /**
   * Does the great circle a->b touch land anywhere it is not excused?
   *
   * Routing tests one cell wider than the coastline (`margin`) while the final
   * verification tests the coastline itself. Without that slack the two sample
   * the same near-miss at slightly different points and disagree about it.
   */
  crosses(a, b, free, margin = true, step = 0.05) {
    const n = Math.max(1, Math.ceil(arcDeg(a, b) / step));
    for (let i = 0; i <= n; i++) {
      const p = arcAt(a, b, i / n);
      if (margin ? this.tooClose(p[0], p[1], free) : this.blocked(p[0], p[1], free)) return true;
    }
    return false;
  }

  tooClose(lat, lon, free) {
    if (this.dist[cellOf(lat, lon)] > 1) return false;
    for (const f of free) if (arcDeg([lat, lon], f) < ENDPOINT_FREE) return false;
    return true;
  }

  _water(lat, lon) {
    const c = cellOf(lat, lon);
    if (!this.land[c]) return c;
    // walk outwards for the nearest water cell - ports and canal mouths sit on land
    for (let r = 1; r <= ENDPOINT_FREE * RES + 3; r++) {
      for (let dy = -r; dy <= r; dy++) {
        for (let dx = -r; dx <= r; dx++) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue;
          const y = ((c / GW) | 0) + dy;
          if (y < 0 || y >= GH) continue;
          const j = y * GW + ((c % GW) + dx + GW) % GW;
          if (!this.land[j]) return j;
        }
      }
    }
    return -1;
  }

  /** A* through water from a to b; returns cell indices or null. */
  search(a, b) {
    this.lastFail = null;
    const start = this._water(a[0], a[1]), goal = this._water(b[0], b[1]);
    if (start < 0 || goal < 0) { this.lastFail = 'no water cell at endpoint'; return null; }
    const gy = (goal / GW) | 0, gx = goal % GW;
    const glat = latOfCell(goal), glon = lonOfCell(goal);

    const run = ++this.run;
    const heap = new Heap();
    this.g[start] = 0; this.from[start] = -1; this.stamp[start] = run;
    heap.push(0, start);

    // Octile distance, not straight-line: the grid only moves in 8 directions, so
    // a Euclidean heuristic underestimates by up to 8% and A* then ploughs through
    // half an ocean of equal-f cells. The 1.05 weight trades a hair of optimality
    // for a search that finishes.
    const H = i => {
      let dLon = Math.abs(lonOfCell(i) - glon);
      if (dLon > 180) dLon = 360 - dLon;
      const ax = dLon * Math.cos((latOfCell(i) + glat) / 2 * Math.PI / 180) * RES;
      const ay = Math.abs(latOfCell(i) - glat) * RES;
      const hi = Math.max(ax, ay), lo = Math.min(ax, ay);
      return 1.05 * (hi + 0.4142 * lo) / RES;
    };

    let guard = 0;
    while (heap.size) {
      if (++guard > 2e7) { this.lastFail = 'guard'; return null; }
      const cur = heap.pop();
      if (cur === goal) break;
      if (this.closed[cur] === run) continue;      // stale heap entry
      this.closed[cur] = run;
      const cy = (cur / GW) | 0, cx = cur % GW;
      const kx = Math.cos(latOfCell(cur) * Math.PI / 180);
      const gc = this.g[cur];
      for (let dy = -1; dy <= 1; dy++) {
        const ny = cy + dy;
        if (ny < 0 || ny >= GH) continue;
        for (let dx = -1; dx <= 1; dx++) {
          if (!dx && !dy) continue;
          const nx = (cx + dx + GW) % GW;
          const j = ny * GW + nx;
          if (this.land[j]) continue;
          const stepD = Math.hypot(dx * kx, dy) / RES;
          // hug the coast and the line looks wrong; this buys sea room
          const clear = Math.min(CLEAR, this.dist[j] === 255 ? CLEAR : this.dist[j]);
          const cost = stepD * (1 + 1.8 * (CLEAR - clear) / CLEAR);
          const ng = gc + cost;
          if (this.stamp[j] === run && this.g[j] <= ng) continue;
          this.stamp[j] = run; this.g[j] = ng; this.from[j] = cur;
          heap.push(ng + H(j), j);
        }
      }
    }
    if (this.stamp[goal] !== run) { this.lastFail = this.lastFail || 'goal unreachable'; return null; }
    const out = [];
    for (let i = goal; i !== -1; i = this.from[i]) out.push(i);
    return out.reverse();
  }

  /**
   * Detour points for one leg, or null if the straight great circle is fine.
   * The raw cell path is far too dense to ship, so it is reduced to the fewest
   * points whose connecting great circles all stay at sea.
   */
  detour(a, b) {
    const free = [a, b];
    if (!this.crosses(a, b, free)) return null;          // already at sea
    const cells = this.search(a, b);
    if (!cells) return { fail: this.lastFail || 'no path' };

    const pts = [a, ...cells.map(i => [latOfCell(i), lonOfCell(i)]), b];
    const keep = [pts[0]];
    let i = 0;
    while (i < pts.length - 1) {
      let j = pts.length - 1;
      // furthest point still reachable in a straight sea line, capped so that
      // the renderer never rounds the corner away
      for (; j > i + 1; j--) {
        if (arcDeg(pts[i], pts[j]) > MAX_SPAN) continue;
        if (!this.crosses(pts[i], pts[j], free)) break;
      }
      keep.push(pts[j]);
      i = j;
    }
    keep.shift(); keep.pop();                      // endpoints are the waypoints themselves

    // longitudes back onto the authored continuum (trans-Pacific legs live below -180)
    let prev = a[1];
    return keep.map(p => {
      let lon = p[1];
      while (lon - prev > 180) lon -= 360;
      while (prev - lon > 180) lon += 360;
      prev = lon;
      return [Math.round(p[0] * 100) / 100, Math.round(lon * 100) / 100];
    });
  }
}

const legKey = (a, b) => `${a[0]},${a[1]}|${b[0]},${b[1]}`;

/** Waypoint name for a coordinate pair, for ONSHORE lookups and reports. */
const WP_NAME = new Map();
for (const k in WP) WP_NAME.set(WP[k][0] + ',' + WP[k][1], k);
const wpName = p => WP_NAME.get(p[0] + ',' + p[1]) || `${p[0]},${p[1]}`;
const isOnshore = (a, b) => ONSHORE.has(wpName(a) + '|' + wpName(b)) || ONSHORE.has(wpName(b) + '|' + wpName(a));

/** Every sea leg in the model, deduplicated, in the order they are authored. */
function allSeaLegs() {
  const seen = new Set(), out = [];
  const add = path => {
    for (let i = 0; i < path.length - 1; i++) {
      const a = path[i], b = path[i + 1];
      if (isOnshore(a, b)) continue;
      const k = legKey(a, b);
      if (seen.has(k)) continue;
      seen.add(k);
      out.push({ key: k, a, b });
    }
  };
  for (const r of ROUTES) {
    if (r.mode !== 'sea') continue;
    add(r.path);
    for (const alt of (r.alts || [])) add(alt.path);
  }
  return out;
}
