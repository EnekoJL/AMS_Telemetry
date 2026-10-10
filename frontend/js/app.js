/**
 * AMS Telemetry Studio — Master Application Coordinator.
 * RAF-synchronized 60 FPS hover, multi-session management, robust error handling.
 */

import { fetchCurrentSession, uploadSessionFile, loadSampleSession } from "./api.js";
import { TrackMap } from "./map.js";
import { TelemetryChart } from "./chart.js";
import { TelemetryHUD } from "./hud.js";

class TelemetryStudioApp {
  constructor() {
    this.sessionData = null;
    this.points = [];
    this.rafPending = false;
    this.pendingPointIdx = 0;
    this.pendingFromMap = false;

    this.hud = new TelemetryHUD();

    // Bi-directional event wiring
    this.trackMap = new TrackMap("track-map", (idx) => {
      this.handlePointSelected(idx, true);
    });

    this.chart = new TelemetryChart("telemetry-plot", (idx) => {
      this.handlePointSelected(idx, false);
    });

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
    if (!session || !session.points || session.points.length === 0) return;
    this.sessionData = session;
    this.points = session.points;

    // 1. Update summary HUD
    this.hud.updateSessionSummary(session.summary);

    // 2. Load track on map
    const minSpeed = Math.min(...this.points.map((p) => p.speed_kmh));
    const maxSpeed = session.summary.max_speed_kmh;
    this.trackMap.loadTrackData(this.points, minSpeed, maxSpeed);

    // 3. Load chart
    this.chart.loadData(this.points);

    // 4. Update initial HUD reading
    this.hud.updateInstant(this.points[0]);
  }

  initEventListeners() {
    // Mode toggles (Time vs Distance)
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

    // Reset zoom button
    const btnResetZoom = document.getElementById("btn-reset-zoom");
    if (btnResetZoom) {
      btnResetZoom.addEventListener("click", () => {
        this.chart.resetZoom();
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
        const file = e.target.files[0];
        if (!file) return;
        await this.handleFileUpload(file);
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
        const file = e.dataTransfer.files[0];
        await this.handleFileUpload(file);
      }
    });
  }

  async handleFileUpload(file) {
    if (!file.name.toLowerCase().endsWith(".bin")) {
      alert("Por favor selecciona un archivo de registro binario (.bin)");
      return;
    }

    try {
      const session = await uploadSessionFile(file);
      this.loadSession(session);
    } catch (err) {
      alert(`Error al procesar el archivo binario: ${err.message}`);
    }
  }
}

// Bootstrap on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  window.app = new TelemetryStudioApp();
});
