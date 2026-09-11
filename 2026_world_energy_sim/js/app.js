/** Wiring: simulation clock, animation loop, throttled UI refresh. */

class App {
  constructor() {
    this.engine = new OilEngine();

    this.view = new MapView(this.engine, {
      onRoute:   id => this.ui.openRoute(id),
      onCountry: id => this.ui.openCountry(id),
      onChoke:   id => this.ui.openChoke(id),
      onBlank:   () => this.ui.closeInspector(),
    });

    this.ui = new UI(this.engine, this.view, this);

    this.playing = false;
    this.speed = 3;            // simulated days per second
    this.acc = 0;              // fractional-day accumulator
    this.lastT = performance.now();
    this.lastUi = 0;
    this.uiTick = 0;

    this.ui.refreshBalances();
    this.ui.refreshKPIs();
    this.ui.refreshLog();
    this.ui.drawChart();

    this._wireKeys();
    requestAnimationFrame(t => this.loop(t));
  }

  _wireKeys() {
    document.addEventListener('keydown', e => {
      if (e.target.tagName === 'INPUT') return;
      if (e.code === 'Space') { e.preventDefault(); this.togglePlay(); }
      if (e.key >= '1' && e.key <= '4') {
        const b = document.querySelectorAll('.sbtn')[+e.key - 1];
        if (b) b.click();
      }
    });
    window.addEventListener('resize', () => this.ui.drawChart());
  }

  togglePlay() {
    this.playing = !this.playing;
    this.lastT = performance.now();
    this.ui.setPlaying(this.playing);
  }

  reset() {
    this.playing = false;
    this.ui.setPlaying(false);
    this.engine.reset();
    this.view.routeState = {};        // drop cached paths and tanker phases
    this.ui.buildChokes();
    this.ui.buildRoutes();
    this.ui.refreshBalances();
    this.ui.refreshKPIs();
    this.engine.log('good', 'Simulation reset to baseline', null);
    this.ui.refreshLog();
    this.ui.drawChart();
  }

  loop(t) {
    const dt = Math.min(0.25, (t - this.lastT) / 1000);   // guard against tab-switch jumps
    this.lastT = t;

    if (this.playing) {
      const dDays = dt * this.speed;
      this.acc += dDays;
      let guard = 0;
      while (this.acc >= 1 && guard++ < 40) {
        this.engine.step();
        this.acc -= 1;
      }
      this.view.animate(dDays);
    }

    // The map redraws every frame: it carries the pulses, hover state and pan.
    // Guarded: a throw here used to kill requestAnimationFrame for good, which
    // looked like "the map froze and the country glyphs vanished".
    try {
      this.view.draw();
    } catch (err) {
      if (!this._drawFailed) { this._drawFailed = true; console.error('map draw failed:', err); }
    }

    // Panels are heavier, so they refresh 8x/s and the big lists every third pass.
    if (t - this.lastUi > 125) {
      this.lastUi = t;
      this.uiTick++;
      this.ui.refreshKPIs();
      if (this.uiTick % 3 === 0) {
        this.ui.refreshBalances();
        this.ui.refreshRouteRows();
        this.ui.refreshChokes();
        this.ui.refreshLog();
        this.ui.drawChart();
      }
    }

    requestAnimationFrame(x => this.loop(x));
  }
}

window.addEventListener('load', () => { window.app = new App(); });
