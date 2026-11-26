'use strict';

// ---------- mapa ----------
const map = L.map('map', { zoomControl: true, preferCanvas: true }).setView([50.6, 21.6], 8);

const basemaps = {
  'Jasna szara (Esri)': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 16, attribution: 'Esri, HERE, Garmin, &copy; OpenStreetMap' }),
  'Topograficzna (OpenTopoMap)': L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    maxZoom: 17, attribution: '&copy; OpenStreetMap, SRTM | styl &copy; OpenTopoMap (CC-BY-SA)' }),
  'Zdjęcia (Esri)': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19, attribution: 'Esri, Maxar, Earthstar Geographics' }),
};
basemaps['Jasna szara (Esri)'].addTo(map);

map.createPane('coverage'); map.getPane('coverage').style.zIndex = 350;
map.createPane('labels'); map.getPane('labels').style.zIndex = 450; map.getPane('labels').style.pointerEvents = 'none';
const labelsLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
  pane: 'labels', maxZoom: 16, attribution: '' }).addTo(map);

L.control.layers(basemaps, { 'Nazwy miejscowości (nad pokryciem)': labelsLayer }, { position: 'topright' }).addTo(map);
L.control.scale({ metric: true, imperial: false, maxWidth: 200, position: 'bottomleft' }).addTo(map);

const titleCtl = L.control({ position: 'topleft' });
titleCtl.onAdd = () => { const d = L.DomUtil.create('div', 'map-title'); return d; };
titleCtl.addTo(map);

const legendCtl = L.control({ position: 'bottomright' });
legendCtl.onAdd = () => L.DomUtil.create('div', 'legend');
legendCtl.addTo(map);

const readoutCtl = L.control({ position: 'bottomleft' });
readoutCtl.onAdd = () => { const d = L.DomUtil.create('div', 'readout'); d.textContent = 'Najedź na mapę, aby odczytać wysokość wykrycia.'; return d; };
readoutCtl.addTo(map);

// ---------- stan ----------
const $ = id => document.getElementById(id);
const PALETTE = ['#08306b', '#2171b5', '#6baed6', '#bdd7ee', '#e3eef9'];
const EPRZ = { name: 'EPRZ Rzeszów-Jasionka', lat: 50.1100, lon: 22.0190 };

let batteries = [];      // {id, name, lat, lon, antH, range, sector, az, ground, layers}
let nextId = 1;
let comp = null;         // {W, H, grid, bounds, resM}
let overlay = null;
let compSeq = 0;

function thresholds() {
  const t = $('thresholds').value.split(/[,;\s]+/).map(Number).filter(v => isFinite(v) && v >= 0);
  return [...new Set(t)].sort((a, b) => a - b).slice(0, 5);
}
function settings() { return { zoom: +$('zoom').value, k: +$('kfac').value || 4 / 3 }; }

// ---------- worker (kolejka żądań) ----------
const worker = new Worker('js/worker.js');
let pending = null, chain = Promise.resolve();
worker.onmessage = (e) => {
  const m = e.data;
  if (m.type === 'progress') { status(m.text); return; }
  if (m.type === 'error') { status('Błąd: ' + m.text, 4000); }
  if (pending) { const p = pending; pending = null; p(m); }
};
function call(msg, transfer) {
  const run = () => new Promise(res => { pending = res; worker.postMessage(msg, transfer || []); });
  const p = chain.then(run);
  chain = p.catch(() => {});
  return p;
}

let statusTimer = null;
function status(text, hideAfter) {
  const s = $('status');
  s.hidden = !text; s.textContent = text || '';
  clearTimeout(statusTimer);
  if (hideAfter) statusTimer = setTimeout(() => { s.hidden = true; }, hideAfter);
}

// ---------- baterie ----------
function addBattery(p, recompute = true) {
  const b = {
    id: nextId++,
    name: p.name || `Bateria ${nextId - 1}`,
    lat: +p.lat, lon: +p.lon,
    antH: p.antH ?? +$('defAnt').value,
    range: p.range ?? +$('defRange').value,
    sector: p.sector ?? +$('defSector').value,
    az: p.az ?? +$('defAz').value,
    ground: null, layers: L.layerGroup().addTo(map),
  };
  batteries.push(b);
  drawBattery(b);
  renderList();
  if (recompute) computeBattery(b).then(refresh);
  return b;
}

function drawBattery(b) {
  b.layers.clearLayers();
  const icon = L.divIcon({ className: 'bat-icon', html: '<div class="sym">P</div>', iconSize: [22, 22], iconAnchor: [11, 11] });
  const mk = L.marker([b.lat, b.lon], { icon, draggable: true, zIndexOffset: 1000 })
    .bindTooltip(b.name, { permanent: true, direction: 'right', offset: [12, 0], className: 'bat-label' });
  mk.on('dragend', () => {
    const ll = mk.getLatLng(); b.lat = ll.lat; b.lon = ll.lng;
    drawBattery(b); renderList(); computeBattery(b).then(refresh);
  });
  b.layers.addLayer(mk);
  b.layers.addLayer(L.circle([b.lat, b.lon], {
    radius: b.range * 1000, color: '#c0392b', weight: 1.5, dashArray: '6 5', fill: false, interactive: false }));
  for (const r of [50, 100]) if (r < b.range) b.layers.addLayer(L.circle([b.lat, b.lon], {
    radius: r * 1000, color: '#c0392b', weight: 0.8, opacity: 0.5, dashArray: '2 4', fill: false, interactive: false }));
  if (b.sector < 360) {
    for (const a of [b.az - b.sector / 2, b.az + b.sector / 2]) {
      b.layers.addLayer(L.polyline([[b.lat, b.lon], destPoint(b.lat, b.lon, a, b.range * 1000)], {
        color: '#c0392b', weight: 1.2, dashArray: '6 5', interactive: false }));
    }
  }
}

function destPoint(lat, lon, brg, d) {
  const R = 6371008.8, r = Math.PI / 180, del = d / R, th = brg * r, p1 = lat * r;
  const p2 = Math.asin(Math.sin(p1) * Math.cos(del) + Math.cos(p1) * Math.sin(del) * Math.cos(th));
  const l2 = lon * r + Math.atan2(Math.sin(th) * Math.sin(del) * Math.cos(p1), Math.cos(del) - Math.sin(p1) * Math.sin(p2));
  return [p2 / r, l2 / r];
}
function distBrg(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180, p1 = lat1 * r, p2 = lat2 * r, dl = (lon2 - lon1) * r;
  const d = Math.acos(Math.min(1, Math.sin(p1) * Math.sin(p2) + Math.cos(p1) * Math.cos(p2) * Math.cos(dl))) * 6371.0088;
  let b = Math.atan2(Math.sin(dl) * Math.cos(p2), Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl)) / r;
  return { d, b: (b + 360) % 360 };
}

async function computeBattery(b) {
  const li = document.querySelector(`li[data-id="${b.id}"]`); if (li) li.classList.add('busy');
  const s = settings();
  const res = await call({ type: 'compute', id: b.id, lat: b.lat, lon: b.lon, antH: b.antH,
    rangeKm: b.range, az: b.az, sector: b.sector, zoom: s.zoom, k: s.k });
  if (res.type === 'computed') b.ground = res.ground;
  renderList();
}

function removeBattery(b) {
  map.removeLayer(b.layers);
  batteries = batteries.filter(x => x !== b);
  worker.postMessage({ type: 'remove', id: b.id });
  renderList(); refresh();
}

function renderList() {
  const ul = $('batteries');
  ul.innerHTML = '';
  for (const b of batteries) {
    const li = document.createElement('li');
    li.dataset.id = b.id;
    li.innerHTML = `
      <div class="bhead"><input class="nm" value="${esc(b.name)}"><button title="Usuń" class="del">×</button></div>
      <div class="bmeta">${b.lat.toFixed(4)}° N, ${b.lon.toFixed(4)}° E · teren ${b.ground == null ? '…' : Math.round(b.ground) + ' m n.p.m.'}</div>
      <div class="bgrid">
        <label>antena m<input type="number" data-k="antH" value="${b.antH}" min="0" max="100"></label>
        <label>zasięg km<input type="number" data-k="range" value="${b.range}" min="10" max="250" step="5"></label>
        <label>sektor °<input type="number" data-k="sector" value="${b.sector}" min="10" max="360" step="10"></label>
        <label>azymut °<input type="number" data-k="az" value="${b.az}" min="0" max="359" step="5"></label>
      </div>`;
    li.querySelector('.del').onclick = () => removeBattery(b);
    li.querySelector('.nm').onchange = (e) => { b.name = e.target.value || b.name; drawBattery(b); refresh(false); };
    li.querySelectorAll('.bgrid input').forEach(inp => inp.onchange = () => {
      b[inp.dataset.k] = +inp.value; drawBattery(b); computeBattery(b).then(refresh);
    });
    ul.appendChild(li);
  }
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

// ---------- składanie i rysowanie pokrycia ----------
async function refresh(recomposite = true) {
  saveHash();
  if (recomposite) {
    const seq = ++compSeq;
    const ids = batteries.filter(b => b.ground != null).map(b => b.id);
    const res = await call({ type: 'composite', ids, maxDim: 2600, seq });
    if (seq !== compSeq) return;              // nowsze żądanie w drodze
    comp = res.empty ? null : res;
    status('');
  }
  paint();
}

function paint() {
  if (overlay) { map.removeLayer(overlay); overlay = null; }
  const t = thresholds();
  const areas = new Array(t.length).fill(0);
  if (comp) {
    const { W, H, grid, bounds, resM } = comp;
    const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
    const ctx = cv.getContext('2d');
    const img = ctx.createImageData(W, H);
    const rgb = t.map((_, i) => hex(PALETTE[Math.min(i, PALETTE.length - 1)]));
    const MER = 6378137, yTop = MER * Math.log(Math.tan(Math.PI / 4 + bounds[1][0] * Math.PI / 360));
    for (let j = 0; j < H; j++) {
      const lat = 2 * Math.atan(Math.exp((yTop - (j + 0.5) * resM) / MER)) - Math.PI / 2;
      const pxArea = (resM * Math.cos(lat)) ** 2 / 1e6;
      for (let i = 0; i < W; i++) {
        const v = grid[j * W + i];
        if (!(v <= t[t.length - 1])) continue;
        let c = 0; while (v > t[c]) c++;
        for (let q = c; q < t.length; q++) areas[q] += pxArea;
        const o = (j * W + i) * 4, col = rgb[c];
        img.data[o] = col[0]; img.data[o + 1] = col[1]; img.data[o + 2] = col[2]; img.data[o + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    overlay = L.imageOverlay(cv.toDataURL(), bounds, { pane: 'coverage', opacity: +$('opacity').value, interactive: false }).addTo(map);
  }
  renderLegend(t, areas);
  renderTitle(t);
}
function hex(h) { return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)); }

function renderLegend(t, areas) {
  const el = legendCtl.getContainer();
  let h = '<h3>Cel widoczny dla radaru</h3>';
  t.forEach((v, i) => {
    h += `<div class="item"><span class="sw" style="background:${PALETTE[Math.min(i, PALETTE.length - 1)]}"></span>`
      + `${i === 0 ? 'już' : 'od'} ${v} m nad terenem<span class="area">${comp ? fmtArea(areas[i]) : ''}</span></div>`;
  });
  h += `<div class="item"><span class="sw" style="background:transparent"></span>niżej niż ${t[t.length - 1] ?? '–'} m — w cieniu terenu</div>`;
  h += '<div class="item"><span class="ring"></span>zasięg instrumentalny</div>';
  h += `<div class="note">Powierzchnia = łączny obszar, w którym cel na danej wysokości jest w polu widzenia co najmniej jednej baterii. Model: linia wzroku, k = ${(+$('kfac').value).toFixed(2)}, DEM bez lasów i zabudowy.</div>`;
  el.innerHTML = h;
}
function fmtArea(a) { return a >= 1000 ? (a / 1000).toFixed(1).replace('.', ',') + ' tys. km²' : Math.round(a) + ' km²'; }

function renderTitle(t) {
  const el = titleCtl.getContainer();
  const n = batteries.length;
  const where = n === 1 ? batteries[0].name : n ? `${n} baterie/baterii` : 'brak baterii — kliknij mapę';
  el.innerHTML = `Pokrycie radarowe AN/MPQ-65 (Patriot) — ${esc(where)}`
    + `<small>Obszar, w którym cel lecący ${t.join(' / ')} m nad terenem znajduje się w linii wzroku radaru</small>`;
}

// ---------- odczyt pod kursorem ----------
map.on('mousemove', (e) => {
  const el = readoutCtl.getContainer();
  let txt = `${e.latlng.lat.toFixed(4)}° N, ${e.latlng.lng.toFixed(4)}° E`;
  if (batteries.length) {
    let best = null;
    for (const b of batteries) { const db = distBrg(b.lat, b.lon, e.latlng.lat, e.latlng.lng); if (!best || db.d < best.d) best = { ...db, bat: b }; }
    txt += ` · ${best.d.toFixed(1)} km, az ${Math.round(best.b)}° od ${esc(best.bat.name)}`;
  }
  if (comp) {
    const MER = 6378137;
    const x = e.latlng.lng * Math.PI / 180 * MER, y = MER * Math.log(Math.tan(Math.PI / 4 + e.latlng.lat * Math.PI / 360));
    const x0 = comp.bounds[0][1] * Math.PI / 180 * MER, yTop = MER * Math.log(Math.tan(Math.PI / 4 + comp.bounds[1][0] * Math.PI / 360));
    const i = Math.floor((x - x0) / comp.resM), j = Math.floor((yTop - y) / comp.resM);
    if (i >= 0 && j >= 0 && i < comp.W && j < comp.H) {
      const v = comp.grid[j * comp.W + i];
      txt += '<br><b>' + (isNaN(v) ? 'poza zasięgiem / sektorem' : `cel widoczny od ${Math.max(0, Math.round(v))} m nad terenem`) + '</b>';
    }
  }
  el.innerHTML = txt;
});

// ---------- interakcje ----------
map.on('click', (e) => addBattery({ lat: e.latlng.lat, lon: e.latlng.lng }));
$('addEprz').onclick = () => addBattery(EPRZ);
$('clearAll').onclick = () => { [...batteries].forEach(b => { map.removeLayer(b.layers); worker.postMessage({ type: 'remove', id: b.id }); }); batteries = []; renderList(); refresh(); };
$('thresholds').onchange = () => { paint(); saveHash(); };
$('opacity').oninput = () => overlay && overlay.setOpacity(+$('opacity').value);
const recomputeAll = async () => { for (const b of batteries) await computeBattery(b); refresh(); };
$('zoom').onchange = recomputeAll;
$('kfac').onchange = recomputeAll;

$('search').onsubmit = async (ev) => {
  ev.preventDefault();
  const q = $('q').value.trim(); if (!q) return;
  status('Szukam…');
  try {
    const r = await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=pl,lt,sk,cz,de,ua,by&q=' + encodeURIComponent(q));
    const j = await r.json();
    if (!j.length) { status('Nie znaleziono', 2500); return; }
    map.setView([+j[0].lat, +j[0].lon], 11);
    status('Kliknij mapę, aby postawić baterię', 3000);
  } catch { status('Wyszukiwarka niedostępna', 3000); }
};

// ---------- stan w adresie URL (do udostępniania) ----------
function saveHash() {
  const bs = batteries.map(b => [b.lat.toFixed(5), b.lon.toFixed(5), b.antH, b.range, b.sector, b.az, encodeURIComponent(b.name)].join(','));
  const h = `b=${bs.join(';')}&t=${thresholds().join(',')}&z=${$('zoom').value}&k=${$('kfac').value}`;
  history.replaceState(null, '', '#' + h);
}
function loadHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.get('t')) $('thresholds').value = p.get('t').split(',').join(', ');
  if (p.get('z')) $('zoom').value = p.get('z');
  if (p.get('k')) $('kfac').value = p.get('k');
  const bs = (p.get('b') || '').split(';').filter(Boolean).map(s => {
    const [lat, lon, antH, range, sector, az, name] = s.split(',');
    return { lat: +lat, lon: +lon, antH: +antH, range: +range, sector: +sector, az: +az, name: decodeURIComponent(name || '') };
  }).filter(b => isFinite(b.lat) && isFinite(b.lon));
  return bs;
}

(async function init() {
  const saved = loadHash();
  const list = saved.length ? saved : [EPRZ];
  const added = list.map(p => addBattery(p, false));
  renderTitle(thresholds()); renderLegend(thresholds(), []);
  for (const b of added) await computeBattery(b);
  await refresh();
  if (added.length) { const bb = L.latLngBounds(added.map(b => L.latLng(b.lat, b.lon).toBounds(b.range * 2000))); map.fitBounds(bb, { padding: [10, 10] }); }
})();
