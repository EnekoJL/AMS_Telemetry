/**
 * Multi-Channel Telemetry Synchronized Stacked Charts.
 * MoTeC / AiM / Bosch Motorsport style with 60 FPS linked crosshair,
 * dual Y-axes for multi-unit channels, dynamic scale range bounding,
 * reliable drag-zoom across all channels, and individual fullscreen maximization.
 */

/**
 * Computes clean min and max boundaries with proportional margin
 * and round tick step boundaries, avoiding compressed curves.
 */
function calcScaleRange(dataMin, dataMax, { forceZeroMin = false, minSpan = 10, padFrac = 0.1, roundStep = 5 } = {}) {
  if (dataMin == null || isNaN(dataMin) || dataMax == null || isNaN(dataMax)) {
    return [0, minSpan];
  }
  let min = Number(dataMin);
  let max = Number(dataMax);

  if (forceZeroMin && min >= 0) {
    min = 0;
  }

  if (max - min < minSpan) {
    if (forceZeroMin && min >= 0) {
      max = min + minSpan;
    } else {
      const mid = (max + min) / 2;
      min = mid - minSpan / 2;
      max = mid + minSpan / 2;
    }
  }

  const span = max - min;
  const pad = span * padFrac;
  let rMin = forceZeroMin && min >= 0 ? 0 : min - pad;
  let rMax = max + pad;

  if (roundStep > 0) {
    rMin = Math.floor(rMin / roundStep) * roundStep;
    rMax = Math.ceil(rMax / roundStep) * roundStep;
  }

  if (forceZeroMin && min >= 0) {
    rMin = 0;
  }

  return [rMin, rMax];
}

export class MultiTelemetryCharts {
  constructor(containerId, onPointHover) {
    this.container = document.getElementById(containerId);
    this.onPointHover = onPointHover;
    this.charts = {};
    this.syncGroup = uPlot.sync("multi_telemetry");
    this.sessionData = null;
    this.channels = null;
    this.xMin = 0;
    this.xMax = 100;
    this._zooming = false;
    this.maximizedKey = null;

    // Numerical readout element caches
    this.readouts = {
      speed: document.getElementById("readout-speed"),
      rpm: document.getElementById("readout-rpm"),
      torque: document.getElementById("readout-torque"),
      fork: document.getElementById("readout-fork"),
      shock: document.getElementById("readout-shock"),
      batt12: document.getElementById("readout-batt12"),
      packV: document.getElementById("readout-pack-v"),
      packI: document.getElementById("readout-pack-i"),
      soc: document.getElementById("readout-soc"),
      cellMin: document.getElementById("readout-cell-min"),
      cellMax: document.getElementById("readout-cell-max"),
      tempMot: document.getElementById("readout-temp-mot"),
      tempInv: document.getElementById("readout-temp-inv"),
      tempBms: document.getElementById("readout-temp-bms"),
      tempMcu: document.getElementById("readout-temp-mcu"),
    };

    this.initMaximizeControls();
  }

  initMaximizeControls() {
    document.querySelectorAll(".btn-card-maximize").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const chartKey = btn.getAttribute("data-chart");
        if (chartKey) {
          this.toggleMaximize(chartKey);
        }
      });
    });

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.maximizedKey) {
        this.toggleMaximize(this.maximizedKey);
      }
    });
  }

  toggleMaximize(chartKey) {
    const card = document.getElementById(`card-${chartKey}`);
    if (!card) return;

    if (this.maximizedKey === chartKey) {
      // Restore back to normal stacked layout
      card.classList.remove("is-maximized");
      this.maximizedKey = null;
      this.updateMaximizeButton(card, false);
    } else {
      // If another card is maximized, restore it first
      if (this.maximizedKey) {
        const prevCard = document.getElementById(`card-${this.maximizedKey}`);
        if (prevCard) {
          prevCard.classList.remove("is-maximized");
          this.updateMaximizeButton(prevCard, false);
        }
      }
      card.classList.add("is-maximized");
      this.maximizedKey = chartKey;
      this.updateMaximizeButton(card, true);
    }

    // Immediately re-adjust chart dimensions
    requestAnimationFrame(() => {
      this.resize();
    });
  }

  updateMaximizeButton(card, isMaximized) {
    const btn = card.querySelector(".btn-card-maximize");
    if (!btn) return;
    const label = btn.querySelector(".btn-maximize-text");
    if (label) {
      label.textContent = isMaximized ? "Minimizar" : "Maximizar";
    }
    btn.title = isMaximized ? "Restaurar vista normal (Esc)" : "Maximizar gráfico";
    btn.setAttribute("aria-label", isMaximized ? "Minimizar" : "Maximizar");
    const svg = btn.querySelector("svg");
    if (svg) {
      if (isMaximized) {
        svg.innerHTML = '<path d="M4 14h6v6M20 10h-6V4M14 10l7-7M10 14l-7 7"></path>';
      } else {
        svg.innerHTML = '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"></path>';
      }
    }
  }

  loadData(session) {
    if (!session || !session.channels) return;
    this.sessionData = session;
    this.channels = session.channels;

    // Destroy any existing uPlot instances
    this.destroy();

    // Determine global time range [0, duration_s]
    this.xMin = 0;
    this.xMax = Math.max(1.0, session.summary.duration_s || 100.0);

    // Initialize all 4 stacked charts
    this.createDynamicsChart();
    this.createSuspensionChart();
    this.createBatteryChart();
    this.createThermalsChart();

    // Ensure sizes match container
    this.resize();
  }

  destroy() {
    if (this.maximizedKey) {
      const card = document.getElementById(`card-${this.maximizedKey}`);
      if (card) {
        card.classList.remove("is-maximized");
        this.updateMaximizeButton(card, false);
      }
      this.maximizedKey = null;
    }

    Object.values(this.charts).forEach((u) => {
      if (u && typeof u.destroy === "function") {
        u.destroy();
      }
    });
    this.charts = {};
  }

  getContainerWidth(key = null) {
    if (key && key === this.maximizedKey) {
      const el = document.getElementById(`plot-${key}`);
      if (el && el.clientWidth > 0) return el.clientWidth;
      return Math.max(300, (window.innerWidth || 800) - 48);
    }
    const parent = document.querySelector(".charts-scroll-container");
    if (parent && parent.clientWidth > 0) {
      return Math.max(300, parent.clientWidth - 48);
    }
    return Math.max(300, (window.innerWidth || 800) - 48);
  }

  getContainerHeight(key = null) {
    if (key && key === this.maximizedKey) {
      const card = document.getElementById(`card-${key}`);
      const header = card ? card.querySelector(".telemetry-card-header") : null;
      const headerH = header ? header.offsetHeight : 45;
      return Math.max(250, (window.innerHeight || 600) - headerH - 52);
    }
    return 150;
  }

  zoomAll(min, max) {
    if (this._zooming || min == null || max == null || isNaN(min) || isNaN(max)) return;
    if (min >= max || max - min < 0.5) return;

    this._zooming = true;
    try {
      const clampedMin = Math.max(this.xMin, min);
      const clampedMax = Math.min(this.xMax, max);

      Object.values(this.charts).forEach((u) => {
        if (u && typeof u.setScale === "function") {
          u.setScale("x", { min: clampedMin, max: clampedMax });
        }
      });
    } finally {
      this._zooming = false;
    }
  }

  resetZoom() {
    this._zooming = true;
    try {
      Object.values(this.charts).forEach((u) => {
        if (u && typeof u.setScale === "function") {
          u.setScale("x", { min: this.xMin, max: this.xMax });
        }
      });
    } finally {
      this._zooming = false;
    }
  }

  createDynamicsChart() {
    const el = document.getElementById("plot-dynamics");
    if (!el) return;
    el.innerHTML = "";

    const hasGps = this.channels.has_gps && this.channels.gps.length > 0;
    const hasInv = this.channels.has_inverter && this.channels.inverter.length > 0;

    if (!hasGps && !hasInv) {
      el.innerHTML = '<div class="chart-empty-msg">Canal de dinámica no disponible en esta sesión</div>';
      return;
    }

    let xData = [];
    let speedData = [];
    let rpmData = [];

    if (hasInv) {
      xData = this.channels.inverter.map((p) => p.rel_time_s);
      rpmData = this.channels.inverter.map((p) => p.motor_rpm);
      if (hasGps) {
        speedData = this.interpolateSeries(
          xData,
          this.channels.gps.map((p) => p.rel_time_s),
          this.channels.gps.map((p) => p.speed_kmh)
        );
      } else {
        speedData = rpmData.map((r) => r / 30.0);
      }
    } else {
      xData = this.channels.gps.map((p) => p.rel_time_s);
      speedData = this.channels.gps.map((p) => p.speed_kmh);
      rpmData = speedData.map((s) => Math.round(s * 30.0));
    }

    const opts = {
      width: this.getContainerWidth("dynamics"),
      height: this.getContainerHeight("dynamics"),
      cursor: {
        sync: { key: this.syncGroup.key, setSeries: true },
        drag: { x: true, y: false, setScale: true },
      },
      hooks: {
        setSelect: [
          (u) => {
            if (u.select && u.select.width > 5) {
              const min = u.posToVal(u.select.left, "x");
              const max = u.posToVal(u.select.left + u.select.width, "x");
              this.zoomAll(min, max);
            }
          },
        ],
        setCursor: [
          (u) => {
            if (u.cursor.idx !== null && u.cursor.idx !== undefined) {
              this.handleCursorMove(u.cursor.idx, xData[u.cursor.idx]);
            }
          },
        ],
      },
      scales: {
        x: { time: false, min: this.xMin, max: this.xMax },
        kmh: {
          range: (u, dataMin, dataMax) =>
            calcScaleRange(dataMin, dataMax, { forceZeroMin: true, minSpan: 40, roundStep: 10 }),
        },
        rpm: {
          range: (u, dataMin, dataMax) =>
            calcScaleRange(dataMin, dataMax, { forceZeroMin: true, minSpan: 1000, roundStep: 500 }),
        },
      },
      axes: [
        {
          stroke: "#8b949e",
          font: "10px monospace",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#1c283d" },
          values: (u, vals) => vals.map((v) => `${v.toFixed(0)}s`),
        },
        {
          scale: "kmh",
          side: 3,
          stroke: "#00ff88",
          font: "10px monospace",
          size: 70,
          grid: { stroke: "#1c283d", width: 1 },
          values: (u, vals) => vals.map((v) => (v != null && !isNaN(v) ? `${Math.round(v)} km/h` : "")),
        },
        {
          scale: "rpm",
          side: 1,
          stroke: "#ff007f",
          font: "10px monospace",
          size: 75,
          grid: { show: false },
          values: (u, vals) => vals.map((v) => (v != null && !isNaN(v) ? `${Math.round(v)} RPM` : "")),
        },
      ],
      series: [
        {},
        {
          scale: "kmh",
          label: "Velocidad (km/h)",
          stroke: "#00ff88",
          width: 2,
        },
        {
          scale: "rpm",
          label: "Motor (RPM)",
          stroke: "#ff007f",
          width: 2,
        },
      ],
    };

    const chart = new uPlot(opts, [xData, speedData, rpmData], el);
    this.charts.dynamics = chart;

    el.addEventListener("dblclick", () => this.resetZoom());
  }

  createSuspensionChart() {
    const el = document.getElementById("plot-suspension");
    if (!el) return;
    el.innerHTML = "";

    if (!this.channels.has_adc || this.channels.adc.length === 0) {
      el.innerHTML = '<div class="chart-empty-msg">Canal ADC de suspensiones no disponible en esta sesión</div>';
      return;
    }

    const xData = this.channels.adc.map((p) => p.rel_time_s);
    const forkData = this.channels.adc.map((p) => p.susp_front_mm);
    const shockData = this.channels.adc.map((p) => p.susp_rear_mm);

    const opts = {
      width: this.getContainerWidth("suspension"),
      height: this.getContainerHeight("suspension"),
      cursor: {
        sync: { key: this.syncGroup.key, setSeries: true },
        drag: { x: true, y: false, setScale: true },
      },
      hooks: {
        setSelect: [
          (u) => {
            if (u.select && u.select.width > 5) {
              const min = u.posToVal(u.select.left, "x");
              const max = u.posToVal(u.select.left + u.select.width, "x");
              this.zoomAll(min, max);
            }
          },
        ],
        setCursor: [
          (u) => {
            if (u.cursor.idx !== null && u.cursor.idx !== undefined) {
              this.handleCursorMove(u.cursor.idx, xData[u.cursor.idx]);
            }
          },
        ],
      },
      scales: {
        x: { time: false, min: this.xMin, max: this.xMax },
        mm: {
          range: (u, dataMin, dataMax) =>
            calcScaleRange(dataMin, dataMax, { forceZeroMin: true, minSpan: 30, roundStep: 10 }),
        },
      },
      axes: [
        {
          stroke: "#8b949e",
          font: "10px monospace",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#1c283d" },
          values: (u, vals) => vals.map((v) => `${v.toFixed(0)}s`),
        },
        {
          scale: "mm",
          side: 3,
          stroke: "#00ff88",
          font: "10px monospace",
          size: 65,
          grid: { stroke: "#1c283d", width: 1 },
          values: (u, vals) => vals.map((v) => (v != null && !isNaN(v) ? `${Math.round(v)} mm` : "")),
        },
      ],
      series: [
        {},
        {
          scale: "mm",
          label: "Horquilla Delantera (mm)",
          stroke: "#00ff88",
          width: 2,
        },
        {
          scale: "mm",
          label: "Amortiguador Trasero (mm)",
          stroke: "#ff8800",
          width: 2,
        },
      ],
    };

    const chart = new uPlot(opts, [xData, forkData, shockData], el);
    this.charts.suspension = chart;

    el.addEventListener("dblclick", () => this.resetZoom());
  }

  createBatteryChart() {
    const el = document.getElementById("plot-battery");
    if (!el) return;
    el.innerHTML = "";

    if (!this.channels.has_bms || this.channels.bms.length === 0) {
      el.innerHTML = '<div class="chart-empty-msg">Canal de batería BMS no disponible en esta sesión</div>';
      return;
    }

    const xData = this.channels.bms.map((p) => p.rel_time_s);
    const packVData = this.channels.bms.map((p) => p.pack_voltage_v);
    const packIData = this.channels.bms.map((p) => p.pack_current_a);

    const opts = {
      width: this.getContainerWidth("battery"),
      height: this.getContainerHeight("battery"),
      cursor: {
        sync: { key: this.syncGroup.key, setSeries: true },
        drag: { x: true, y: false, setScale: true },
      },
      hooks: {
        setSelect: [
          (u) => {
            if (u.select && u.select.width > 5) {
              const min = u.posToVal(u.select.left, "x");
              const max = u.posToVal(u.select.left + u.select.width, "x");
              this.zoomAll(min, max);
            }
          },
        ],
        setCursor: [
          (u) => {
            if (u.cursor.idx !== null && u.cursor.idx !== undefined) {
              this.handleCursorMove(u.cursor.idx, xData[u.cursor.idx]);
            }
          },
        ],
      },
      scales: {
        x: { time: false, min: this.xMin, max: this.xMax },
        volt: {
          range: (u, dataMin, dataMax) =>
            calcScaleRange(dataMin, dataMax, { forceZeroMin: false, minSpan: 20, roundStep: 10 }),
        },
        amp: {
          range: (u, dataMin, dataMax) =>
            calcScaleRange(dataMin, dataMax, { forceZeroMin: false, minSpan: 30, roundStep: 10 }),
        },
      },
      axes: [
        {
          stroke: "#8b949e",
          font: "10px monospace",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#1c283d" },
          values: (u, vals) => vals.map((v) => `${v.toFixed(0)}s`),
        },
        {
          scale: "volt",
          side: 3,
          stroke: "#00ff88",
          font: "10px monospace",
          size: 65,
          grid: { stroke: "#1c283d", width: 1 },
          values: (u, vals) => vals.map((v) => (v != null && !isNaN(v) ? `${Math.round(v)} V` : "")),
        },
        {
          scale: "amp",
          side: 1,
          stroke: "#ff007f",
          font: "10px monospace",
          size: 65,
          grid: { show: false },
          values: (u, vals) => vals.map((v) => (v != null && !isNaN(v) ? `${Math.round(v)} A` : "")),
        },
      ],
      series: [
        {},
        {
          scale: "volt",
          label: "Tensión Pack (V)",
          stroke: "#00ff88",
          width: 2,
        },
        {
          scale: "amp",
          label: "Corriente Pack (A)",
          stroke: "#ff007f",
          width: 2,
        },
      ],
    };

    const chart = new uPlot(opts, [xData, packVData, packIData], el);
    this.charts.battery = chart;

    el.addEventListener("dblclick", () => this.resetZoom());
  }

  createThermalsChart() {
    const el = document.getElementById("plot-thermals");
    if (!el) return;
    el.innerHTML = "";

    const hasInv = this.channels.has_inverter && this.channels.inverter.length > 0;
    const hasBms = this.channels.has_bms && this.channels.bms.length > 0;
    const hasAdc = this.channels.has_adc && this.channels.adc.length > 0;

    if (!hasInv && !hasBms && !hasAdc) {
      el.innerHTML = '<div class="chart-empty-msg">Canales térmicos no disponibles en esta sesión</div>';
      return;
    }

    let xData = [];
    if (hasInv) {
      xData = this.channels.inverter.map((p) => p.rel_time_s);
    } else if (hasAdc) {
      xData = this.channels.adc.map((p) => p.rel_time_s);
    } else {
      xData = this.channels.bms.map((p) => p.rel_time_s);
    }

    const motTemp = hasInv ? this.channels.inverter.map((p) => p.motor_temp_c) : xData.map(() => 45.0);
    const invTemp = hasInv ? this.channels.inverter.map((p) => p.inverter_temp_c) : xData.map(() => 40.0);
    const bmsTemp = hasBms
      ? this.interpolateSeries(
          xData,
          this.channels.bms.map((p) => p.rel_time_s),
          this.channels.bms.map((p) => p.cell_temp_max_c)
        )
      : xData.map(() => 35.0);
    const mcuTemp = hasAdc
      ? this.interpolateSeries(
          xData,
          this.channels.adc.map((p) => p.rel_time_s),
          this.channels.adc.map((p) => p.mcu_temp_c)
        )
      : xData.map(() => 42.0);

    const opts = {
      width: this.getContainerWidth("thermals"),
      height: this.getContainerHeight("thermals"),
      cursor: {
        sync: { key: this.syncGroup.key, setSeries: true },
        drag: { x: true, y: false, setScale: true },
      },
      hooks: {
        setSelect: [
          (u) => {
            if (u.select && u.select.width > 5) {
              const min = u.posToVal(u.select.left, "x");
              const max = u.posToVal(u.select.left + u.select.width, "x");
              this.zoomAll(min, max);
            }
          },
        ],
        setCursor: [
          (u) => {
            if (u.cursor.idx !== null && u.cursor.idx !== undefined) {
              this.handleCursorMove(u.cursor.idx, xData[u.cursor.idx]);
            }
          },
        ],
      },
      scales: {
        x: { time: false, min: this.xMin, max: this.xMax },
        celsius: {
          range: (u, dataMin, dataMax) =>
            calcScaleRange(dataMin, dataMax, { forceZeroMin: false, minSpan: 20, roundStep: 5 }),
        },
      },
      axes: [
        {
          stroke: "#8b949e",
          font: "10px monospace",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#1c283d" },
          values: (u, vals) => vals.map((v) => `${v.toFixed(0)}s`),
        },
        {
          scale: "celsius",
          side: 3,
          stroke: "#ff007f",
          font: "10px monospace",
          size: 65,
          grid: { stroke: "#1c283d", width: 1 },
          values: (u, vals) => vals.map((v) => (v != null && !isNaN(v) ? `${Math.round(v)} °C` : "")),
        },
      ],
      series: [
        {},
        {
          scale: "celsius",
          label: "Motor (°C)",
          stroke: "#ff007f",
          width: 2,
        },
        {
          scale: "celsius",
          label: "Inversor (°C)",
          stroke: "#ff8800",
          width: 2,
        },
        {
          scale: "celsius",
          label: "Batería Máx (°C)",
          stroke: "#ffd600",
          width: 2,
        },
        {
          scale: "celsius",
          label: "STM32 MCU (°C)",
          stroke: "#00ff88",
          width: 2,
        },
      ],
    };

    const chart = new uPlot(opts, [xData, motTemp, invTemp, bmsTemp, mcuTemp], el);
    this.charts.thermals = chart;

    el.addEventListener("dblclick", () => this.resetZoom());
  }

  interpolateSeries(targetX, sourceX, sourceY) {
    if (!sourceX.length) return targetX.map(() => 0.0);
    let sIdx = 0;
    return targetX.map((tx) => {
      while (sIdx < sourceX.length - 1 && sourceX[sIdx + 1] <= tx) {
        sIdx++;
      }
      if (sIdx >= sourceX.length - 1) return sourceY[sourceY.length - 1];
      const x0 = sourceX[sIdx];
      const x1 = sourceX[sIdx + 1];
      const frac = x1 > x0 ? (tx - x0) / (x1 - x0) : 0.0;
      return sourceY[sIdx] + frac * (sourceY[sIdx + 1] - sourceY[sIdx]);
    });
  }

  handleCursorMove(idx, relTimeS) {
    if (relTimeS === undefined || relTimeS === null) return;

    // Binary search helper
    const findClosest = (arr) => {
      if (!arr || !arr.length) return null;
      let low = 0,
        high = arr.length - 1;
      while (low <= high) {
        const mid = (low + high) >> 1;
        if (arr[mid].rel_time_s < relTimeS) low = mid + 1;
        else high = mid - 1;
      }
      const i0 = Math.max(0, Math.min(arr.length - 1, low));
      const i1 = Math.max(0, Math.min(arr.length - 1, low - 1));
      return Math.abs(arr[i0].rel_time_s - relTimeS) < Math.abs(arr[i1].rel_time_s - relTimeS) ? arr[i0] : arr[i1];
    };

    // Update Dynamics
    const ptGps = findClosest(this.channels.gps);
    const ptInv = findClosest(this.channels.inverter);
    if (this.readouts.speed) this.readouts.speed.textContent = ptGps ? `${ptGps.speed_kmh.toFixed(1)} km/h` : "—";
    if (this.readouts.rpm) this.readouts.rpm.textContent = ptInv ? `${ptInv.motor_rpm} RPM` : "—";
    if (this.readouts.torque) this.readouts.torque.textContent = ptInv ? `${ptInv.torque_nm.toFixed(1)} Nm` : "—";

    // Update Suspension
    const ptAdc = findClosest(this.channels.adc);
    if (this.readouts.fork) this.readouts.fork.textContent = ptAdc ? `${ptAdc.susp_front_mm.toFixed(1)} mm` : "—";
    if (this.readouts.shock) this.readouts.shock.textContent = ptAdc ? `${ptAdc.susp_rear_mm.toFixed(1)} mm` : "—";
    if (this.readouts.batt12) this.readouts.batt12.textContent = ptAdc ? `${ptAdc.batt_12v_v.toFixed(2)} V` : "—";

    // Update Battery
    const ptBms = findClosest(this.channels.bms);
    if (this.readouts.packV) this.readouts.packV.textContent = ptBms ? `${ptBms.pack_voltage_v.toFixed(1)} V` : "—";
    if (this.readouts.packI) {
      if (ptBms) {
        const sign = ptBms.pack_current_a > 0 ? "+" : "";
        this.readouts.packI.textContent = `${sign}${ptBms.pack_current_a.toFixed(1)} A`;
        this.readouts.packI.style.color = ptBms.pack_current_a > 0 ? "var(--accent-pink)" : "var(--accent-green)";
      } else {
        this.readouts.packI.textContent = "—";
      }
    }
    if (this.readouts.soc) this.readouts.soc.textContent = ptBms ? `${ptBms.soc_percent.toFixed(1)}%` : "—";
    if (this.readouts.cellMin) this.readouts.cellMin.textContent = ptBms ? `${ptBms.cell_min_v.toFixed(3)} V` : "—";
    if (this.readouts.cellMax) this.readouts.cellMax.textContent = ptBms ? `${ptBms.cell_max_v.toFixed(3)} V` : "—";

    // Update Thermals
    if (this.readouts.tempMot) this.readouts.tempMot.textContent = ptInv ? `${ptInv.motor_temp_c.toFixed(1)} °C` : "—";
    if (this.readouts.tempInv) this.readouts.tempInv.textContent = ptInv ? `${ptInv.inverter_temp_c.toFixed(1)} °C` : "—";
    if (this.readouts.tempBms) this.readouts.tempBms.textContent = ptBms ? `${ptBms.cell_temp_max_c.toFixed(1)} °C` : "—";
    if (this.readouts.tempMcu) this.readouts.tempMcu.textContent = ptAdc ? `${ptAdc.mcu_temp_c.toFixed(1)} °C` : "—";

    // Forward to Map & HUD
    if (this.onPointHover && ptGps) {
      this.onPointHover(ptGps);
    }
  }

  setCursorTime(relTimeS) {
    const target = (this.maximizedKey && this.charts[this.maximizedKey]) || this.charts.dynamics;
    if (!target) return;
    const left = target.valToPos(relTimeS, "x");
    target.setCursor({ left, top: 40 }, false);
  }

  resize() {
    Object.entries(this.charts).forEach(([key, u]) => {
      if (u && typeof u.setSize === "function") {
        const width = this.getContainerWidth(key);
        const height = this.getContainerHeight(key);
        u.setSize({ width, height });
      }
    });
  }
}
