/**
 * High-performance Speed Telemetry Chart using uPlot.
 * Drag/Wheel Zoom support, fixed 0 to 400 km/h scale, and direct instant speed tracking.
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

  findClosestIndex(xVal) {
    if (!this.points.length) return 0;
    const isTime = this.mode === "time";
    let low = 0;
    let high = this.points.length - 1;

    while (low <= high) {
      const mid = (low + high) >> 1;
      const val = isTime ? this.points[mid].rel_time_s : this.points[mid].cum_dist_m;
      if (val < xVal) low = mid + 1;
      else if (val > xVal) high = mid - 1;
      else return mid;
    }

    if (low >= this.points.length) return this.points.length - 1;
    if (high < 0) return 0;
    const vLow = isTime ? this.points[low].rel_time_s : this.points[low].cum_dist_m;
    const vHigh = isTime ? this.points[high].rel_time_s : this.points[high].cum_dist_m;
    return Math.abs(vLow - xVal) < Math.abs(vHigh - xVal) ? low : high;
  }

  resetZoom() {
    if (!this.uplot || !this.points.length) return;
    const maxX = this.mode === "time"
      ? (this.points[this.points.length - 1].rel_time_s || 100)
      : (this.points[this.points.length - 1].cum_dist_m || 1000);
    this.uplot.setScale("x", { min: 0, max: Math.ceil(maxX * 1.02) });
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
        drag: {
          x: true,        // Enable horizontal box drag-zoom
          y: false,
          setScale: true, // Automatically update x-axis scale on drag release
        },
        sync: { key: "ams_telemetry" },
        points: {
          size: 9,
          width: 2.5,
          stroke: "#ff007f", // Hot Racing Pink hover point
          fill: "#ffffff",
        },
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
          values: (u, vals) =>
            vals.map((v) => (v != null && !isNaN(v) ? `${Math.round(v)} km/h` : "")),
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

    // Attach direct mousemove listener to overlay for 100% reliable instant speed updates
    if (this.uplot.over) {
      this.uplot.over.addEventListener("mousemove", (e) => {
        if (!this.uplot || !this.points.length) return;
        const bbox = this.uplot.over.getBoundingClientRect();
        const left = e.clientX - bbox.left;
        if (left >= 0 && left <= bbox.width) {
          const xVal = this.uplot.posToVal(left, "x");
          const idx = this.findClosestIndex(xVal);
          if (idx >= 0 && idx < this.points.length && idx !== this.currentIndex) {
            this.currentIndex = idx;
            if (this.onCursorMove) {
              this.onCursorMove(idx);
            }
          }
        }
      });

      // Double-click on chart canvas resets zoom
      this.uplot.over.addEventListener("dblclick", () => {
        this.resetZoom();
      });

      // Mouse wheel zoom plugin
      this.uplot.over.addEventListener("wheel", (e) => {
        e.preventDefault();
        const bbox = this.uplot.over.getBoundingClientRect();
        const left = e.clientX - bbox.left;
        const xVal = this.uplot.posToVal(left, "x");
        const xMin = this.uplot.scales.x.min;
        const xMax = this.uplot.scales.x.max;
        const xRange = xMax - xMin;

        const factor = e.deltaY < 0 ? 0.8 : 1.25;
        const newRange = xRange * factor;

        // Keep centered around mouse cursor
        const ratio = (xVal - xMin) / (xRange || 1);
        let newMin = Math.max(0, xVal - newRange * ratio);
        let newMax = newMin + newRange;

        if (newRange > 2) {
          this.uplot.setScale("x", { min: newMin, max: newMax });
        }
      }, { passive: false });
    }
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
