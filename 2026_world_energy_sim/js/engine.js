/**
 * Simulation engine - one step = one day.
 *
 * The daily loop:
 *   1. pick the route variant (primary / diversion)
 *   2. desired flow -> chokepoint limits -> bypass pipeline limits
 *      -> exporter limit (nobody ships more oil than they have)
 *   3. loading -> transit queue; oil sails for X days, so cutting a route
 *      today only reaches the buyer X days from now
 *   4. arrivals -> country balance -> stocks -> unmet demand
 *   5. an exporter with no buyer fills storage, then shuts in wells
 *   6. world price from the supply gap, damped by the level of stocks
 *
 * Every country's balance closes by construction:
 *   supply = own output + route arrivals + off-model supply
 *   use    = consumption + route departures + off-model sales
 * The difference lands in stocks. "Off-model" is the dispersed spot trade
 * that tops up real volumes and cannot be severed by one cut.
 */

class OilEngine {
  constructor() { this.reset(); }

  reset() {
    this.day = 0;
    this.startDate = new Date(2026, 0, 1);
    this.price = MODEL.basePrice;
    this.gap = 0;
    this.availFactor = 1;
    this.demandFactor = 1;
    this.history = [];
    this.events = [];

    this.countries = {};
    for (const c of COUNTRIES) {
      this.countries[c.id] = {
        ...c,
        stockMb: c.stock * c.cons,   // stocks in mn bbl
        stockMb0: c.stock * c.cons,
        prodEff: c.prod,
        consEff: c.cons,
        shutIn: 0,
        surplusMb: 0,
        arrivals: 0,
        sold: 0,
        balance: 0,
        unmet: 0,
        unmetPct: 0,
        cumUnmetMb: 0,
        strandedToday: 0,
        status: 'ok',
        prevStatus: 'ok',
      };
    }

    this.routes = {};
    for (const r of ROUTES) {
      this.routes[r.id] = {
        ...r,
        userCap: r.disabled ? 0 : 1,
        altId: null,
        manualAlt: false,
        flow: r.vol,
        queue: [],
        inTransit: 0,
      };
    }

    this.chokes = {};
    for (const k of CHOKEPOINTS) this.chokes[k.id] = { ...k, userCap: 1, load: 0, baseLoad: 0 };

    this.pipes = {};
    for (const p of INFRASTRUCTURE) this.pipes[p.id] = { ...p, load: 0 };

    this.autoReroute = true;
    this._computeBaseline();
    this._primeTransit();
    this._recalcCountries();
    this._record();
  }

  // --- Baseline equilibrium ------------------------------------------------
  _computeBaseline() {
    const inflow = {}, outflow = {};
    for (const r of ROUTES) {
      inflow[r.to] = (inflow[r.to] || 0) + r.vol;
      outflow[r.from] = (outflow[r.from] || 0) + r.vol;
    }

    for (const c of Object.values(this.countries)) {
      c.routedImports0 = inflow[c.id] || 0;
      c.routedExports0 = outflow[c.id] || 0;
      c.netImport0 = Math.max(0, c.cons - c.prod);
      c.netExport0 = Math.max(0, c.prod - c.cons);

      // What is missing (or left over) once modelled routes are accounted for.
      // Positive = the country tops up on the spot market, negative = it sells off-model.
      const need = c.cons + c.routedExports0 - c.prod - c.routedImports0;
      c.otherSupply0 = Math.max(0, need);
      c.otherExport0 = Math.max(0, -need);
      c.otherSupply = c.otherSupply0;
      c.otherExportNow = c.otherExport0;

      // opening state = equilibrium
      c.arrivals = c.routedImports0;
      c.sold = c.routedExports0 + c.otherExport0;
    }

    this.baseSupply = COUNTRIES.reduce((s, c) => s + c.prod, 0);
    this.baseDemand = COUNTRIES.reduce((s, c) => s + c.cons, 0);
    // We model 34 countries, not the whole planet, so this system carries its
    // own surplus (the remaining buyers sit outside the grid). Price is measured
    // as the DEVIATION from that equilibrium - otherwise small disruptions would
    // fall into a dead zone and never move it.
    this.baseGap = this.baseDemand - this.baseSupply;

    for (const k of Object.values(this.chokes)) k.baseLoad = 0;
    for (const r of ROUTES) {
      for (const v of r.via) if (this.chokes[v]) this.chokes[v].baseLoad += r.vol;
      for (const v of r.via) if (this.chokes[v]) this.chokes[v].load = this.chokes[v].baseLoad;
    }
  }

  /** Fills the sea with tankers so day 0 does not start with empty routes. */
  _primeTransit() {
    for (const r of Object.values(this.routes)) {
      const days = this._transitDays(r);
      for (let d = 1; d <= days; d++) r.queue.push({ arriveDay: d, vol: r.vol * r.userCap });
      r.inTransit = r.vol * r.userCap * days;
    }
  }

  // --- Helpers -------------------------------------------------------------
  _alt(r) { return r.altId ? (r.alts || []).find(a => a.id === r.altId) : null; }
  _viaOf(r) { const a = this._alt(r); return a ? a.via : r.via; }
  _pathOf(r) { const a = this._alt(r); return a ? a.path : r.path; }
  _transitDays(r) { const a = this._alt(r); return Math.max(1, r.days + (a ? a.addDays : 0)); }

  _passabilityOf(via) {
    let f = 1;
    for (const v of via) {
      const k = this.chokes[v];
      if (k) f = Math.min(f, k.userCap);
    }
    return f;
  }

  _passability(r) { return this._passabilityOf(this._viaOf(r)); }

  _altFeasible(r, a) {
    return !a.via.some(v => this.chokes[v] && this.chokes[v].userCap <= 0.001);
  }

  get date() {
    const d = new Date(this.startDate);
    d.setDate(d.getDate() + this.day);
    return d;
  }

  // =========================== ONE DAY =====================================
  step() {
    this.day++;

    // demand response to price (short-run elasticity) and global availability
    this.demandFactor = Math.pow(this.price / MODEL.basePrice, -MODEL.demandElasticity);
    const supplyNow = Object.values(this.countries).reduce((s, c) => s + c.prodEff, 0);
    this.availFactor = Math.min(1, supplyNow / this.baseSupply);
    for (const c of Object.values(this.countries)) {
      c.consEff = c.cons * this.demandFactor;
      c.otherSupply = c.otherSupply0 * this.availFactor;
    }

    this._chooseVariants();
    const desired = this._desiredFlows();
    this._applyChokeLimits(desired);
    this._applyPipeLimits(desired);
    this._applyExporterLimits(desired);
    this._dispatch(desired);
    this._deliver();
    this._balance();
    this._updatePrice();
    this._recalcCountries();
    this._record();
  }

  /**
   * Automatic diversion. Shippers do not wait for a full closure: once the
   * primary route drops below `rerouteBelow` passability they take the best
   * available variant, and only come back above `rerouteBack` (hysteresis
   * keeps the fleet from flip-flopping day to day).
   */
  _chooseVariants() {
    if (!this.autoReroute) return;
    for (const r of Object.values(this.routes)) {
      if (r.manualAlt) continue;
      const pMain = this._passabilityOf(r.via);

      if (r.altId) {
        if (pMain >= MODEL.rerouteBack) {
          r.altId = null;
          this.log('reroute', `${r.label}: back on the primary route`, r.from);
        }
        continue;
      }
      if (pMain >= MODEL.rerouteBelow) continue;

      let best = null, bestP = pMain;
      for (const a of (r.alts || [])) {
        const p = this._passabilityOf(a.via);
        if (p > bestP + 1e-6) { bestP = p; best = a; }
      }
      if (best) {
        r.altId = best.id;
        this.log('reroute', `${r.label}: diverting → ${best.label} (${best.addDays >= 0 ? '+' : ''}${best.addDays} days)`, r.from);
      }
    }
  }

  _desiredFlows() {
    const d = {};
    for (const r of Object.values(this.routes)) d[r.id] = r.vol * r.userCap * this._passability(r);
    return d;
  }

  /** Chokepoint capacity is a hard ceiling - any excess is scaled back pro rata. */
  _applyChokeLimits(desired) {
    for (let pass = 0; pass < 5; pass++) {
      const load = {};
      for (const r of Object.values(this.routes)) {
        for (const v of this._viaOf(r)) load[v] = (load[v] || 0) + desired[r.id];
      }
      let changed = false;
      for (const k of Object.values(this.chokes)) {
        const limit = k.cap * k.userCap;
        const cur = load[k.id] || 0;
        if (cur > limit + 1e-6) {
          const f = limit / cur;
          for (const r of Object.values(this.routes)) {
            if (this._viaOf(r).includes(k.id)) desired[r.id] *= f;
          }
          changed = true;
        }
      }
      if (!changed) break;
    }
    const load = {};
    for (const r of Object.values(this.routes)) {
      for (const v of this._viaOf(r)) load[v] = (load[v] || 0) + desired[r.id];
    }
    for (const k of Object.values(this.chokes)) k.load = load[k.id] || 0;
  }

  /** Bypass pipelines have their own low ceilings - that is the crux of "routing around Hormuz". */
  _applyPipeLimits(desired) {
    const load = {};
    for (const r of Object.values(this.routes)) {
      const a = this._alt(r);
      if (a && a.requires) load[a.requires] = (load[a.requires] || 0) + desired[r.id];
    }
    for (const p of Object.values(this.pipes)) {
      const cur = load[p.id] || 0;
      p.load = Math.min(cur, p.cap);
      if (cur > p.cap + 1e-6) {
        const f = p.cap / cur;
        for (const r of Object.values(this.routes)) {
          const a = this._alt(r);
          if (a && a.requires === p.id) desired[r.id] *= f;
        }
      }
    }
  }

  /** Nobody ships more than they hold: output + arrivals - consumption + some stock. */
  _applyExporterLimits(desired) {
    const out = {};
    for (const r of Object.values(this.routes)) out[r.from] = (out[r.from] || 0) + desired[r.id];

    for (const c of Object.values(this.countries)) {
      const want = out[c.id] || 0;
      if (want <= 1e-6) continue;
      const avail = c.prodEff + c.arrivals + c.otherSupply - c.consEff - c.otherExportNow
                  + c.stockMb * 0.02;   // daily drawdown allowed from storage
      if (want > avail + 1e-6) {
        const f = Math.max(0, avail) / want;
        for (const r of Object.values(this.routes)) if (r.from === c.id) desired[r.id] *= f;
      }
    }
  }

  _dispatch(desired) {
    for (const r of Object.values(this.routes)) {
      r.flow = desired[r.id];
      r.queue.push({ arriveDay: this.day + this._transitDays(r), vol: r.flow });
    }
  }

  _deliver() {
    for (const c of Object.values(this.countries)) c.arrivals = 0;
    for (const r of Object.values(this.routes)) {
      const keep = [];
      let inT = 0;
      for (const q of r.queue) {
        if (q.arriveDay <= this.day) this.countries[r.to].arrivals += q.vol;
        else { keep.push(q); inT += q.vol; }
      }
      r.queue = keep;
      r.inTransit = inT;
    }
  }

  _balance() {
    const outflow = {};
    for (const r of Object.values(this.routes)) outflow[r.from] = (outflow[r.from] || 0) + r.flow;

    for (const c of Object.values(this.countries)) {
      const isExp = c.prod > c.cons;
      const dispatched = outflow[c.id] || 0;

      // Off-model sales shrink too: an exporter with shut-in wells has less oil,
      // and a refining hub (Italy, Netherlands, India) starved of crude stops
      // re-exporting products.
      c.otherExportNow = c.otherExport0 * (isExp
        ? (c.prod > 0 ? c.prodEff / c.prod : 1)
        : (c.routedImports0 > 0 ? Math.min(1, c.arrivals / c.routedImports0) : 1));

      const supply = c.prodEff + c.arrivals + c.otherSupply;
      const use = c.consEff + dispatched + c.otherExportNow;

      c.sold = dispatched + c.otherExportNow;
      c.balance = supply - use;
      c.stockMb += c.balance;

      c.unmet = 0;
      if (c.stockMb < 0) {
        c.unmet = Math.min(c.consEff, -c.stockMb);
        c.cumUnmetMb += c.unmet;
        c.stockMb = 0;
      }

      // Storage ceiling. For an exporter, breaching it means the oil has
      // nowhere to go - wells have to be shut in.
      const cap = isExp ? c.stockMb0 + c.store : c.stockMb0 * 1.6 + 30;
      if (c.stockMb > cap) {
        const over = c.stockMb - cap;
        c.stockMb = cap;
        if (isExp) c.shutIn = Math.min(c.prod * 0.9, c.shutIn + over * MODEL.shutInRate);
      }

      // Output comes back once storage starts draining again
      if (isExp && c.shutIn > 0 && c.balance < -1e-3) {
        c.shutIn = Math.max(0, c.shutIn - c.prod * MODEL.restartRate);
      }
      if (isExp) c.prodEff = Math.max(0, c.prod - c.shutIn);

      c.surplusMb = Math.max(0, c.stockMb - c.stockMb0);
      // oil produced but parked in storage instead of reaching the market
      c.strandedToday = isExp ? Math.max(0, c.balance) : 0;
    }
  }

  _updatePrice() {
    const supply = Object.values(this.countries).reduce((s, c) => s + c.prodEff, 0);
    const demand = Object.values(this.countries).reduce((s, c) => s + c.consEff, 0);
    const stranded = Object.values(this.countries).reduce((s, c) => s + c.strandedToday, 0);

    const gap = (demand - supply + stranded - this.baseGap) / this.baseDemand;

    const cover = this._globalCover();
    const cushion = 1 - MODEL.stockCushion * Math.min(1, cover / 60);
    const target = MODEL.basePrice * (1 + Math.max(0, gap) / MODEL.demandElasticity * cushion);

    this.price += (Math.min(MODEL.maxPrice, target) - this.price) * MODEL.priceSmoothing;
    this.price = Math.max(20, this.price);
    this.gap = gap;
  }

  _globalCover() {
    const imp = Object.values(this.countries).filter(c => c.cons > c.prod);
    const stock = imp.reduce((s, c) => s + c.stockMb, 0);
    const cons = imp.reduce((s, c) => s + c.consEff, 0);
    return cons > 0 ? stock / cons : 999;
  }

  _recalcCountries() {
    for (const c of Object.values(this.countries)) {
      c.coverDays = c.consEff > 0 ? c.stockMb / c.consEff : 999;
      c.importDep = c.cons > 0 ? Math.max(0, (c.cons - c.prod) / c.cons) : 0;
      c.unmetPct = c.consEff > 0 ? c.unmet / c.consEff : 0;

      let s;
      if (c.unmet > 1e-3) s = 'crisis';
      else if (c.prod > c.cons) s = c.shutIn > 0.05 ? 'shutin' : 'ok';
      else if (c.coverDays < MODEL.thresholds.alert) s = 'crisis';
      else if (c.coverDays < MODEL.thresholds.watch) s = 'alert';
      else if (c.coverDays < MODEL.thresholds.ok) s = 'watch';
      else s = 'ok';

      if (s !== c.status) {
        c.prevStatus = c.status;
        c.status = s;
        if (this.day > 0) this._statusEvent(c);
      }
    }
  }

  _statusEvent(c) {
    const rank = { ok: 0, shutin: 1, watch: 1, alert: 2, crisis: 3 };
    if (rank[c.status] <= rank[c.prevStatus]) {
      if (c.status === 'ok') this.log('good', `${c.name}: back to normal`, c.id);
      return;
    }
    const msg = {
      watch:  `${c.name}: stocks below ${MODEL.thresholds.ok} days of cover`,
      alert:  `${c.name}: ALERT - stocks below ${MODEL.thresholds.watch} days`,
      shutin: `${c.name}: storage full, shutting in production`,
      crisis: c.unmet > 0
        ? `${c.name}: SHORTAGE - ${(c.unmetPct * 100).toFixed(0)}% of demand unmet`
        : `${c.name}: CRITICAL - stocks below ${MODEL.thresholds.alert} days`,
    }[c.status];
    if (msg) this.log(c.status === 'crisis' ? 'bad' : 'warn', msg, c.id);
  }

  _record() {
    const unmet = Object.values(this.countries).reduce((s, c) => s + c.unmet, 0);
    const supply = Object.values(this.countries).reduce((s, c) => s + c.prodEff, 0);
    this.history.push({ day: this.day, price: this.price, unmet, supply, cover: this._globalCover() });
    if (this.history.length > 3000) this.history.shift();
  }

  log(kind, text, country) {
    this.events.unshift({ day: this.day, kind, text, country });
    if (this.events.length > 300) this.events.pop();
  }

  dateStr(d) {
    return (d || this.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  // --- Controls driven by the UI -------------------------------------------
  setChokeCap(id, v) {
    const k = this.chokes[id];
    if (!k) return;
    const was = k.userCap;
    k.userCap = Math.max(0, Math.min(1, v));
    if (was > 0.001 && k.userCap <= 0.001) this.log('bad', `${k.name}: CLOSED`, null);
    else if (was <= 0.001 && k.userCap > 0.001) this.log('good', `${k.name}: reopened`, null);
    else if (Math.abs(was - k.userCap) > 0.001)
      this.log('warn', `${k.name}: throughput ${Math.round(k.userCap * 100)}% (${(k.cap * k.userCap).toFixed(1)} mb/d)`, null);
  }

  setRouteCap(id, v) {
    const r = this.routes[id];
    if (!r) return;
    const was = r.userCap;
    r.userCap = Math.max(0, Math.min(1, v));
    if (Math.abs(was - r.userCap) > 0.001)
      this.log('warn', `${r.label}: capacity ${Math.round(r.userCap * 100)}%`, r.from);
  }

  setRouteAlt(id, altId) {
    const r = this.routes[id];
    if (!r) return;
    r.altId = altId;
    r.manualAlt = altId !== null;
    const a = this._alt(r);
    this.log('reroute', a ? `${r.label}: forced → ${a.label}` : `${r.label}: primary route`, r.from);
  }

  releaseReserves(id) {
    const c = this.countries[id];
    if (!c) return;
    const add = c.stockMb0 * 0.1;
    c.stockMb += add;
    this.log('good', `${c.name}: strategic reserve release (+${add.toFixed(0)} mn bbl)`, id);
  }

  snapshot() {
    return {
      day: this.day,
      date: this.dateStr(),
      price: this.price,
      gap: this.gap || 0,
      cover: this._globalCover(),
      unmet: Object.values(this.countries).reduce((s, c) => s + c.unmet, 0),
      shutIn: Object.values(this.countries).reduce((s, c) => s + c.shutIn, 0),
    };
  }
}
