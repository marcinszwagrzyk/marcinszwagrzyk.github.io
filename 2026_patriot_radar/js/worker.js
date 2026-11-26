// Worker: pobiera DEM (Terrarium), liczy zasięg radaru promieniowo i składa siatkę
// „minimalnej wysokości wykrycia” (m nad terenem) dla wszystkich baterii.
'use strict';

const R_EARTH = 6371008.8;
const TILE_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
const DEG = Math.PI / 180;

const tileCache = new Map();   // "z/x/y" -> Promise<Float32Array(256*256)>
const batteries = new Map();   // id -> {lat, lon, rangeM, step, nRays, nSteps, polar}

function lon2px(lon, z) { return (lon + 180) / 360 * 256 * (1 << z); }
function lat2px(lat, z) {
  const s = Math.sin(lat * DEG);
  return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * 256 * (1 << z);
}

function loadTile(z, x, y) {
  const key = z + '/' + x + '/' + y;
  if (!tileCache.has(key)) {
    const p = fetch(TILE_URL.replace('{z}', z).replace('{x}', x).replace('{y}', y))
      .then(r => { if (!r.ok) throw new Error(r.status); return r.blob(); })
      .then(b => createImageBitmap(b))
      .then(bmp => {
        const c = new OffscreenCanvas(256, 256);
        const ctx = c.getContext('2d');
        ctx.drawImage(bmp, 0, 0);
        const d = ctx.getImageData(0, 0, 256, 256).data;
        const out = new Float32Array(256 * 256);
        for (let i = 0; i < out.length; i++) {
          const h = d[i * 4] * 256 + d[i * 4 + 1] + d[i * 4 + 2] / 256 - 32768;
          out[i] = h < 0 ? 0 : h;               // morze / batymetria -> 0 m
        }
        return out;
      })
      .catch(() => new Float32Array(256 * 256)); // brak kafla -> 0 m
    tileCache.set(key, p);
  }
  return tileCache.get(key);
}

async function buildMosaic(lat, lon, rangeM, z) {
  const dLat = rangeM / 111320 + 0.05;
  const dLon = rangeM / (111320 * Math.cos(lat * DEG)) + 0.05;
  const tx0 = Math.floor(lon2px(lon - dLon, z) / 256), tx1 = Math.floor(lon2px(lon + dLon, z) / 256);
  const ty0 = Math.floor(lat2px(lat + dLat, z) / 256), ty1 = Math.floor(lat2px(lat - dLat, z) / 256);
  const nx = tx1 - tx0 + 1, ny = ty1 - ty0 + 1;
  const W = nx * 256, H = ny * 256;
  const data = new Float32Array(W * H);
  const jobs = [];
  let done = 0;
  const total = nx * ny;
  for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++) {
    jobs.push(loadTile(z, tx, ty).then(t => {
      const ox = (tx - tx0) * 256, oy = (ty - ty0) * 256;
      for (let r = 0; r < 256; r++) data.set(t.subarray(r * 256, r * 256 + 256), (oy + r) * W + ox);
      done++;
      if (done % 8 === 0 || done === total) postMessage({ type: 'progress', text: `DEM: ${done}/${total} kafli` });
    }));
  }
  await Promise.all(jobs);
  return { data, W, H, x0: tx0 * 256, y0: ty0 * 256, z };
}

function sampleDem(m, lat, lon) {
  let x = lon2px(lon, m.z) - m.x0 - 0.5, y = lat2px(lat, m.z) - m.y0 - 0.5;
  if (x < 0) x = 0; if (y < 0) y = 0;
  if (x > m.W - 1.001) x = m.W - 1.001; if (y > m.H - 1.001) y = m.H - 1.001;
  const ix = x | 0, iy = y | 0, fx = x - ix, fy = y - iy;
  const i = iy * m.W + ix, d = m.data;
  return (d[i] * (1 - fx) + d[i + 1] * fx) * (1 - fy) + (d[i + m.W] * (1 - fx) + d[i + m.W + 1] * fx) * fy;
}

async function compute(msg) {
  const { id, lat, lon, antH, rangeKm, az, sector, zoom, k } = msg;
  const rangeM = rangeKm * 1000;
  const m = await buildMosaic(lat, lon, rangeM, zoom);
  postMessage({ type: 'progress', text: 'Liczenie linii widoczności…' });

  const pxM = 156543.034 * Math.cos(lat * DEG) / (1 << zoom);   // m na piksel DEM
  const step = Math.max(25, pxM * 0.9);
  const nSteps = Math.ceil(rangeM / step);
  const nRays = Math.min(7200, Math.max(1440, Math.ceil(2 * Math.PI * rangeM / (step * 2.5))));
  const polar = new Float32Array(nRays * nSteps);
  const ground = sampleDem(m, lat, lon);
  const h0 = ground + antH;
  const kR2 = 2 * k * R_EARTH;
  const lat1 = lat * DEG, lon1 = lon * DEG, sLat1 = Math.sin(lat1), cLat1 = Math.cos(lat1);
  const half = sector / 2;

  for (let r = 0; r < nRays; r++) {
    const a = r * 360 / nRays;
    let dA = Math.abs(((a - az) % 360 + 540) % 360 - 180);
    const base = r * nSteps;
    if (sector < 360 && dA > half) { polar.fill(Infinity, base, base + nSteps); continue; }
    const th = a * DEG, sTh = Math.sin(th), cTh = Math.cos(th);
    let maxTan = -Infinity;
    for (let s = 0; s < nSteps; s++) {
      const d = (s + 1) * step;
      const del = d / R_EARTH, sD = Math.sin(del), cD = Math.cos(del);
      const sLat2 = sLat1 * cD + cLat1 * sD * cTh;
      const lat2 = Math.asin(sLat2);
      const lon2 = lon1 + Math.atan2(sTh * sD * cLat1, cD - sLat1 * sLat2);
      const rel = sampleDem(m, lat2 / DEG, lon2 / DEG) - d * d / kR2 - h0;
      const need = maxTan * d - rel;
      polar[base + s] = need > 0 ? need : 0;
      const t = rel / d;
      if (t > maxTan) maxTan = t;
    }
    if ((r & 255) === 0) postMessage({ type: 'progress', text: `Promienie: ${Math.round(100 * r / nRays)}%` });
  }
  batteries.set(id, { lat, lon, rangeM, step, nRays, nSteps, polar });
  return { type: 'computed', id, ground };
}

// Siatka wynikowa w Web Mercator (EPSG:3857), min po bateriach.
function composite(msg) {
  const { ids, maxDim } = msg;
  const list = ids.map(i => batteries.get(i)).filter(Boolean);
  if (!list.length) return { type: 'composite', empty: true };
  const MER = 6378137;
  const toMx = lon => lon * DEG * MER;
  const toMy = lat => MER * Math.log(Math.tan(Math.PI / 4 + lat * DEG / 2));
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity, res = Infinity;
  for (const b of list) {
    const dLat = b.rangeM / 111320, dLon = b.rangeM / (111320 * Math.cos(b.lat * DEG));
    xmin = Math.min(xmin, toMx(b.lon - dLon)); xmax = Math.max(xmax, toMx(b.lon + dLon));
    ymin = Math.min(ymin, toMy(b.lat - dLat)); ymax = Math.max(ymax, toMy(b.lat + dLat));
    res = Math.min(res, b.step / Math.cos(b.lat * DEG));
  }
  res = Math.max(res, (xmax - xmin) / maxDim, (ymax - ymin) / maxDim);
  const W = Math.ceil((xmax - xmin) / res), H = Math.ceil((ymax - ymin) / res);
  const grid = new Float32Array(W * H).fill(NaN);
  const pre = list.map(b => ({ ...b, sLat: Math.sin(b.lat * DEG), cLat: Math.cos(b.lat * DEG), lonR: b.lon * DEG }));
  for (let j = 0; j < H; j++) {
    const my = ymax - (j + 0.5) * res;
    const latR = 2 * Math.atan(Math.exp(my / MER)) - Math.PI / 2;
    const sLat = Math.sin(latR), cLat = Math.cos(latR);
    for (let i = 0; i < W; i++) {
      const lonR = (xmin + (i + 0.5) * res) / MER;
      let best = NaN;
      for (const b of pre) {
        const dLon = lonR - b.lonR;
        const cosC = b.sLat * sLat + b.cLat * cLat * Math.cos(dLon);
        const d = Math.acos(Math.min(1, cosC)) * R_EARTH;
        if (d >= b.rangeM) continue;
        let brg = Math.atan2(Math.sin(dLon) * cLat, b.cLat * sLat - b.sLat * cLat * Math.cos(dLon)) / DEG;
        if (brg < 0) brg += 360;
        const r = Math.round(brg * b.nRays / 360) % b.nRays;
        const s = Math.max(0, Math.min(b.nSteps - 1, Math.round(d / b.step) - 1));
        const v = b.polar[r * b.nSteps + s];
        if (v !== Infinity && !(v >= best)) best = v;
      }
      grid[j * W + i] = best;
    }
    if ((j & 127) === 0) postMessage({ type: 'progress', text: `Składanie mapy: ${Math.round(100 * j / H)}%` });
  }
  const lat = y => (2 * Math.atan(Math.exp(y / MER)) - Math.PI / 2) / DEG;
  return {
    type: 'composite', W, H, grid, resM: res,
    bounds: [[lat(ymin), xmin / MER / DEG], [lat(ymax), xmax / MER / DEG]],
  };
}

onmessage = async (e) => {
  const msg = e.data;
  try {
    if (msg.type === 'compute') postMessage(await compute(msg));
    else if (msg.type === 'remove') batteries.delete(msg.id);
    else if (msg.type === 'composite') {
      const out = composite(msg);
      out.seq = msg.seq;
      postMessage(out, out.grid ? [out.grid.buffer] : []);
    }
  } catch (err) {
    postMessage({ type: 'error', text: String(err && err.message || err) });
  }
};
