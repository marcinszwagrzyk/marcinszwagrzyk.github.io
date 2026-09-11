/**
 * Self-contained map renderer - Web Mercator on two stacked canvases.
 * No tile server, no mapping library: the page must work as a single file.
 *
 *   base canvas  - land polygons, redrawn only when the view changes
 *   fx canvas    - routes, tankers, chokepoints, country glyphs; every frame
 *
 * A country glyph is its whole energy balance in one mark, so all 34 read
 * at once without clicking:
 *   disc size   = consumption
 *   pie wedges  = what covers today's demand
 *                 (green own output / blue imports / amber stocks / red unmet)
 *   ring        = importer: days of cover left; exporter: share of exports moving
 */

// Canvas mirrors the CSS type split: labels in the UI face, figures in the readout face.
const F_UI = '"Segoe UI", system-ui, sans-serif';
const F_READ = 'ui-monospace, "Cascadia Mono", Consolas, monospace';

// Drawn content spans wider than one world: trans-Pacific route legs are authored
// with longitudes below -180 so the lines stay continuous across the antimeridian.
const CONTENT_MIN = -0.2;
const CONTENT_MAX = 1.0;

function bboxOf(path) {
  let minWx = Infinity, maxWx = -Infinity, minWy = Infinity, maxWy = -Infinity;
  for (const [lat, lon] of path) {
    const wx = wxOf(lon), wy = wyOf(lat);
    if (wx < minWx) minWx = wx;
    if (wx > maxWx) maxWx = wx;
    if (wy < minWy) minWy = wy;
    if (wy > maxWy) maxWy = wy;
  }
  return { minWx, maxWx, minWy, maxWy };
}

function bboxOfLonLat(ring) {
  let minWx = Infinity, maxWx = -Infinity, minWy = Infinity, maxWy = -Infinity;
  for (const [lon, lat] of ring) {
    const wx = wxOf(lon), wy = wyOf(lat);
    if (wx < minWx) minWx = wx;
    if (wx > maxWx) maxWx = wx;
    if (wy < minWy) minWy = wy;
    if (wy > maxWy) maxWy = wy;
  }
  return { minWx, maxWx, minWy, maxWy };
}

const COL = {
  ok: '#3fc98b', watch: '#e0c341', alert: '#f09033', crisis: '#ef4b5c',
  flow: '#35c7d6', imp: '#4a8fe0', pipe: '#b07be0', track: '#1c2735',
  shutin: '#b07be0',
  ocean: '#070d15', land: '#18242f', coast: '#4d7aa2',
  // the lanes themselves run a shade lighter than the UI accent they share a
  // meaning with - a ribbon is a big area of colour, a diamond is a few pixels
  flowLine: '#5cd8e3', pipeLine: '#c096e9', ghost: '#5a7691',
  landOn: '#1f2e3d',            // one of the 34 modelled countries
  landSel: '#2b4159',           // the selected one
  halo: '#2e7aa8',              // coastal glow, only where land meets water
  border: '#35526f',
  grid: 'rgba(86,132,178,.055)',
};

// --- projection -------------------------------------------------------------
const wxOf = lon => (lon + 180) / 360;
const wyOf = lat => {
  const s = Math.sin(Math.max(-85, Math.min(85, lat)) * Math.PI / 180);
  return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
};
const lonOf = wx => wx * 360 - 180;
const latOf = wy => {
  const n = Math.PI * (1 - 2 * wy);
  return 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
};

// --- great-circle geometry --------------------------------------------------
// Waypoints say where a route has to pass; the line between two of them is the
// route a ship actually steers - a great circle, not a straight line on the
// Mercator sheet. Every leg is therefore sampled along its orthodrome, which is
// why the long ocean crossings arc polewards instead of running flat.
const D2R = Math.PI / 180, R2D = 180 / Math.PI;

const ARC_STEP = 1.5;    // degrees of arc between sampled vertices
const ROUND_MIN = 4.0;   // only corners between legs this long get rounded
const ROUND_MAX = 1.1;   // and never by more than this (degrees of arc)

/** Great-circle distance in degrees. */
function arcDeg(p1, p2) {
  const f1 = p1[0] * D2R, f2 = p2[0] * D2R;
  let dLon = p2[1] - p1[1];
  while (dLon > 180) dLon -= 360;
  while (dLon < -180) dLon += 360;
  const sh = Math.sin((f2 - f1) / 2), sl = Math.sin(dLon * D2R / 2);
  return 2 * Math.asin(Math.min(1, Math.sqrt(sh * sh + Math.cos(f1) * Math.cos(f2) * sl * sl))) * R2D;
}

/**
 * Point at fraction t of the great circle p1 -> p2.
 *
 * Longitude comes back as p1's longitude plus the travelled angle, never
 * re-wrapped: the trans-Pacific legs are authored with longitudes below -180 so
 * the line stays continuous across the antimeridian, and that has to survive.
 */
function arcAt(p1, p2, t) {
  const f1 = p1[0] * D2R, f2 = p2[0] * D2R;
  let dLon = p2[1] - p1[1];
  while (dLon > 180) dLon -= 360;
  while (dLon < -180) dLon += 360;
  const dl = dLon * D2R;
  const sh = Math.sin((f2 - f1) / 2), sl = Math.sin(dl / 2);
  const d = 2 * Math.asin(Math.min(1, Math.sqrt(sh * sh + Math.cos(f1) * Math.cos(f2) * sl * sl)));
  const sd = Math.sin(d);
  if (sd < 1e-9) return [p1[0] + (p2[0] - p1[0]) * t, p1[1] + dLon * t];
  const A = Math.sin((1 - t) * d) / sd, B = Math.sin(t * d) / sd;
  const x = A * Math.cos(f1) + B * Math.cos(f2) * Math.cos(dl);
  const y = B * Math.cos(f2) * Math.sin(dl);
  const z = A * Math.sin(f1) + B * Math.sin(f2);
  return [Math.atan2(z, Math.hypot(x, y)) * R2D, p1[1] + Math.atan2(y, x) * R2D];
}

function arcInto(p1, p2, out) {
  const n = Math.max(1, Math.ceil(arcDeg(p1, p2) / ARC_STEP));
  for (let i = 1; i <= n; i++) out.push(arcAt(p1, p2, i / n));
}

function quadInto(p0, c, p1, out) {
  for (let i = 1; i <= 10; i++) {
    const t = i / 10, u = 1 - t, a = u * u, b = 2 * u * t, d = t * t;
    out.push([a * p0[0] + b * c[0] + d * p1[0], a * p0[1] + b * c[1] + d * p1[1]]);
  }
}

/**
 * Splices in the land-avoiding detours from js/data/sea-detours.js.
 *
 * The route data names the waypoints a lane must pass; between two of them the
 * great circle is free to cut across Yemen or Sumatra. tools/build-detours.ps1
 * routes those legs around the coastline offline and the result is spliced back
 * in here, so what is drawn stays at sea without the data losing its shape.
 */
function expandPath(wps) {
  const pts = [wps[0]], legs = [];
  for (let i = 1; i < wps.length; i++) {
    const a = wps[i - 1], b = wps[i];
    const pa = `${a[0]},${a[1]}`, pb = `${b[0]},${b[1]}`;
    // Direction-free key, so the two directions of a corridor share one bundle,
    // plus the sign that says which way this route runs along it.
    const tag = pa < pb ? { k: pa + '|' + pb, s: 1 } : { k: pb + '|' + pa, s: -1 };
    const d = typeof SEA_DETOURS !== 'undefined' && SEA_DETOURS[pa + '|' + pb];
    if (d) for (const p of d) { pts.push(p); legs.push(tag); }
    pts.push(b); legs.push(tag);
  }
  return { pts, legs };
}

/**
 * Waypoint list -> drawable path: every leg on its great circle, and corners
 * between two long legs eased with a short arc instead of a hard kink.
 *
 * Corners are only rounded where there is room for it. A waypoint sitting in a
 * strait or a port approach has short legs on at least one side, and those keep
 * their exact position - the line still threads Hormuz, Malacca and Suez.
 */
function geoPath(wps) { return geoPathTagged(wps).path; }

/**
 * As geoPath, but every emitted point also carries the authored leg it came
 * from (`tags[i]`, or the leg index when no tags are given). That is what lets
 * the renderer know which bundle a piece of line belongs to.
 */
function geoPathTagged(wps, tags) {
  const n = wps.length;
  const tagOf = i => (tags ? tags[i] : i);
  if (n < 2) return { path: wps.slice(), tag: wps.map(() => tagOf(0)) };

  const len = [];
  for (let i = 0; i < n - 1; i++) len.push(Math.max(1e-6, arcDeg(wps[i], wps[i + 1])));
  const r = new Array(n).fill(0);
  for (let i = 1; i < n - 1; i++) {
    if (len[i - 1] < ROUND_MIN || len[i] < ROUND_MIN) continue;
    r[i] = Math.min(0.18 * len[i - 1], 0.18 * len[i], ROUND_MAX);
  }

  const out = [], tag = [];
  for (let i = 0; i < n - 1; i++) {
    const A = wps[i], B = wps[i + 1];
    const s = r[i] / len[i], e = r[i + 1] / len[i];
    const P0 = s > 0 ? arcAt(A, B, s) : A;
    const P1 = e > 0 ? arcAt(A, B, 1 - e) : B;
    if (!out.length) out.push(P0);
    arcInto(P0, P1, out);
    if (r[i + 1] > 0) {
      const C = wps[i + 2];
      quadInto(P1, B, arcAt(B, C, r[i + 1] / len[i + 1]), out);
    }
    while (tag.length < out.length) tag.push(tagOf(i));
  }
  return { path: out, tag };
}

// Lane spacing. A lane is narrower than the ribbon it carries, so a busy bundle
// overlaps a little rather than sprawling, and the whole bundle is capped: at
// Hormuz fifteen routes share one leg, and a strait is 0.4 degrees wide.
const LANE_PITCH = 0.6;    // share of a route's ribbon width its lane reserves
const LANE_GAP = 1.4;      // px of air between neighbouring lanes
const LANE_MAX = 13;       // px, half-width of the widest bundle

/**
 * Softens the steps in a per-point offset array. A route that leaves a bundle
 * would otherwise jump sideways at the waypoint where it parts company; this
 * spreads the move over a stretch of line so lanes peel off instead.
 */
function smoothOffsets(v, passes = 6) {
  let a = v.slice(), b = new Array(v.length);
  const last = v.length - 1;
  for (let p = 0; p < passes; p++) {
    for (let i = 0; i <= last; i++) {
      b[i] = 0.25 * a[i > 0 ? i - 1 : 0] + 0.5 * a[i] + 0.25 * a[i < last ? i + 1 : last];
    }
    const t = a; a = b; b = t;
  }
  return a;
}

// --- path geometry ----------------------------------------------------------
function pathLengths(path) {
  const segs = [];
  let total = 0;
  for (let i = 1; i < path.length; i++) {
    const [y1, x1] = path[i - 1], [y2, x2] = path[i];
    const dx = (x2 - x1) * Math.cos((y1 + y2) / 2 * Math.PI / 180);
    const d = Math.hypot(dx, y2 - y1) || 1e-6;
    segs.push(d); total += d;
  }
  return { segs, total };
}

/** Position at fraction t along a path, plus the segment it fell on. */
function pointAt(path, meta, t) {
  const target = Math.max(0, Math.min(1, t)) * meta.total;
  let acc = 0;
  for (let i = 0; i < meta.segs.length; i++) {
    if (acc + meta.segs[i] >= target) {
      const f = (target - acc) / meta.segs[i];
      const [y1, x1] = path[i], [y2, x2] = path[i + 1];
      return [y1 + (y2 - y1) * f, x1 + (x2 - x1) * f, i, f];
    }
    acc += meta.segs[i];
  }
  const last = path.length - 1;
  return [path[last][0], path[last][1], Math.max(0, last - 1), 1];
}

function distToSeg(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  let t = len2 ? ((px - x1) * dx + (py - y1) * dy) / len2 : 0;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

// ============================================================================
class MapView {
  constructor(engine, handlers) {
    this.engine = engine;
    this.h = handlers || {};
    this.selected = null;
    this.hover = null;
    this.reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    this.base = document.getElementById('mapbase');
    this.fx = document.getElementById('mapfx');
    this.wrap = document.getElementById('map');
    this.tip = document.getElementById('tooltip');

    this.zoom = 2.4;
    this.cx = wxOf(52);
    this.cy = wyOf(26);
    this.routeState = {};
    this.anim = null;
    this.baseDirty = true;

    this._wire();
    this.resize();
  }

  get worldPx() { return 256 * Math.pow(2, this.zoom); }

  toScreen(wx, wy, k = 0) {
    const s = this.worldPx;
    return [(wx + k - this.cx) * s + this.W / 2, (wy - this.cy) * s + this.H / 2];
  }

  fromScreen(px, py) {
    const s = this.worldPx;
    return [(px - this.W / 2) / s + this.cx, (py - this.H / 2) / s + this.cy];
  }

  /**
   * Which integer world copies overlap the viewport (this is what keeps the
   * antimeridian continuous). Content runs wider than one world: trans-Pacific
   * legs use longitudes below -180, so they reach wx = -0.2.
   * Copy k covers [k + CONTENT_MIN, k + CONTENT_MAX]; keep only the ones that
   * actually intersect the view - a padded guess costs 2-3 redundant redraws
   * of every route, every frame.
   */
  visibleCopies() {
    const s = this.worldPx;
    const left = this.cx - (this.W / 2) / s;
    const right = this.cx + (this.W / 2) / s;
    const out = [];
    for (let k = Math.ceil(left - CONTENT_MAX); k <= Math.floor(right - CONTENT_MIN); k++) out.push(k);
    return out.length ? out : [0];
  }

  /** Screen-space reject for a whole path on a given world copy. */
  _copyVisible(bb, k) {
    const s = this.worldPx, pad = 40;
    const x1 = (bb.minWx + k - this.cx) * s + this.W / 2;
    const x2 = (bb.maxWx + k - this.cx) * s + this.W / 2;
    if (x2 < -pad || x1 > this.W + pad) return false;
    const y1 = (bb.minWy - this.cy) * s + this.H / 2;
    const y2 = (bb.maxWy - this.cy) * s + this.H / 2;
    return !(y2 < -pad || y1 > this.H + pad);
  }

  // ---------------- interaction ----------------
  _wire() {
    const el = this.fx;
    let dragging = false, moved = 0, lastX = 0, lastY = 0;

    el.addEventListener('mousedown', e => {
      dragging = true; moved = 0; lastX = e.clientX; lastY = e.clientY;
      el.style.cursor = 'grabbing';
      this.anim = null;
      this.hover = null;               // panning is not hovering
    });
    window.addEventListener('mouseup', e => {
      if (dragging && moved < 4) this._click(e);
      dragging = false; el.style.cursor = '';
    });
    window.addEventListener('mousemove', e => {
      if (dragging) {
        const dx = e.clientX - lastX, dy = e.clientY - lastY;
        moved += Math.abs(dx) + Math.abs(dy);
        lastX = e.clientX; lastY = e.clientY;
        this.cx -= dx / this.worldPx;
        this.cy -= dy / this.worldPx;
        this._clampY();
        this.baseDirty = true;   // repainted once in the next frame, not per event
      } else {
        this._hover(e);
      }
    });
    // the cursor leaving the canvas has to drop the hover too, or the map stays
    // faded out while you are over a panel
    el.addEventListener('mouseleave', () => { this.hover = null; this._hideTip(); });
    el.addEventListener('wheel', e => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      this.zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 0.4 : -0.4);
    }, { passive: false });

    window.addEventListener('resize', () => this.resize());

    const zi = document.getElementById('zoomIn'), zo = document.getElementById('zoomOut');
    if (zi) zi.addEventListener('click', () => this.zoomAt(this.W / 2, this.H / 2, 0.7));
    if (zo) zo.addEventListener('click', () => this.zoomAt(this.W / 2, this.H / 2, -0.7));
  }

  zoomAt(px, py, dz) {
    const before = this.fromScreen(px, py);
    this.zoom = Math.max(1.2, Math.min(7, this.zoom + dz));
    const after = this.fromScreen(px, py);
    this.cx += before[0] - after[0];
    this.cy += before[1] - after[1];
    this._clampY();
    this.baseDirty = true;
  }

  _clampY() {
    const half = (this.H / 2) / this.worldPx;
    this.cy = Math.max(half * 0.2, Math.min(1 - half * 0.2, this.cy));
  }

  resize() {
    const r = this.wrap.getBoundingClientRect();
    this.W = r.width; this.H = r.height;
    const dpr = window.devicePixelRatio || 1;
    this.dpr = dpr;
    for (const c of [this.base, this.fx]) {
      c.width = Math.round(this.W * dpr); c.height = Math.round(this.H * dpr);
      c.style.width = this.W + 'px'; c.style.height = this.H + 'px';
    }
    this.baseDirty = true;
  }

  flyTo(lat, lon, zoom) {
    this.anim = {
      t0: performance.now(), dur: 650,
      from: { cx: this.cx, cy: this.cy, z: this.zoom },
      to: { cx: wxOf(lon), cy: wyOf(lat), z: Math.max(this.zoom, zoom || 3.6) },
    };
  }

  _tickAnim() {
    if (!this.anim) return;
    const p = Math.min(1, (performance.now() - this.anim.t0) / this.anim.dur);
    const e = p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    const { from, to } = this.anim;
    this.cx = from.cx + (to.cx - from.cx) * e;
    this.cy = from.cy + (to.cy - from.cy) * e;
    this.zoom = from.z + (to.z - from.z) * e;
    this._clampY();
    this.baseDirty = true;
    if (p >= 1) this.anim = null;
  }

  focus(id) {
    const c = this.engine.countries[id];
    if (c) this.flyTo(c.lat, c.lon, 3.8);
  }

  // ---------------- base layer: land ----------------
  /**
   * Country rings for the current zoom, with a screen-reject box each.
   * LAND_LOW is a heavily simplified copy of the same boundaries: below the
   * threshold the detail is smaller than a pixel, and it is 8x cheaper to draw.
   */
  _landSet() {
    const key = this.zoom >= 3 ? 'fine' : 'low';
    if (!this._land) this._land = {};
    if (!this._land[key]) {
      this._land[key] = (key === 'fine' ? LAND : LAND_LOW).map(p => ({
        iso: p.iso,
        ring: p.ring,
        bb: bboxOfLonLat(p.ring),
        modelled: !!this.engine.countries[p.iso],
      }));
    }
    return this._land[key];
  }

  /** Faint lat/lon grid, drawn on the water and painted over by the land. */
  _graticule(ctx, copies) {
    const step = this.zoom >= 4.5 ? 10 : this.zoom >= 3 ? 15 : 30;
    ctx.strokeStyle = COL.grid;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let lat = -80; lat <= 80; lat += step) {
      const y = this.toScreen(0, wyOf(lat))[1];
      if (y < 0 || y > this.H) continue;
      ctx.moveTo(0, y); ctx.lineTo(this.W, y);
    }
    for (const k of copies) {
      for (let lon = -180; lon < 180; lon += step) {
        const x = this.toScreen(wxOf(lon), 0, k)[0];
        if (x < 0 || x > this.W) continue;
        ctx.moveTo(x, 0); ctx.lineTo(x, this.H);
      }
    }
    ctx.stroke();
  }

  drawBase() {
    if (!this.W) return;
    const ctx = this.base.getContext('2d');
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);

    const sea = ctx.createLinearGradient(0, 0, 0, this.H);
    sea.addColorStop(0, '#060c15');
    sea.addColorStop(0.55, '#081220');
    sea.addColorStop(1, '#060b13');
    ctx.fillStyle = sea;
    ctx.fillRect(0, 0, this.W, this.H);

    const copies = this.visibleCopies();
    this._graticule(ctx, copies);

    const selId = this.selected && this.selected.type === 'country' ? this.selected.id : null;

    // One Path2D per visible ring, reused by all five passes below.
    const paths = [];
    for (const k of copies) {
      for (const L of this._landSet()) {
        if (!this._copyVisible(L.bb, k)) continue;
        const p = new Path2D();
        let px = 0, py = 0, on = false;
        for (let i = 0; i < L.ring.length; i++) {
          const [x, y] = this.toScreen(wxOf(L.ring[i][0]), wyOf(L.ring[i][1]), k);
          // skip vertices that would land on the pixel we are already at
          if (on && Math.abs(x - px) < 0.4 && Math.abs(y - py) < 0.4) continue;
          on ? p.lineTo(x, y) : p.moveTo(x, y);
          on = true; px = x; py = y;
        }
        p.closePath();
        paths.push({ p, L });
      }
    }

    // Halo and coastline go UNDER the fills on purpose: along an inland border
    // the neighbour paints over them, so the glow survives only where land
    // actually meets water. Coasts read as coasts, borders as hairlines.
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.strokeStyle = COL.halo;
    ctx.lineWidth = 9; ctx.globalAlpha = 0.09;
    for (const q of paths) ctx.stroke(q.p);
    ctx.lineWidth = 3.5; ctx.globalAlpha = 0.15;
    for (const q of paths) ctx.stroke(q.p);
    ctx.strokeStyle = COL.coast;
    ctx.lineWidth = 1.4; ctx.globalAlpha = 0.9;
    for (const q of paths) ctx.stroke(q.p);

    ctx.globalAlpha = 1;
    for (const q of paths) {
      ctx.fillStyle = q.L.iso === selId ? COL.landSel : q.L.modelled ? COL.landOn : COL.land;
      ctx.fill(q.p);
    }

    ctx.strokeStyle = COL.border;
    ctx.lineWidth = 0.6; ctx.globalAlpha = 0.6;
    for (const q of paths) ctx.stroke(q.p);
    ctx.globalAlpha = 1;
  }

  // ---------------- route bookkeeping ----------------
  _variantKey(r) { return (r.altId || 'main'); }

  _ensureRoute(r) {
    const key = this._variantKey(r);
    let st = this.routeState[r.id];
    if (st && st.key === key) return st;

    const ex = expandPath(this.engine._pathOf(r));
    const g = geoPathTagged(ex.pts, ex.legs);
    const path = g.path;
    const meta = pathLengths(path);
    const n = Math.max(2, Math.min(9, Math.round(r.vol * 3.2)));
    const tankers = [];
    const prev = st ? st.tankers : null;
    for (let i = 0; i < n; i++) {
      tankers.push({ phase: prev && prev[i] ? prev[i].phase : i / n, active: true });
    }
    st = { key, path, meta, tankers, bbox: bboxOf(path), tag: g.tag, off: null,
           r: r.mode === 'pipe' ? 1.5 : 1.5 + Math.sqrt(r.vol) * 1.1 };
    this.routeState[r.id] = st;
    this._laneSig = null;                     // geometry changed - lanes must be redealt
    return st;
  }

  /**
   * Deals every route a lane inside the corridors it shares with others, so the
   * Mediterranean, the Red Sea or Malacca carry a combed bundle of parallel
   * lines instead of one line with five routes hidden under it. The width of
   * the bundle is then the total flow through that corridor.
   *
   * Lanes are ordered by one global route order, applied identically on every
   * leg: two routes that run together never swap sides, so the bundle stays
   * parallel and only fans out where routes actually join or leave.
   */
  /**
   * Projects a route onto world copy k and pushes every point sideways into its
   * lane. The shift is in screen space and in pixels, so a bundle keeps the same
   * spacing at every zoom instead of collapsing when you pull back.
   */
  _laneScreen(st, k) {
    const n = st.path.length;
    if (!this._sx || this._sx.length < n) {
      this._sx = new Float64Array(n * 2); this._sy = new Float64Array(n * 2);
      this._lx = new Float64Array(n * 2); this._ly = new Float64Array(n * 2);
    }
    const sx = this._sx, sy = this._sy, lx = this._lx, ly = this._ly;
    for (let i = 0; i < n; i++) {
      const p = this.toScreen(wxOf(st.path[i][1]), wyOf(st.path[i][0]), k);
      sx[i] = p[0]; sy[i] = p[1];
    }
    for (let i = 0; i < n; i++) {
      const o = st.off ? st.off[i] : 0;
      if (!o) { lx[i] = sx[i]; ly[i] = sy[i]; continue; }
      const a = i > 0 ? i - 1 : 0, b = i < n - 1 ? i + 1 : n - 1;
      const dx = sx[b] - sx[a], dy = sy[b] - sy[a];
      const d = Math.hypot(dx, dy) || 1;
      lx[i] = sx[i] - dy / d * o;             // left normal of the travel direction
      ly[i] = sy[i] + dx / d * o;
    }
    return n;
  }

  _lanePath(st, k) {
    const n = this._laneScreen(st, k);
    const p = new Path2D();
    for (let i = 0; i < n; i++) i ? p.lineTo(this._lx[i], this._ly[i]) : p.moveTo(this._lx[i], this._ly[i]);
    return p;
  }

  _relane() {
    const routes = Object.values(this.engine.routes);
    const sig = routes.map(r => r.id + ':' + this._variantKey(r)).join(',');
    if (this._laneSig === sig) return;

    const ordered = routes.slice().sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const lane = r => ribbon(r.vol) * LANE_PITCH + LANE_GAP;

    const total = new Map();
    for (const r of ordered) {
      for (const k of new Set(this._ensureRoute(r).tag.map(t => t.k))) {
        total.set(k, (total.get(k) || 0) + lane(r));
      }
    }
    const squeeze = new Map();
    for (const [k, w] of total) squeeze.set(k, Math.min(1, LANE_MAX / (w / 2)));

    const used = new Map();
    for (const r of ordered) {
      const st = this.routeState[r.id];
      const w = lane(r);
      const mine = new Map();
      for (const k of new Set(st.tag.map(t => t.k))) {
        const u = used.get(k) || 0;
        mine.set(k, (u + w / 2 - total.get(k) / 2) * squeeze.get(k));
        used.set(k, u + w);
      }
      // Per point, then smoothed: where a route leaves a bundle its lane has to
      // drift back to the centre over a stretch of line, not step sideways.
      const raw = st.tag.map(t => mine.get(t.k) * t.s);
      st.off = smoothOffsets(raw);
    }
    this._laneSig = sig;          // set last: _ensureRoute above may have cleared it
  }

  _routeColor(r) {
    const ratio = r.vol > 0 ? r.flow / r.vol : (r.userCap > 0 ? 1 : 0);
    if (ratio <= 0.02) return { c: COL.crisis, o: .8, dash: [3, 7], ratio };
    if (ratio < 0.55) return { c: COL.alert, o: .65, dash: r.mode === 'pipe' ? [7, 5] : null, ratio };
    if (this.engine._alt(r)) return { c: COL.watch, o: .68, dash: r.mode === 'pipe' ? [7, 5] : null, ratio };
    return { c: r.mode === 'pipe' ? COL.pipeLine : COL.flowLine, o: .68, dash: r.mode === 'pipe' ? [7, 5] : null, ratio };
  }

  animate(dDays) {
    for (const r of Object.values(this.engine.routes)) {
      const st = this._ensureRoute(r);
      const ratio = r.vol > 0 ? r.flow / r.vol : 0;
      const days = Math.max(1, this.engine._transitDays(r));
      for (const t of st.tankers) {
        if (!t.active && ratio <= 0.02) continue;
        t.phase += dDays / days;
        if (t.phase >= 1) { t.phase -= 1; t.active = ratio > 0.02; }
      }
    }
  }

  /**
   * What the current selection puts in focus. Clicking a country lights up its
   * import/export routes; clicking a chokepoint lights up every route through it
   * and every country on either end - that is the "who is affected" answer.
   */
  _highlight() {
    // Hovering a lane previews the same focus a click would lock in: everything
    // that is not that route and its two ends drops back. A click still wins, so
    // sweeping the mouse cannot knock a selection out of focus.
    const soft = !this.selected && this.hover && this.hover.type === 'route';
    const s = this.selected || (soft ? this.hover : null);
    if (!s) return null;
    const routes = new Set(), countries = new Set(), chokes = new Set();
    const add = r => {
      routes.add(r.id); countries.add(r.from); countries.add(r.to);
      for (const v of this.engine._viaOf(r)) chokes.add(v);
    };
    if (s.type === 'route') add(this.engine.routes[s.id]);
    else if (s.type === 'country') {
      countries.add(s.id);
      for (const r of Object.values(this.engine.routes)) if (r.from === s.id || r.to === s.id) add(r);
    } else if (s.type === 'choke') {
      chokes.add(s.id);
      for (const r of Object.values(this.engine.routes)) if (this.engine._viaOf(r).includes(s.id)) add(r);
    } else if (s.type === 'pipe') {
      for (const r of Object.values(this.engine.routes)) {
        const a = this.engine._alt(r);
        if (a && a.requires === s.id) add(r);
      }
    }
    return { routes, countries, chokes, type: s.type, id: s.id, soft };
  }

  // ---------------- dynamic layer ----------------
  draw() {
    if (!this.W) return;
    this._tickAnim();
    if (this.baseDirty) { this.drawBase(); this.baseDirty = false; }
    const ctx = this.fx.getContext('2d');
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.W, this.H);
    const copies = this.visibleCopies();
    const hl = this._highlight();
    const DIM = 0.14;

    this._relane();
    this._drawPipelines(ctx, copies, hl);

    // --- routes, drawn as a flow ribbon: width is the volume itself.
    // Two bands per route - a dim one sized by the baseline volume and a bright
    // one sized by today's actual flow. The gap between them is the loss.
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    for (const r of Object.values(this.engine.routes)) {
      const st = this._ensureRoute(r);
      const style = this._routeColor(r);
      const on = !hl || hl.routes.has(r.id);
      const hov = this.hover && this.hover.type === 'route' && this.hover.id === r.id;
      const sel = hl && hl.type === 'route' && hl.id === r.id;
      const boost = sel ? 1.5 : (hov || (hl && on)) ? 1.2 : 1;

      // ghost band = what this route carries when nothing is in the way
      const shown = copies.filter(k => this._copyVisible(st.bbox, k));
      if (!shown.length) continue;

      // one path per world copy, stroked twice - the lane offsets make it too
      // expensive to walk the geometry once per band
      const lanes = shown.map(k => this._lanePath(st, k));

      ctx.setLineDash(r.mode === 'pipe' ? [7, 5] : []);
      ctx.strokeStyle = style.ratio <= 0.02 ? COL.crisis : COL.ghost;
      ctx.globalAlpha = on ? (style.ratio < 0.98 ? 0.18 : 0.09) : DIM * 0.5;
      ctx.lineWidth = ribbon(r.vol) * boost;
      for (const p of lanes) ctx.stroke(p);

      // live band = today's flow
      if (r.flow > 0.005) {
        ctx.strokeStyle = style.c;
        ctx.globalAlpha = on ? ((sel || hov) ? 1 : style.o - 0.12) : DIM;
        ctx.lineWidth = ribbon(r.flow) * boost;
        for (const p of lanes) ctx.stroke(p);
      }
    }
    ctx.setLineDash([]);
    ctx.lineCap = 'butt';
    ctx.globalAlpha = 1;

    // --- tankers
    for (const r of Object.values(this.engine.routes)) {
      const st = this.routeState[r.id];
      const lit = !hl || hl.routes.has(r.id);
      // A locked selection drops the other traffic entirely; a hover only fades
      // it, so the map does not blink every time the cursor crosses a lane.
      if (!lit && !hl.soft) continue;
      const shown = copies.filter(k => this._copyVisible(st.bbox, k));
      if (!shown.length) continue;
      const style = this._routeColor(r);
      const glow = style.c === COL.crisis ? 'rgba(239,75,92,.15)' : 'rgba(255,255,255,.18)';
      // tankers ride inside the ribbon, so they scale with it
      const tr = Math.max(1.1, ribbon(r.flow) * 0.3);
      ctx.globalAlpha = lit ? 1 : DIM;
      for (const t of st.tankers) {
        if (!t.active) continue;
        const [lat, lon, si, sf] = pointAt(st.path, st.meta, t.phase);
        // a tanker rides its own lane, not the centre of the bundle
        const off = st.off ? st.off[si] + (st.off[si + 1] - st.off[si]) * sf : 0;
        for (const k of shown) {
          let [x, y] = this.toScreen(wxOf(lon), wyOf(lat), k);
          if (off) {
            const a = this.toScreen(wxOf(st.path[si][1]), wyOf(st.path[si][0]), k);
            const b = this.toScreen(wxOf(st.path[si + 1][1]), wyOf(st.path[si + 1][0]), k);
            const dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1;
            x -= dy / d * off; y += dx / d * off;
          }
          if (x < -20 || y < -20 || x > this.W + 20 || y > this.H + 20) continue;
          ctx.beginPath(); ctx.arc(x, y, tr + 1.6, 0, 6.2832);
          ctx.fillStyle = glow; ctx.fill();
          ctx.beginPath(); ctx.arc(x, y, tr, 0, 6.2832);
          ctx.fillStyle = '#e8f6ff'; ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    }

    // --- chokepoints
    for (const kp of Object.values(this.engine.chokes)) {
      const closed = kp.userCap <= 0.001, limited = !closed && kp.userCap < 0.99;
      const on = !hl || hl.chokes.has(kp.id);
      const isSel = hl && hl.type === 'choke' && hl.id === kp.id;
      const col = closed ? COL.crisis : limited ? COL.alert : COL.flow;
      const pulse = (closed && !this.reduceMotion)
        ? 0.45 + 0.55 * Math.abs(Math.sin(performance.now() / 450)) : 1;
      for (const k of copies) {
        const [x, y] = this.toScreen(wxOf(kp.lon), wyOf(kp.lat), k);
        if (x < -90 || y < -40 || x > this.W + 90 || y > this.H + 40) continue;
        ctx.globalAlpha = on ? pulse : DIM;

        if (isSel) {
          ctx.beginPath(); ctx.arc(x, y, 14, 0, 6.2832);
          ctx.strokeStyle = col; ctx.lineWidth = 1.2; ctx.globalAlpha = .6 * pulse; ctx.stroke();
          ctx.globalAlpha = pulse;
        }
        ctx.save();
        ctx.translate(x, y); ctx.rotate(Math.PI / 4);
        ctx.fillStyle = closed ? col : 'rgba(13,19,28,.9)';
        ctx.strokeStyle = col; ctx.lineWidth = isSel ? 2.6 : 2;
        ctx.beginPath(); ctx.rect(-6, -6, 12, 12); ctx.fill(); ctx.stroke();
        ctx.restore();

        const short = kp.short || kp.name;
        const labelCol = closed ? COL.crisis : limited ? COL.alert : '#cfe0f0';
        ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
        ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(5,9,14,.92)'; ctx.lineJoin = 'round';

        ctx.font = '600 9.5px ' + F_UI;
        ctx.strokeText(short, x + 11, y);
        ctx.fillStyle = labelCol; ctx.fillText(short, x + 11, y);

        const nx = x + 11 + ctx.measureText(short).width + 4;
        const figure = closed ? '✕' : fmt(kp.load, 1);
        ctx.font = '600 9.5px ' + F_READ;
        ctx.strokeText(figure, nx, y);
        ctx.fillStyle = labelCol; ctx.fillText(figure, nx, y);
        ctx.globalAlpha = 1;
      }
    }

    // --- country glyphs
    for (const c of Object.values(this.engine.countries)) {
      const on = !hl || hl.countries.has(c.id);
      const isSel = hl && hl.type === 'country' && hl.id === c.id;
      for (const k of copies) {
        const [x, y] = this.toScreen(wxOf(c.lon), wyOf(c.lat), k);
        if (x < -60 || y < -60 || x > this.W + 60 || y > this.H + 60) continue;
        ctx.globalAlpha = on ? 1 : DIM;
        this._glyph(ctx, c, x, y);
        if (on && hl) {
          // accent ring: the selected country solid, the ones it trades with lighter
          const R = 5 + Math.sqrt(Math.max(c.cons, 0.2)) * 2.35 + 9.5;
          ctx.beginPath(); ctx.arc(x, y, R, 0, 6.2832);
          ctx.strokeStyle = isSel ? '#ffffff' : COL.flow;
          ctx.globalAlpha = isSel ? .85 : .45;
          ctx.lineWidth = isSel ? 1.6 : 1;
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }
    }
  }

  /** Bypass pipelines drawn as standing infrastructure, lit by how much they carry. */
  _drawPipelines(ctx, copies, hl) {
    for (const p of INFRASTRUCTURE) {
      const live = this.engine.pipes[p.id];
      const load = live ? live.load : 0;
      const frac = Math.min(1, load / p.cap);
      const carrying = load > 0.01;
      const hov = this.hover && this.hover.type === 'pipe' && this.hover.id === p.id;
      const isSel = hl && hl.type === 'pipe' && hl.id === p.id;

      ctx.setLineDash([2, 5]);
      ctx.strokeStyle = COL.pipe;
      ctx.globalAlpha = (hov || isSel) ? 1 : carrying ? 0.55 + 0.4 * frac : (hl ? 0.12 : 0.28);
      // idle pipelines stay hairlines; once they carry oil the ribbon rule applies
      ctx.lineWidth = carrying ? ribbon(load) * (isSel ? 1.4 : 1) : 1.6;
      p._geo = p._geo || geoPath(p.path);       // same great-circle treatment as the sea lanes
      p._bb = p._bb || bboxOf(p._geo);
      for (const k of copies) {
        if (!this._copyVisible(p._bb, k)) continue;
        ctx.beginPath();
        for (let i = 0; i < p._geo.length; i++) {
          const [x, y] = this.toScreen(wxOf(p._geo[i][1]), wyOf(p._geo[i][0]), k);
          i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        }
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // label at the midpoint, only when it matters or on hover
      if (carrying || hov) {
        const mid = p._geo[Math.floor(p._geo.length / 2)];
        for (const k of copies) {
          const [x, y] = this.toScreen(wxOf(mid[1]), wyOf(mid[0]), k);
          if (x < -70 || y < -20 || x > this.W + 70 || y > this.H + 20) continue;
          const txt = `${p.id === 'PIPE_EW' ? 'Petroline' : p.id === 'PIPE_ADCOP' ? 'ADCOP' : 'Kirkuk-Ceyhan'} ${fmt(load, 1)}/${fmt(p.cap, 1)}`;
          ctx.font = '600 9px ' + F_READ;
          ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
          ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(5,9,14,.92)'; ctx.lineJoin = 'round';
          ctx.globalAlpha = 1;
          ctx.strokeText(txt, x, y - 5);
          ctx.fillStyle = frac > 0.98 ? COL.alert : COL.pipe;
          ctx.fillText(txt, x, y - 5);
        }
      }
      ctx.globalAlpha = 1;
    }
  }

  _glyph(ctx, c, x, y) {
    const isExp = c.prod > c.cons;
    const R = 5 + Math.sqrt(Math.max(c.cons, 0.2)) * 2.35;
    const ringR = R + 5.5;

    let dom, imp, sto, def;
    if (isExp) { dom = 1; imp = sto = def = 0; }
    else {
      const cons = Math.max(0.001, c.consEff);
      dom = Math.min(c.prodEff, cons) / cons;
      imp = Math.min((c.arrivals || 0) + (c.otherSupply || 0), cons * (1 - dom)) / cons;
      def = Math.min(1 - dom - imp, (c.unmet || 0) / cons);
      sto = Math.max(0, 1 - dom - imp - def);
    }

    let ringFrac, ringCol;
    if (isExp) {
      ringFrac = Math.min(1, (c.sold || 0) / Math.max(0.001, c.netExport0));
      ringCol = c.shutIn > 0.05 ? COL.shutin : ringFrac > .9 ? COL.ok : ringFrac > .55 ? COL.watch : COL.crisis;
    } else {
      ringFrac = Math.min(1, c.coverDays / 90);
      ringCol = { ok: COL.ok, watch: COL.watch, alert: COL.alert, crisis: COL.crisis, shutin: COL.shutin }[c.status] || COL.ok;
    }

    // alarm pulse for a country in actual shortage
    if (c.status === 'crisis') {
      const a0 = ctx.globalAlpha;
      const p = this.reduceMotion ? 0.45 : (performance.now() % 1600) / 1600;
      ctx.beginPath();
      ctx.arc(x, y, ringR + 2 + p * 8, 0, 6.2832);
      ctx.strokeStyle = COL.crisis;
      ctx.globalAlpha = a0 * (this.reduceMotion ? 0.5 : 0.55 * (1 - p));
      ctx.lineWidth = 1; ctx.stroke();
      ctx.globalAlpha = a0;
    }

    // ring: track + value
    ctx.beginPath(); ctx.arc(x, y, ringR, 0, 6.2832);
    ctx.strokeStyle = COL.track; ctx.lineWidth = 3.4; ctx.stroke();
    if (ringFrac > 0.004) {
      ctx.beginPath();
      ctx.arc(x, y, ringR, -Math.PI / 2, -Math.PI / 2 + ringFrac * 6.2832);
      ctx.strokeStyle = ringCol; ctx.lineWidth = 3.4; ctx.lineCap = 'round'; ctx.stroke();
      ctx.lineCap = 'butt';
    }

    // pie: what covers today's demand
    ctx.globalAlpha = .85;
    let a0 = -Math.PI / 2;
    for (const [frac, col] of [[dom, COL.ok], [imp, COL.imp], [sto, COL.watch], [def, COL.crisis]]) {
      if (frac <= 0.002) continue;
      const a1 = a0 + frac * 6.2832;
      ctx.beginPath();
      if (frac > 0.999) ctx.arc(x, y, R, 0, 6.2832);
      else { ctx.moveTo(x, y); ctx.arc(x, y, R, a0, a1); ctx.closePath(); }
      ctx.fillStyle = col; ctx.fill();
      a0 = a1;
    }
    ctx.globalAlpha = 1;
    ctx.beginPath(); ctx.arc(x, y, R, 0, 6.2832);
    ctx.strokeStyle = 'rgba(6,10,16,.85)'; ctx.lineWidth = 1; ctx.stroke();

    // labels
    const sub = isExp ? `${fmt(c.sold || 0, 1)} mb/d`
      : c.unmet > 0.001 ? `-${(c.unmetPct * 100).toFixed(0)}%` : `${Math.round(c.coverDays)}d`;
    ctx.textAlign = 'center';
    ctx.lineJoin = 'round'; ctx.strokeStyle = 'rgba(5,9,14,.92)'; ctx.lineWidth = 3;

    ctx.font = '600 9.5px ' + F_UI;
    ctx.textBaseline = 'bottom';
    ctx.strokeText(c.id, x, y - ringR - 4);
    ctx.fillStyle = '#cfe0f0'; ctx.fillText(c.id, x, y - ringR - 4);

    ctx.font = '600 8.5px ' + F_READ;
    ctx.textBaseline = 'top';
    ctx.strokeText(sub, x, y + ringR + 4);
    ctx.fillStyle = c.unmet > 0.001 ? COL.crisis : '#8fa3ba';
    ctx.fillText(sub, x, y + ringR + 4);
  }

  // ---------------- hit testing ----------------
  hitTest(px, py) {
    const copies = this.visibleCopies();

    for (const c of Object.values(this.engine.countries)) {
      const R = 5 + Math.sqrt(Math.max(c.cons, 0.2)) * 2.35 + 6;
      for (const k of copies) {
        const [x, y] = this.toScreen(wxOf(c.lon), wyOf(c.lat), k);
        if (Math.hypot(px - x, py - y) <= R) return { type: 'country', id: c.id, obj: c };
      }
    }
    for (const kp of Object.values(this.engine.chokes)) {
      for (const k of copies) {
        const [x, y] = this.toScreen(wxOf(kp.lon), wyOf(kp.lat), k);
        if (Math.hypot(px - x, py - y) <= 10) return { type: 'choke', id: kp.id, obj: kp };
      }
    }
    // Routes: the pick tolerance follows the ribbon, so fat flows are easy to grab
    // and a thin one hiding under them still wins when the cursor is right on it.
    let best = null, bestScore = 0;
    const probe = (path, tol, hit) => {
      for (const k of copies) {
        for (let i = 1; i < path.length; i++) {
          const [x1, y1] = this.toScreen(wxOf(path[i - 1][1]), wyOf(path[i - 1][0]), k);
          const [x2, y2] = this.toScreen(wxOf(path[i][1]), wyOf(path[i][0]), k);
          const d = distToSeg(px, py, x1, y1, x2, y2);
          const score = tol - d;                 // >0 means inside the band
          if (score > 0 && score > bestScore) { bestScore = score; best = hit; }
        }
      }
    };

    // routes are picked on the lane they are drawn in, not on the centreline
    this._relane();
    for (const r of Object.values(this.engine.routes)) {
      const st = this._ensureRoute(r);
      const tol = ribbon(r.vol) / 2 + 4;
      const hit = { type: 'route', id: r.id, obj: r };
      for (const k of copies) {
        const n = this._laneScreen(st, k);
        for (let i = 1; i < n; i++) {
          const score = tol - distToSeg(px, py, this._lx[i - 1], this._ly[i - 1], this._lx[i], this._ly[i]);
          if (score > 0 && score > bestScore) { bestScore = score; best = hit; }
        }
      }
    }
    for (const p of INFRASTRUCTURE) {
      probe(p._geo || p.path, 6, { type: 'pipe', id: p.id, obj: p });
    }
    return best;
  }

  _localPoint(e) {
    const r = this.fx.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  _click(e) {
    const hit = this.hitTest(...this._localPoint(e));
    if (!hit) { this.select(null); this.h.onBlank && this.h.onBlank(); return; }
    if (hit.type === 'country') this.h.onCountry && this.h.onCountry(hit.id);
    else if (hit.type === 'choke') this.h.onChoke && this.h.onChoke(hit.id);
    else if (hit.type === 'pipe') this.select({ type: 'pipe', id: hit.id });
    else this.h.onRoute && this.h.onRoute(hit.id);
  }

  _hover(e) {
    const hit = this.hitTest(...this._localPoint(e));
    this.hover = hit;
    this.fx.style.cursor = hit ? 'pointer' : 'grab';
    if (!hit) return this._hideTip();
    const html = hit.type === 'country' ? this._countryTip(hit.obj)
      : hit.type === 'choke' ? this._chokeTip(hit.obj)
      : hit.type === 'pipe' ? this._pipeTip(hit.obj)
      : this._routeTip(hit.obj);
    this._showTip(html, e);
  }

  _pipeTip(p) {
    const live = this.engine.pipes[p.id] || { load: 0 };
    const users = Object.values(this.engine.routes).filter(r => {
      const a = this.engine._alt(r);
      return a && a.requires === p.id;
    });
    const frac = live.load / p.cap;
    return `<h5>${p.name}</h5><table>
      <tr><td class="muted">capacity</td><td>${fmt(p.cap, 1)} mb/d</td></tr>
      <tr><td class="muted">carrying now</td><td style="color:${frac > .98 ? COL.alert : frac > 0 ? COL.ok : 'inherit'}">${fmt(live.load, 2)} mb/d (${(frac * 100).toFixed(0)}%)</td></tr>
      <tr><td class="muted">routes diverted onto it</td><td>${users.length}</td></tr>
      </table><div class="muted" style="margin-top:5px;font-size:10px">${p.note}</div>
      ${users.length ? '<div class="muted" style="margin-top:4px;font-size:10px">click to highlight them</div>' : ''}`;
  }

  select(sel) {
    // the land layer tints the selected country, so it has to be repainted
    const was = this.selected && this.selected.type === 'country' ? this.selected.id : null;
    const now = sel && sel.type === 'country' ? sel.id : null;
    if (was !== now) this.baseDirty = true;
    this.selected = sel;
  }

  // API kept for the app loop; everything is drawn live from engine state
  refreshRoutes() {}
  refreshChokes() {}
  refreshCountries() {}
  refreshRouteGeometry() {}
  refreshAllGeometry() {}

  // ---------------- tooltips ----------------
  _showTip(html, e) {
    const t = this.tip;
    t.innerHTML = html;
    t.classList.remove('hidden');
    const pad = 16;
    let x = e.clientX + pad, y = e.clientY + pad;
    if (x + t.offsetWidth > window.innerWidth - 10) x = e.clientX - t.offsetWidth - pad;
    if (y + t.offsetHeight > window.innerHeight - 10) y = e.clientY - t.offsetHeight - pad;
    t.style.left = x + 'px'; t.style.top = y + 'px';
  }

  _hideTip() { this.tip.classList.add('hidden'); }

  _routeTip(r) {
    const alt = this.engine._alt(r);
    const pct = r.vol > 0 ? (r.flow / r.vol * 100) : 0;
    const via = this.engine._viaOf(r).map(v => this.engine.chokes[v] ? this.engine.chokes[v].name : v);
    return `<h5>${r.label}</h5><table>
      <tr><td class="muted">${this.engine.countries[r.from].name} → ${this.engine.countries[r.to].name}</td><td></td></tr>
      <tr><td class="muted">flow</td><td>${fmt(r.flow, 2)} / ${fmt(r.vol, 2)} mb/d</td></tr>
      <tr><td class="muted">utilisation</td><td>${pct.toFixed(0)}%</td></tr>
      <tr><td class="muted">transit</td><td>${this.engine._transitDays(r)} days</td></tr>
      <tr><td class="muted">oil at sea</td><td>${fmt(r.inTransit, 1)} mn bbl</td></tr>
      ${alt ? `<tr><td class="muted">variant</td><td style="color:${COL.watch}">${alt.label}</td></tr>` : ''}
      ${via.length ? `<tr><td class="muted">via</td><td>${via.join(', ')}</td></tr>` : ''}
      </table><div class="muted" style="margin-top:5px;font-size:10px">click to open inspector</div>`;
  }

  _chokeTip(k) {
    const use = k.cap > 0 ? (k.load / k.cap * 100) : 0;
    return `<h5>${k.name}</h5><table>
      <tr><td class="muted">capacity</td><td>${fmt(k.cap, 1)} mb/d</td></tr>
      <tr><td class="muted">setting</td><td>${(k.userCap * 100).toFixed(0)}%</td></tr>
      <tr><td class="muted">modelled traffic</td><td>${fmt(k.load, 2)} mb/d</td></tr>
      <tr><td class="muted">utilisation</td><td>${use.toFixed(0)}%</td></tr>
      </table><div class="muted" style="margin-top:5px;font-size:10px">${k.note}</div>`;
  }

  _countryTip(c) {
    const isExp = c.prod > c.cons;
    const rows = isExp
      ? `<tr><td class="muted">output</td><td>${fmt(c.prodEff, 2)} / ${fmt(c.prod, 2)} mb/d</td></tr>
         <tr><td class="muted">own demand</td><td>${fmt(c.consEff, 2)} mb/d</td></tr>
         <tr><td class="muted">exports today</td><td>${fmt(c.sold || 0, 2)} / ${fmt(c.netExport0, 2)} mb/d</td></tr>
         <tr><td class="muted">oil with no buyer</td><td>${fmt(c.surplusMb, 1)} mn bbl</td></tr>
         ${c.shutIn > 0.01 ? `<tr><td class="muted">shut-in output</td><td style="color:${COL.crisis}">${fmt(c.shutIn, 2)} mb/d</td></tr>` : ''}`
      : `<tr><td class="muted">consumption</td><td>${fmt(c.consEff, 2)} mb/d</td></tr>
         <tr><td class="muted">own output</td><td>${fmt(c.prodEff, 2)} mb/d</td></tr>
         <tr><td class="muted">arrivals today</td><td>${fmt(c.arrivals, 2)} mb/d</td></tr>
         <tr><td class="muted">off-model supply</td><td>${fmt(c.otherSupply || 0, 2)} mb/d</td></tr>
         <tr><td class="muted">daily balance</td><td style="color:${c.balance < 0 ? COL.crisis : COL.ok}">${c.balance >= 0 ? '+' : ''}${fmt(c.balance, 2)} mb/d</td></tr>
         <tr><td class="muted">stocks</td><td>${fmt(c.stockMb, 0)} mn bbl (${Math.round(c.coverDays)} d)</td></tr>
         <tr><td class="muted">import dependence</td><td>${(c.importDep * 100).toFixed(0)}%</td></tr>
         ${c.unmet > 0.001 ? `<tr><td class="muted">unmet demand</td><td style="color:${COL.crisis}">${fmt(c.unmet, 2)} mb/d (${(c.unmetPct * 100).toFixed(0)}%)</td></tr>` : ''}`;
    return `<h5>${c.name}</h5><table>${rows}</table>`;
  }
}

/**
 * Ribbon width in pixels. Linear in volume on purpose: the line IS the
 * quantity, so 2 mb/d must read as twice 1 mb/d rather than 1.4x under a sqrt.
 */
function ribbon(v) { return Math.min(16, 1.1 + Math.max(0, v) * 3.4); }

function fmt(v, d = 1) {
  return (v == null || isNaN(v)) ? '—' : v.toFixed(d);
}
