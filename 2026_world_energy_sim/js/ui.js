/** Control panels, the country balance table, the chart and the event log. */

const STATUS_COL = {
  ok: '#3fc98b', watch: '#e0c341', alert: '#f09033', crisis: '#ef4b5c', shutin: '#b07be0',
};
const STATUS_RANK = { crisis: 0, alert: 1, watch: 2, shutin: 3, ok: 4 };

class UI {
  constructor(engine, view, app) {
    this.e = engine; this.v = view; this.app = app;
    this.sort = 'risk';
    this.routeFilter = '';
    this.selCountry = null;

    this.el = {
      simDate: document.getElementById('simDate'),
      simDay: document.getElementById('simDay'),
      chokeList: document.getElementById('chokeList'),
      pipeList: document.getElementById('pipeList'),
      scenarioList: document.getElementById('scenarioList'),
      routeList: document.getElementById('routeList'),
      balanceList: document.getElementById('balanceList'),
      log: document.getElementById('log'),
      inspector: document.getElementById('inspector'),
      inspBody: document.getElementById('inspBody'),
    };

    this._wireTabs();
    this._wireLegend();
    this._wireTransport();
    this._wireSort();
    this._wireInspector();
    this.buildChokes();
    this.buildScenarios();
    this.buildRoutes();
  }

  // ===================== chrome =====================
  _wireTabs() {
    document.querySelectorAll('.ptab').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('.ptab').forEach(x => x.classList.toggle('active', x === b));
      document.querySelectorAll('.tabpane').forEach(p =>
        p.classList.toggle('active', p.dataset.pane === b.dataset.tab));
    }));

    const f = document.getElementById('routeFilter');
    f.addEventListener('input', () => { this.routeFilter = f.value.toLowerCase(); this.buildRoutes(); });
    document.getElementById('btnClearLog').addEventListener('click', () => {
      this.e.events.length = 0; this.refreshLog();
    });
  }

  /** The map key folds away - it is scaffolding once you know the marks. */
  _wireLegend() {
    const box = document.getElementById('legend');
    const btn = document.getElementById('legendToggle');
    if (!box || !btn) return;
    // short viewports have no room for the open key next to the panels
    if (window.innerHeight < 760) box.classList.add('closed');
    btn.addEventListener('click', () => {
      const closed = box.classList.toggle('closed');
      btn.title = closed ? 'Show the key' : 'Hide the key';
    });
  }

  _wireTransport() {
    document.getElementById('btnPlay').addEventListener('click', () => this.app.togglePlay());
    document.getElementById('btnReset').addEventListener('click', () => this.app.reset());
    document.querySelectorAll('.sbtn').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('.sbtn').forEach(x => x.classList.toggle('active', x === b));
      this.app.speed = +b.dataset.speed;
    }));
  }

  _wireSort() {
    document.querySelectorAll('.sortb').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('.sortb').forEach(x => x.classList.toggle('active', x === b));
      this.sort = b.dataset.sort;
      this.refreshBalances();
    }));
  }

  _wireInspector() {
    document.getElementById('inspClose').addEventListener('click', () => this.closeInspector());
    document.addEventListener('keydown', ev => { if (ev.key === 'Escape') this.closeInspector(); });
  }

  setPlaying(on) {
    const b = document.getElementById('btnPlay');
    b.textContent = on ? '❚❚' : '▶';
    b.classList.toggle('playing', on);
  }

  // ===================== chokepoints =====================
  buildChokes() {
    this.el.chokeList.innerHTML = '';
    for (const k of Object.values(this.e.chokes)) {
      const d = document.createElement('div');
      d.className = 'choke';
      d.dataset.id = k.id;
      d.innerHTML = `
        <div class="choke-top">
          <span class="choke-name">${k.name}</span>
          <span class="choke-load"></span>
        </div>
        <div class="choke-bar"><i></i></div>
        <div class="choke-ctl">
          <input type="range" min="0" max="100" step="5" value="100">
          <span class="choke-pct">100%</span>
        </div>
        <div class="choke-note">${k.note}</div>`;
      const range = d.querySelector('input');
      range.addEventListener('input', () => {
        this.e.setChokeCap(k.id, range.value / 100);
        this.refreshChokes(); this.refreshLog();
      });
      d.querySelector('.choke-name').addEventListener('click', () => {
        d.classList.toggle('open-note');
        this.v.flyTo(k.lat, k.lon, 4);
      });
      this.el.chokeList.appendChild(d);
    }
    this.refreshChokes();
  }

  refreshChokes() {
    for (const d of this.el.chokeList.children) {
      const k = this.e.chokes[d.dataset.id];
      const use = k.cap > 0 ? Math.min(1, k.load / k.cap) : 0;
      d.classList.toggle('closed', k.userCap <= 0.001);
      d.classList.toggle('limited', k.userCap > 0.001 && k.userCap < 0.99);
      d.querySelector('.choke-load').textContent = `${nf(k.load, 1)} / ${nf(k.cap, 1)} mb/d`;
      const bar = d.querySelector('.choke-bar i');
      bar.style.width = (use * 100).toFixed(0) + '%';
      bar.style.background = k.userCap <= 0.001 ? STATUS_COL.crisis
        : use > .92 ? STATUS_COL.alert : 'var(--flow)';
      d.querySelector('.choke-pct').textContent = Math.round(k.userCap * 100) + '%';
      const r = d.querySelector('input');
      if (document.activeElement !== r) r.value = Math.round(k.userCap * 100);
    }

    // Bypass pipelines: the saturation bar is the whole story of a Hormuz closure -
    // once Petroline is full, everyone downstream shares the same scraps.
    this.el.pipeList.innerHTML = Object.values(this.e.pipes).map(p => {
      const f = Math.min(1, p.load / p.cap);
      const full = f > 0.98;
      return `<div class="pipe-row" title="${p.note}">
        <span>${p.name}</span>
        <b style="color:${full ? STATUS_COL.alert : p.load > 0.01 ? STATUS_COL.ok : 'var(--txt-faint)'}">${nf(p.load, 2)} / ${nf(p.cap, 1)}</b>
        <div class="pipe-bar"><i style="width:${(f * 100).toFixed(0)}%;background:${full ? STATUS_COL.alert : 'var(--pipe)'}"></i></div>
      </div>`;
    }).join('');
  }

  // ===================== scenarios =====================
  buildScenarios() {
    this.el.scenarioList.innerHTML = '';
    for (const s of SCENARIOS) {
      const b = document.createElement('button');
      b.className = 'scen';
      b.innerHTML = `<div class="scen-top"><span class="scen-name">${s.name}</span>
        <span class="scen-tag ${s.tag}">${s.tag}</span></div>
        <div class="scen-desc">${s.desc}</div>`;
      b.addEventListener('click', () => {
        s.apply(this.e);
        this.e.log('warn', `Scenario applied: ${s.name}`, null);
        this.refreshChokes(); this.buildRoutes(); this.refreshLog();
      });
      this.el.scenarioList.appendChild(b);
    }
  }

  // ===================== route list =====================
  buildRoutes() {
    const q = this.routeFilter;
    const rows = Object.values(this.e.routes).filter(r => {
      if (!q) return true;
      const hay = (r.label + ' ' + this.e.countries[r.from].name + ' ' +
        this.e.countries[r.to].name + ' ' + r.mode).toLowerCase();
      return hay.includes(q);
    }).sort((a, b) => b.vol - a.vol);

    this.el.routeList.innerHTML = '';
    for (const r of rows) {
      const d = document.createElement('div');
      d.className = 'rrow';
      d.dataset.id = r.id;
      d.innerHTML = `
        <div class="rrow-top">
          <i class="rmode ${r.mode}"></i>
          <span class="rname" title="${r.label}">${r.from} → ${r.to} &middot; ${r.label}</span>
          <span class="rvol"></span>
        </div>
        <div class="rrow-ctl">
          <input type="range" min="0" max="100" step="5" value="${Math.round(r.userCap * 100)}">
          <span class="choke-pct">${Math.round(r.userCap * 100)}%</span>
          <span class="rerouted-tag"></span>
        </div>`;
      const range = d.querySelector('input');
      range.addEventListener('input', () => {
        this.e.setRouteCap(r.id, range.value / 100);
        this.refreshRouteRows(); this.refreshLog();
      });
      d.querySelector('.rname').addEventListener('click', () => this.openRoute(r.id));
      this.el.routeList.appendChild(d);
    }
    this.refreshRouteRows();
  }

  refreshRouteRows() {
    for (const d of this.el.routeList.children) {
      const r = this.e.routes[d.dataset.id];
      const alt = this.e._alt(r);
      d.classList.toggle('cut', r.flow <= 0.02 * Math.max(r.vol, 0.01));
      d.classList.toggle('rerouted', !!alt);
      d.querySelector('.rvol').textContent = `${nf(r.flow, 2)}/${nf(r.vol, 2)}`;
      d.querySelector('.rerouted-tag').textContent = alt ? '↪ diverted' : '';
      d.querySelector('.choke-pct').textContent = Math.round(r.userCap * 100) + '%';
      const range = d.querySelector('input');
      if (document.activeElement !== range) range.value = Math.round(r.userCap * 100);
    }
  }

  // ===================== country balances =====================
  refreshBalances() {
    const list = Object.values(this.e.countries);
    const maxCons = Math.max(...list.map(c => c.cons));

    list.sort((a, b) => {
      if (this.sort === 'cons') return b.cons - a.cons;
      if (this.sort === 'dep') return b.importDep - a.importDep;
      const r = STATUS_RANK[a.status] - STATUS_RANK[b.status];
      if (r !== 0) return r;
      const ae = a.prod > a.cons, be = b.prod > b.cons;
      if (ae !== be) return ae ? 1 : -1;
      return a.coverDays - b.coverDays;
    });

    this.el.balanceList.innerHTML = list.map(c => this._balanceRow(c, maxCons)).join('');
    for (const row of this.el.balanceList.children) {
      row.addEventListener('click', () => this.openCountry(row.dataset.id));
    }
  }

  _balanceRow(c, maxCons) {
    const isExp = c.prod > c.cons;
    const scale = 30 + 70 * (c.cons / maxCons);   // bar width tracks absolute demand

    let segs, right, tip;
    if (isExp) {
      const base = Math.max(0.001, c.netExport0);
      const sold = Math.min(1, (c.sold || 0) / base);
      const stuck = Math.max(0, 1 - sold);
      segs = `<i class="dom" style="width:${(sold * 100).toFixed(1)}%"></i>
              <i class="def" style="width:${(stuck * 100).toFixed(1)}%;opacity:.55"></i>`;
      right = `<b style="color:${c.shutIn > .05 ? STATUS_COL.crisis : 'var(--txt)'}">${nf(c.sold || 0, 1)}</b>exported`;
      tip = `${c.name}: exporting ${nf(c.sold || 0, 2)} of ${nf(c.netExport0, 2)} mb/d`;
    } else {
      const cons = Math.max(0.001, c.consEff);
      const dom = Math.min(c.prodEff, cons) / cons;
      const imp = Math.min((c.arrivals || 0) + (c.otherSupply || 0), cons * (1 - dom)) / cons;
      const def = Math.min(1 - dom - imp, (c.unmet || 0) / cons);
      const sto = Math.max(0, 1 - dom - imp - def);
      segs = [[dom, 'dom'], [imp, 'imp'], [sto, 'sto'], [def, 'def']]
        .map(([f, k]) => f > 0.002 ? `<i class="${k}" style="width:${(f * 100).toFixed(1)}%"></i>` : '').join('');
      const col = c.coverDays < 12 ? STATUS_COL.crisis : c.coverDays < 30 ? STATUS_COL.alert : 'var(--txt)';
      right = `<b style="color:${col}">${Math.round(c.coverDays)}</b>days cover`;
      tip = `${c.name}: ${nf(c.cons, 2)} mb/d demand, ${(c.importDep * 100).toFixed(0)}% imported`;
    }

    return `<div class="brow ${this.selCountry === c.id ? 'sel' : ''}" data-id="${c.id}" title="${tip}">
      <div class="bname"><i style="background:${STATUS_COL[c.status]}"></i><span>${c.name}</span></div>
      <div style="width:${scale}%"><div class="bbar">${segs}</div></div>
      <div class="bcover">${right}</div>
    </div>`;
  }

  // ===================== KPIs =====================
  refreshKPIs() {
    const s = this.e.snapshot();
    this.el.simDate.textContent = s.date;
    this.el.simDay.textContent = s.day;

    const crisisCount = Object.values(this.e.countries).filter(c => c.unmet > 0.001).length;

    setKpi('kpiPrice', nf(s.price, 0), 'USD/bbl',
      `${s.price > MODEL.basePrice ? '+' : ''}${nf((s.price / MODEL.basePrice - 1) * 100, 0)}% vs baseline`,
      s.price > 160 ? 'crit' : s.price > 105 ? 'hot' : '');

    setKpi('kpiGap', nf(Math.max(0, s.gap) * 100, 1), '%', 'demand vs supply',
      s.gap > 0.04 ? 'crit' : s.gap > 0.012 ? 'hot' : '');

    setKpi('kpiUnmet', nf(s.unmet, 2), 'mb/d',
      `${crisisCount} ${crisisCount === 1 ? 'country' : 'countries'} short`,
      s.unmet > 1 ? 'crit' : s.unmet > 0.01 ? 'hot' : '');

    setKpi('kpiCover', Math.round(s.cover), 'days', 'importers, weighted average',
      s.cover < 25 ? 'crit' : s.cover < 45 ? 'hot' : '');
  }

  // ===================== log =====================
  refreshLog() {
    this.el.log.innerHTML = this.e.events.slice(0, 90).map(ev =>
      `<div class="lrow ${ev.kind}"><span class="lday">${ev.day ? 'd+' + ev.day : 'start'}</span><span class="ltxt">${ev.text}</span></div>`
    ).join('') || '<div class="lrow"><span class="ltxt" style="color:var(--txt-faint)">No events yet. Close a chokepoint or run a scenario.</span></div>';
  }

  // ===================== inspector =====================
  openRoute(id) {
    const r = this.e.routes[id];
    const from = this.e.countries[r.from], to = this.e.countries[r.to];
    const alt = this.e._alt(r);
    const via = this.e._viaOf(r);

    const altBtns = (r.alts || []).map(a => {
      const feasible = this.e._altFeasible(r, a);
      const pipe = a.requires ? this.e.pipes[a.requires] : null;
      return `<button class="altbtn ${alt && alt.id === a.id ? 'active' : ''} ${feasible ? '' : 'blocked'}"
                 data-alt="${a.id}" ${feasible ? '' : 'disabled'}>
        ${a.label}
        <small>${a.addDays >= 0 ? '+' : ''}${a.addDays} days transit${pipe ? ` &middot; pipeline limit ${nf(pipe.cap, 1)} mb/d (now ${nf(pipe.load, 2)})` : ''}${feasible ? '' : ' &middot; this variant is blocked too'}</small>
      </button>`;
    }).join('');

    this.el.inspBody.innerHTML = `
      <h2>${r.label}</h2>
      <div class="sub">${from.name} → ${to.name} &middot; ${r.mode === 'pipe' ? 'pipeline' : 'sea route'}</div>
      <div class="ispec">
        <div><span>Flow today</span><b>${nf(r.flow, 2)} mb/d</b></div>
        <div><span>Baseline volume</span><b>${nf(r.vol, 2)} mb/d</b></div>
        <div><span>Transit time</span><b>${this.e._transitDays(r)} days</b></div>
        <div><span>Oil at sea</span><b>${nf(r.inTransit, 1)} mn bbl</b></div>
      </div>
      ${via.length ? `<h4>Passes through</h4>
        <div style="font-size:11.5px;line-height:1.7">${via.map(v => {
          const k = this.e.chokes[v]; if (!k) return v;
          const cls = k.userCap <= .001 ? STATUS_COL.crisis : k.userCap < .99 ? STATUS_COL.alert : STATUS_COL.ok;
          return `<span style="color:${cls}">● ${k.name} (${Math.round(k.userCap * 100)}%)</span>`;
        }).join('<br>')}</div>` : ''}
      <h4>Route capacity</h4>
      <div class="choke-ctl">
        <input id="inspCap" type="range" min="0" max="100" step="5" value="${Math.round(r.userCap * 100)}">
        <span class="choke-pct" id="inspCapV">${Math.round(r.userCap * 100)}%</span>
      </div>
      ${r.note ? `<div class="hint" style="margin-top:8px">${r.note}</div>` : ''}
      <h4>Reroute</h4>
      ${altBtns || '<div class="hint">No alternative variant. Cutting this route means the volume is simply lost.</div>'}
      ${(r.alts || []).length ? `<button class="altbtn ${alt ? '' : 'active'}" data-alt="">Primary route<small>${r.days} days transit</small></button>` : ''}`;

    const cap = document.getElementById('inspCap');
    cap.addEventListener('input', () => {
      document.getElementById('inspCapV').textContent = cap.value + '%';
      this.e.setRouteCap(id, cap.value / 100);
      this.refreshRouteRows(); this.refreshLog();
    });
    this.el.inspBody.querySelectorAll('.altbtn[data-alt]').forEach(b => {
      if (b.disabled) return;
      b.addEventListener('click', () => {
        this.e.setRouteAlt(id, b.dataset.alt || null);
        this.refreshRouteRows(); this.refreshLog();
        this.openRoute(id);
      });
    });

    this.el.inspector.classList.remove('hidden');
    this.v.select({ type: 'route', id });
  }

  openCountry(id) {
    const c = this.e.countries[id];
    this.selCountry = id;
    const isExp = c.prod > c.cons;

    const list = Object.values(this.e.routes)
      .filter(r => (isExp ? r.from : r.to) === id)
      .sort((a, b) => b.vol - a.vol);

    const rows = list.map(r => {
      const pct = r.vol > 0 ? r.flow / r.vol : 0;
      const col = pct < .05 ? STATUS_COL.crisis : pct < .6 ? STATUS_COL.alert : STATUS_COL.ok;
      const other = this.e.countries[isExp ? r.to : r.from].name;
      const via = this.e._viaOf(r).map(v => this.e.chokes[v] ? this.e.chokes[v].short : v).join(', ');
      return `<div class="rrow" style="cursor:pointer" data-route="${r.id}">
        <div class="rrow-top">
          <i class="rmode ${r.mode}"></i>
          <span class="rname">${other} &middot; ${r.label}</span>
          <span class="rvol" style="color:${col}">${nf(r.flow, 2)}/${nf(r.vol, 2)}</span>
        </div>
        ${via ? `<div class="rvia">via ${via}</div>` : ''}
      </div>`;
    }).join('') || '<div class="hint">No modelled routes.</div>';

    const spec = isExp ? `
      <div><span>Output</span><b>${nf(c.prodEff, 2)}<small style="font-size:10px;color:var(--txt-faint)"> / ${nf(c.prod, 2)}</small></b></div>
      <div><span>Exports today</span><b>${nf(c.sold || 0, 2)} mb/d</b></div>
      <div><span>Oil with no buyer</span><b>${nf(c.surplusMb, 0)} mn bbl</b></div>
      <div><span>Shut-in wells</span><b style="color:${c.shutIn > .05 ? STATUS_COL.crisis : 'inherit'}">${nf(c.shutIn, 2)} mb/d</b></div>
    ` : `
      <div><span>Consumption</span><b>${nf(c.consEff, 2)} mb/d</b></div>
      <div><span>Daily balance</span><b style="color:${c.balance < 0 ? STATUS_COL.crisis : STATUS_COL.ok}">${c.balance >= 0 ? '+' : ''}${nf(c.balance, 2)}</b></div>
      <div><span>Stocks</span><b>${Math.round(c.coverDays)} days</b></div>
      <div><span>Import dependence</span><b>${(c.importDep * 100).toFixed(0)}%</b></div>`;

    this.el.inspBody.innerHTML = `
      <h2>${c.name}</h2>
      <div class="sub">${isExp ? 'net exporter' : 'net importer'} &middot; ${c.group}</div>
      <div class="ispec">${spec}</div>
      ${c.unmet > 0.001 ? `<div class="choke closed" style="margin-bottom:12px">
        <b style="color:${STATUS_COL.crisis}">Shortfall: ${nf(c.unmet, 2)} mb/d (${(c.unmetPct * 100).toFixed(0)}% of demand)</b>
        <div class="choke-note" style="display:block">Cumulative deficit: ${nf(c.cumUnmetMb, 0)} mn bbl since the start of the run.</div>
      </div>` : ''}
      ${!isExp ? `<button class="altbtn" id="btnSPR">Release strategic reserves
        <small>+10% of opening stocks (${nf(c.stockMb0 * 0.1, 0)} mn bbl) &mdash; one shot per click</small></button>` : ''}
      <h4>${isExp ? 'Export routes' : 'Supply routes'} (${list.length})</h4>
      ${rows}`;

    const spr = document.getElementById('btnSPR');
    if (spr) spr.addEventListener('click', () => {
      this.e.releaseReserves(id); this.refreshLog(); this.refreshBalances(); this.openCountry(id);
    });
    this.el.inspBody.querySelectorAll('[data-route]').forEach(el =>
      el.addEventListener('click', () => this.openRoute(el.dataset.route)));

    this.el.inspector.classList.remove('hidden');
    this.v.select({ type: 'country', id });   // lights up its supply/export routes
    this.v.focus(id);
    this.refreshBalances();
  }

  openChoke(id) {
    const k = this.e.chokes[id];
    const routes = Object.values(this.e.routes).filter(r => this.e._viaOf(r).includes(id))
      .sort((a, b) => b.flow - a.flow);
    this.el.inspBody.innerHTML = `
      <h2>${k.name}</h2>
      <div class="sub">chokepoint of the world oil trade</div>
      <div class="ispec">
        <div><span>Capacity</span><b>${nf(k.cap, 1)} mb/d</b></div>
        <div><span>Modelled traffic</span><b>${nf(k.load, 2)} mb/d</b></div>
        <div><span>Setting</span><b>${Math.round(k.userCap * 100)}%</b></div>
        <div><span>Routes</span><b>${routes.length}</b></div>
      </div>
      <div class="hint">${k.note}</div>
      <h4>Throughput</h4>
      <div class="choke-ctl">
        <input id="inspCap" type="range" min="0" max="100" step="5" value="${Math.round(k.userCap * 100)}">
        <span class="choke-pct" id="inspCapV">${Math.round(k.userCap * 100)}%</span>
      </div>
      <h4>Countries exposed</h4>
      ${this._exposure(routes)}
      <h4>Routes through here</h4>
      ${routes.map(r => `<div class="rrow" style="cursor:pointer" data-route="${r.id}">
        <div class="rrow-top"><i class="rmode ${r.mode}"></i>
        <span class="rname">${r.label}</span>
        <span class="rvol">${nf(r.flow, 2)}/${nf(r.vol, 2)}</span></div></div>`).join('') ||
        '<div class="hint">No modelled route currently uses this passage.</div>'}`;

    const cap = document.getElementById('inspCap');
    cap.addEventListener('input', () => {
      document.getElementById('inspCapV').textContent = cap.value + '%';
      this.e.setChokeCap(id, cap.value / 100);
      this.refreshChokes(); this.refreshLog();
    });
    this.el.inspBody.querySelectorAll('[data-route]').forEach(el =>
      el.addEventListener('click', () => this.openRoute(el.dataset.route)));
    this.el.inspBody.querySelectorAll('[data-country]').forEach(el =>
      el.addEventListener('click', () => this.openCountry(el.dataset.country)));

    this.el.inspector.classList.remove('hidden');
    this.v.select({ type: 'choke', id });   // lights up every route and country behind it
  }

  /**
   * How much each country rides on a single chokepoint: for importers, the share
   * of their demand arriving through it; for exporters, the share of their exports
   * leaving through it. This is what separates a diversified buyer from one whose
   * supply hangs off a single strait.
   */
  _exposure(routes) {
    const imp = {}, exp = {};
    for (const r of routes) {
      imp[r.to] = (imp[r.to] || 0) + r.vol;
      exp[r.from] = (exp[r.from] || 0) + r.vol;
    }
    const rows = [];
    for (const [id, v] of Object.entries(imp)) {
      const c = this.e.countries[id];
      if (c.prod > c.cons) continue;
      rows.push({ c, v, pct: v / c.cons, side: 'of demand' });
    }
    for (const [id, v] of Object.entries(exp)) {
      const c = this.e.countries[id];
      if (c.prod <= c.cons) continue;
      rows.push({ c, v, pct: v / Math.max(0.001, c.netExport0), side: 'of exports' });
    }
    if (!rows.length) return '<div class="hint">Nobody in the model depends on this passage.</div>';
    rows.sort((a, b) => b.pct - a.pct);

    return rows.map(({ c, v, pct }) => {
      const col = pct > .5 ? STATUS_COL.crisis : pct > .25 ? STATUS_COL.alert : STATUS_COL.watch;
      return `<div class="exrow" data-country="${c.id}" title="${nf(v, 2)} mb/d through this chokepoint">
        <span class="exname">${c.name}</span>
        <div class="exbar"><i style="width:${(Math.min(1, pct) * 100).toFixed(0)}%;background:${col}"></i></div>
        <span class="expct" style="color:${col}">${(pct * 100).toFixed(0)}%</span>
      </div>`;
    }).join('');
  }

  closeInspector() {
    this.el.inspector.classList.add('hidden');
    this.v.select(null);
  }
}

// --- helpers ----------------------------------------------------------------
function nf(v, d = 1) {
  return (v == null || isNaN(v)) ? '—' : v.toFixed(d);
}

function setKpi(id, val, unit, delta, cls) {
  const el = document.getElementById(id);
  el.querySelector('.kval').innerHTML = `${val}<small>${unit}</small>`;
  el.querySelector('.kdelta').textContent = delta;
  el.className = 'kpi ' + (cls || '');
}
