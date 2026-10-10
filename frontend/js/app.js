/**
 * AMS Telemetry Studio — Master Application Coordinator.
 * Unified Single-View Cockpit Dashboard with Collapsible Map & HUD,
 * 60 FPS linked crosshair, multi-channel streams, and synchronized zoom.
 */

import { fetchCurrentSession, uploadSessionFile, uploadMultiTelemetryFiles, loadSampleSession } from "./api.js";
import { TrackMap } from "./map.js";
import { TelemetryHUD } from "./hud.js";
import { MultiTelemetryCharts } from "./multi_chart.js";

class TelemetryStudioApp {
  constructor() {
    this.sessionData = null;
    this.points = [];
    this.mapVisible = true;
    this.rafPending = false;
    this.pendingPoint = null;

    this.hud = new TelemetryHUD();

    // Map coordinator with point selection callback
    this.trackMap = new TrackMap("track-map", (idx) => {
      this.handleMapPointSelected(idx);
    });

    // Multi-channel stacked charts manager with real-time hover callback
    this.multiCharts = new MultiTelemetryCharts("telemetry-charts-section", (ptGps) => {
      this.handleChartPointHover(ptGps);
    });

    this.initEventListeners();
    this.initSession();
  }

  handleChartPointHover(ptGps) {
    if (!ptGps) return;
    this.pendingPoint = ptGps;

    if (!this.rafPending) {
      this.rafPending = true;
      requestAnimationFrame(() => {
        this.rafPending = false;
        if (this.pendingPoint) {
          this.hud.updateInstant(this.pendingPoint);
          if (this.mapVisible) {
            this.trackMap.setCursorPosition(this.pendingPoint);
          }
        }
      });
    }
  }

  handleMapPointSelected(idx) {
    if (!this.points.length || idx < 0 || idx >= this.points.length) return;
    const pt = this.points[idx];
    if (!pt) return;

    this.hud.updateInstant(pt);
    this.trackMap.setCursorPosition(pt);
    this.multiCharts.setCursorTime(pt.rel_time_s);
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

    // 2. Load track on map if GPS data is present
    if (this.points.length > 0) {
      const minSpeed = Math.min(...this.points.map((p) => p.speed_kmh));
      const maxSpeed = session.summary.max_speed_kmh;
      this.trackMap.loadTrackData(this.points, minSpeed, maxSpeed);
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

  toggleMapVisibility() {
    this.mapVisible = !this.mapVisible;
    const mapCollapsible = document.getElementById("map-hud-collapsible");
    const btnToggle = document.getElementById("btn-toggle-map");
    const btnText = document.getElementById("btn-toggle-map-text");

    if (mapCollapsible) {
      mapCollapsible.classList.toggle("collapsed", !this.mapVisible);
    }

    if (btnText) {
      btnText.textContent = this.mapVisible ? "Ocultar Mapa" : "Mostrar Mapa";
    }

    if (btnToggle) {
      btnToggle.classList.toggle("active", !this.mapVisible);
    }

    setTimeout(() => {
      if (this.mapVisible && this.trackMap && this.trackMap.map) {
        this.trackMap.map.invalidateSize();
      }
      this.multiCharts.resize();
    }, 80);
  }

  initEventListeners() {
    // Toggle Map Button
    const btnToggleMap = document.getElementById("btn-toggle-map");
    if (btnToggleMap) {
      btnToggleMap.addEventListener("click", () => this.toggleMapVisibility());
    }

    // Reset Zoom Button
    const btnResetZoom = document.getElementById("btn-reset-zoom");
    if (btnResetZoom) {
      btnResetZoom.addEventListener("click", () => {
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

    // File input upload
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
      this.multiCharts.resize();
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
