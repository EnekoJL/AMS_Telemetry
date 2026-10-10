/**
 * High-performance Speed Telemetry Chart using uPlot.
 * Fixed scale ranges (0 to 400 km/h), Neon Green curve & Hot Pink cursor.
 */

export class TelemetryChart {
  constructor(containerId, onCursorMove) {
    this.container = document.getElementById(containerId);
    this.onCursorMove = onCursorMove;
    this.uplot = null;
    this.points = [];
    this.mode = "time"; // "time" or "distance"
    this.currentIndex = 0;
    this.lastW = 0;
    this.lastH = 0;

    // Observe parent container to prevent feedback loops with uPlot canvas
    const parentEl = this.container ? this.container.parentElement : null;
    if (parentEl) {
      this.resizeObserver = new ResizeObserver(() => {
        this.handleResize();
      });
      this.resizeObserver.observe(parentEl);
    }
  }

  setMode(mode) {
    if (this.mode === mode) return;
    this.mode = mode;
    this.render();
  }

  loadData(points) {
    this.points = points;
    this.render();
  }

  buildData() {
    if (!this.points.length) return [[], []];

    const xValues = this.points.map((p) => (this.mode === "time" ? p.rel_time_s : p.cum_dist_m));
    const speedValues = this.points.map((p) => p.speed_kmh);

    return [xValues, speedValues];
  }

  render() {
    if (!this.container || !this.points.length) return;

    if (this.uplot) {
      this.uplot.destroy();
      this.uplot = null;
    }

    const stage = this.container.parentElement;
    const width = (stage ? stage.clientWidth : this.container.clientWidth) || 800;
    const height = (stage ? stage.clientHeight : this.container.clientHeight) || 210;

    this.lastW = width;
    this.lastH = height;

    const data = this.buildData();

    // Determine clean rounded upper ceiling for speed axis
    const maxSpeed = Math.max(...this.points.map((p) => p.speed_kmh));
    const topCeil = Math.max(100, Math.ceil((maxSpeed * 1.1) / 50) * 50);

    const maxX = this.mode === "time"
      ? (this.points[this.points.length - 1].rel_time_s || 100)
      : (this.points[this.points.length - 1].cum_dist_m || 1000);

    const opts = {
      width: width,
      height: height,
      padding: [12, 24, 8, 12],
      cursor: {
        drag: { setScale: false },
        sync: { key: "ams_telemetry" },
        points: {
          size: 9,
          width: 2.5,
          stroke: "#ff007f", // Hot Racing Pink hover point
          fill: "#ffffff",
        },
      },
      hooks: {
        setCursor: [
          (u) => {
            const idx = u.cursor.idx;
            if (idx !== null && idx !== undefined && idx >= 0 && idx < this.points.length) {
              if (idx !== this.currentIndex) {
                this.currentIndex = idx;
                if (this.onCursorMove) {
                  this.onCursorMove(idx);
                }
              }
            }
          },
        ],
      },
      scales: {
        x: {
          time: false,
          range: [0, Math.ceil(maxX * 1.02)],
        },
        speed: {
          auto: false,
          range: [0, topCeil], // Explicit 0 to 400 km/h scale
        },
      },
      axes: [
        {
          scale: "x",
          size: 32,
          stroke: "#8b949e",
          font: "11px monospace",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#243048", width: 1 },
          values: (u, vals) =>
            vals.map((v) => (this.mode === "time" ? `${v.toFixed(1)}s` : `${Math.round(v)}m`)),
        },
        {
          scale: "speed",
          size: 68,
          stroke: "#8b949e",
          font: "11px monospace",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#243048", width: 1 },
          values: (u, vals) => vals.map((v) => `${Math.round(v)} km/h`),
        },
      ],
      series: [
        {}, // X axis series
        {
          scale: "speed",
          label: "Velocidad",
          stroke: "#00ff88", // Neon Racing Green
          width: 2.5,
          fill: "rgba(0, 255, 136, 0.12)", // Neon Green subtle gradient fill
          points: { show: false },
        },
      ],
    };

    this.uplot = new uPlot(opts, data, this.container);
  }

  setCursorIndex(idx) {
    if (!this.uplot || !this.points.length || idx < 0 || idx >= this.points.length) return;
    this.currentIndex = idx;
    const xVal = this.mode === "time" ? this.points[idx].rel_time_s : this.points[idx].cum_dist_m;
    const left = this.uplot.valToPos(xVal, "x");
    this.uplot.setCursor({ left, top: 40 }, false);
  }

  handleResize() {
    if (!this.uplot || !this.container) return;
    const stage = this.container.parentElement;
    const w = stage ? stage.clientWidth : this.container.clientWidth;
    const h = stage ? stage.clientHeight : this.container.clientHeight;

    // Guard against feedback loops
    if (w > 0 && h > 0 && (Math.abs(w - this.lastW) > 2 || Math.abs(h - this.lastH) > 2)) {
      this.lastW = w;
      this.lastH = h;
      this.uplot.setSize({ width: w, height: h });
    }
  }
}
