/**
 * Multi-Channel Telemetry Synchronized Stacked Charts.
 * MoTeC / AiM / Bosch Motorsport style with 60 FPS linked crosshair,
 * reliable drag-zoom across all channels, and map/HUD synchronization.
 */

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
    Object.values(this.charts).forEach((u) => {
      if (u && typeof u.destroy === "function") {
        u.destroy();
      }
    });
    this.charts = {};
  }

  getContainerWidth() {
    const parent = document.querySelector(".charts-scroll-container");
    if (parent && parent.clientWidth > 0) {
      return Math.max(300, parent.clientWidth - 48);
    }
    return Math.max(300, (window.innerWidth || 800) - 48);
  }

  zoomAll(min, max) {
    if (this._zooming || min == null || max == null || isNaN(min) || isNaN(max)) return;
    if (min >= max || (max - min) < 0.5) return;

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
        speedData = this.interpolateSeries(xData, this.channels.gps.map((p) => p.rel_time_s), this.channels.gps.map((p) => p.speed_kmh));
      } else {
        speedData = rpmData.map((r) => r / 30.0);
      }
    } else {
      xData = this.channels.gps.map((p) => p.rel_time_s);
      speedData = this.channels.gps.map((p) => p.speed_kmh);
      rpmData = speedData.map((s) => Math.round(s * 30.0));
    }

    const opts = {
      width: this.getContainerWidth(),
      height: 150,
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
        kmh: { auto: true },
        rpm: { auto: true },
      },
      axes: [
        {
          stroke: "#8b949e",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#1c283d" },
          values: (u, vals) => vals.map((v) => `${v.toFixed(0)}s`),
        },
        {
          scale: "kmh",
          stroke: "#00ff88",
          size: 55,
          grid: { stroke: "#1c283d", width: 1 },
          values: (u, vals) => `${Math.round(vals)} km/h`,
        },
        {
          scale: "rpm",
          side: 1,
          stroke: "#ff007f",
          size: 55,
          grid: { show: false },
          values: (u, vals) => `${Math.round(vals)}`,
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
      width: this.getContainerWidth(),
      height: 150,
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
        mm: { auto: true },
      },
      axes: [
        {
          stroke: "#8b949e",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#1c283d" },
          values: (u, vals) => vals.map((v) => `${v.toFixed(0)}s`),
        },
        {
          scale: "mm",
          stroke: "#00ff88",
          size: 55,
          grid: { stroke: "#1c283d", width: 1 },
          values: (u, vals) => `${Math.round(vals)} mm`,
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
      width: this.getContainerWidth(),
      height: 150,
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
        volt: { auto: true },
        amp: { auto: true },
      },
      axes: [
        {
          stroke: "#8b949e",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#1c283d" },
          values: (u, vals) => vals.map((v) => `${v.toFixed(0)}s`),
        },
        {
          scale: "volt",
          stroke: "#00ff88",
          size: 55,
          grid: { stroke: "#1c283d", width: 1 },
          values: (u, vals) => `${Math.round(vals)} V`,
        },
        {
          scale: "amp",
          side: 1,
          stroke: "#ff007f",
          size: 55,
          grid: { show: false },
          values: (u, vals) => `${Math.round(vals)} A`,
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
      ? this.interpolateSeries(xData, this.channels.bms.map((p) => p.rel_time_s), this.channels.bms.map((p) => p.cell_temp_max_c))
      : xData.map(() => 35.0);
    const mcuTemp = hasAdc
      ? this.interpolateSeries(xData, this.channels.adc.map((p) => p.rel_time_s), this.channels.adc.map((p) => p.mcu_temp_c))
      : xData.map(() => 42.0);

    const opts = {
      width: this.getContainerWidth(),
      height: 150,
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
        celsius: { auto: true },
      },
      axes: [
        {
          stroke: "#8b949e",
          grid: { stroke: "#1c283d", width: 1 },
          ticks: { stroke: "#1c283d" },
          values: (u, vals) => vals.map((v) => `${v.toFixed(0)}s`),
        },
        {
          scale: "celsius",
          stroke: "#ff007f",
          size: 55,
          grid: { stroke: "#1c283d", width: 1 },
          values: (u, vals) => `${Math.round(vals)} °C`,
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
      let low = 0, high = arr.length - 1;
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
    if (!this.charts.dynamics) return;
    const u = this.charts.dynamics;
    const left = u.valToPos(relTimeS, "x");
    u.setCursor({ left, top: 40 }, false);
  }

  resize() {
    const width = this.getContainerWidth();
    Object.values(this.charts).forEach((u) => {
      if (u && typeof u.setSize === "function") {
        u.setSize({ width, height: 150 });
      }
    });
  }
}
