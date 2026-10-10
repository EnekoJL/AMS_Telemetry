/**
 * AMS Telemetry Studio — Master Application Coordinator.
 * RAF-synchronized 60 FPS hover, multi-session management, tab navigation,
 * and multi-channel telemetry streams (GPS, ADC, BMS, Inverter).
 */

import { fetchCurrentSession, uploadSessionFile, uploadMultiTelemetryFiles, loadSampleSession } from "./api.js";
import { TrackMap } from "./map.js";
import { TelemetryChart } from "./chart.js";
import { TelemetryHUD } from "./hud.js";
import { MultiTelemetryCharts } from "./multi_chart.js";

class TelemetryStudioApp {
  constructor() {
    this.sessionData = null;
    this.points = [];
    this.currentView = "track";
    this.rafPending = false;
    this.pendingPointIdx = 0;
    this.pendingFromMap = false;

    this.hud = new TelemetryHUD();

    // Bi-directional event wiring for Track view
    this.trackMap = new TrackMap("track-map", (idx) => {
      this.handlePointSelected(idx, true);
    });

    this.chart = new TelemetryChart("telemetry-plot", (idx) => {
      this.handlePointSelected(idx, false);
    });

    // Multi-channel stacked graphs manager
    this.multiCharts = new MultiTelemetryCharts("view-graphs");

    this.initEventListeners();
    this.initSession();
  }

  handlePointSelected(idx, fromMap = false) {
    if (!this.points.length || idx < 0 || idx >= this.points.length) return;
    this.pendingPointIdx = idx;
    this.pendingFromMap = fromMap;

    // Throttle to display refresh rate (60 FPS) to guarantee silk-smooth performance
    if (!this.rafPending) {
      this.rafPending = true;
      requestAnimationFrame(() => {
        this.rafPending = false;
        const currentIdx = this.pendingPointIdx;
        const pt = this.points[currentIdx];
        if (pt) {
          this.hud.updateInstant(pt);
          this.trackMap.setCursorPosition(pt);
          if (this.pendingFromMap) {
            this.chart.setCursorIndex(currentIdx);
          }
        }
      });
    }
  }

  async initSession() {
    try {
      const session = await fetchCurrentSession();
      this.loadSession(session);
    } catch (err) {
      console.warn("No active session loaded on startup:", err.message);
    }
  }

  loadSession(session) {
    if (!session) return;
    this.sessionData = session;
    this.points = session.points || [];

    // 1. Update summary HUD
    this.hud.updateSessionSummary(session.summary);

    // 2. Load track on map & speed chart if GPS data is present
    if (this.points.length > 0) {
      const minSpeed = Math.min(...this.points.map((p) => p.speed_kmh));
      const maxSpeed = session.summary.max_speed_kmh;
      this.trackMap.loadTrackData(this.points, minSpeed, maxSpeed);
      this.chart.loadData(this.points);
      this.hud.updateInstant(this.points[0]);
    }

    // 3. Update active channel status pills
    this.updateChannelPills(session.channels);

    // 4. Load multi-channel charts
    this.multiCharts.loadData(session);
  }

  updateChannelPills(channels) {
    if (!channels) return;
    const pillGps = document.getElementById("pill-ch-gps");
    const pillAdc = document.getElementById("pill-ch-adc");
    const pillBms = document.getElementById("pill-ch-bms");
    const pillInv = document.getElementById("pill-ch-inv");

    if (pillGps) pillGps.classList.toggle("active", Boolean(channels.has_gps));
    if (pillAdc) pillAdc.classList.toggle("active", Boolean(channels.has_adc));
    if (pillBms) pillBms.classList.toggle("active", Boolean(channels.has_bms));
    if (pillInv) pillInv.classList.toggle("active", Boolean(channels.has_inverter));
  }

  switchView(viewName) {
    this.currentView = viewName;
    const btnTrack = document.getElementById("tab-btn-track");
    const btnGraphs = document.getElementById("tab-btn-graphs");
    const viewTrack = document.getElementById("view-track");
    const viewGraphs = document.getElementById("view-graphs");

    if (viewName === "track") {
      if (btnTrack) btnTrack.classList.add("active");
      if (btnGraphs) btnGraphs.classList.remove("active");
      if (viewTrack) {
        viewTrack.style.display = "flex";
        viewTrack.classList.add("active");
      }
      if (viewGraphs) {
        viewGraphs.style.display = "none";
        viewGraphs.classList.remove("active");
      }
      setTimeout(() => {
        if (this.trackMap && this.trackMap.map) {
          this.trackMap.map.invalidateSize();
        }
      }, 50);
    } else {
      if (btnGraphs) btnGraphs.classList.add("active");
      if (btnTrack) btnTrack.classList.remove("active");
      if (viewGraphs) {
        viewGraphs.style.display = "flex";
        viewGraphs.classList.add("active");
      }
      if (viewTrack) {
        viewTrack.style.display = "none";
        viewTrack.classList.remove("active");
      }
      setTimeout(() => {
        this.multiCharts.resize();
      }, 50);
    }
  }

  initEventListeners() {
    // Navigation Tabs
    const btnTabTrack = document.getElementById("tab-btn-track");
    const btnTabGraphs = document.getElementById("tab-btn-graphs");

    if (btnTabTrack) {
      btnTabTrack.addEventListener("click", () => this.switchView("track"));
    }
    if (btnTabGraphs) {
      btnTabGraphs.addEventListener("click", () => this.switchView("graphs"));
    }

    // Mode toggles (Time vs Distance) in Track View
    const btnTime = document.getElementById("toggle-time");
    const btnDist = document.getElementById("toggle-dist");

    if (btnTime && btnDist) {
      btnTime.addEventListener("click", () => {
        btnTime.classList.add("active");
        btnDist.classList.remove("active");
        this.chart.setMode("time");
      });

      btnDist.addEventListener("click", () => {
        btnDist.classList.add("active");
        btnTime.classList.remove("active");
        this.chart.setMode("distance");
      });
    }

    // Reset zoom button in Track View
    const btnResetZoom = document.getElementById("btn-reset-zoom");
    if (btnResetZoom) {
      btnResetZoom.addEventListener("click", () => {
        this.chart.resetZoom();
      });
    }

    // Reset zoom button in Multi-Graphs View
    const btnResetMultiZoom = document.getElementById("btn-reset-multi-zoom");
    if (btnResetMultiZoom) {
      btnResetMultiZoom.addEventListener("click", () => {
        this.multiCharts.resetZoom();
      });
    }

    // Load sample session button
    const btnSample = document.getElementById("btn-load-sample");
    if (btnSample) {
      btnSample.addEventListener("click", async () => {
        try {
          btnSample.disabled = true;
          const session = await loadSampleSession();
          this.loadSession(session);
        } catch (err) {
          alert(`Error al cargar muestra: ${err.message}`);
        } finally {
          btnSample.disabled = false;
        }
      });
    }

    // File input upload (Supports multiple .bin and .csv files)
    const fileInput = document.getElementById("file-input");
    const btnUpload = document.getElementById("btn-upload");

    if (btnUpload && fileInput) {
      btnUpload.addEventListener("click", () => fileInput.click());

      fileInput.addEventListener("change", async (e) => {
        const files = Array.from(e.target.files);
        if (!files.length) return;
        await this.handleFilesUpload(files);
        fileInput.value = "";
      });
    }

    // Drag and Drop support
    const dropOverlay = document.getElementById("drop-overlay");
    window.addEventListener("dragenter", (e) => {
      e.preventDefault();
      if (dropOverlay) dropOverlay.classList.add("active");
    });

    window.addEventListener("dragover", (e) => {
      e.preventDefault();
    });

    window.addEventListener("dragleave", (e) => {
      if (e.relatedTarget === null && dropOverlay) {
        dropOverlay.classList.remove("active");
      }
    });

    window.addEventListener("drop", async (e) => {
      e.preventDefault();
      if (dropOverlay) dropOverlay.classList.remove("active");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const files = Array.from(e.dataTransfer.files);
        await this.handleFilesUpload(files);
      }
    });

    // Window resize handler
    window.addEventListener("resize", () => {
      if (this.currentView === "graphs") {
        this.multiCharts.resize();
      }
    });
  }

  async handleFilesUpload(files) {
    const validFiles = files.filter((f) => {
      const lower = f.name.toLowerCase();
      return lower.endsWith(".bin") || lower.endsWith(".csv");
    });

    if (!validFiles.length) {
      alert("Por favor selecciona archivos válidos de telemetría (.bin o .csv)");
      return;
    }

    try {
      let session;
      if (validFiles.length === 1 && validFiles[0].name.toLowerCase().endsWith(".bin")) {
        session = await uploadSessionFile(validFiles[0]);
      } else {
        session = await uploadMultiTelemetryFiles(validFiles);
      }
      this.loadSession(session);
    } catch (err) {
      alert(`Error al procesar archivos de telemetría: ${err.message}`);
    }
  }
}

// Bootstrap on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  window.app = new TelemetryStudioApp();
});
