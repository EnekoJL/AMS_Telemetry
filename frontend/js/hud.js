/**
 * HUD & Telemetry Metrics Panel updates.
 */

const CARDINALS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"];

function courseToCardinal(deg) {
  const norm = ((deg % 360) + 360) % 360;
  const idx = Math.round(norm / 45);
  return CARDINALS[idx];
}

export class TelemetryHUD {
  constructor() {
    // Header chips
    this.sessionNameEl = document.getElementById("chip-session-name");
    this.durationEl = document.getElementById("chip-duration");
    this.distanceEl = document.getElementById("chip-distance");
    this.maxSpeedEl = document.getElementById("chip-max-speed");
    this.avgSpeedEl = document.getElementById("chip-avg-speed");
    this.pointsCountEl = document.getElementById("chip-points");

    // Live HUD elements
    this.speedKmhEl = document.getElementById("hud-speed-kmh");
    this.speedMsEl = document.getElementById("hud-speed-ms");
    this.distEl = document.getElementById("hud-dist");
    this.utcEl = document.getElementById("hud-utc");
    this.accelEl = document.getElementById("hud-accel");
    this.courseEl = document.getElementById("hud-course");
  }

  updateSessionSummary(summary) {
    if (this.sessionNameEl) this.sessionNameEl.textContent = summary.session_name;
    if (this.durationEl) this.durationEl.textContent = `${summary.duration_s.toFixed(1)}s`;
    if (this.distanceEl) {
      const km = (summary.total_distance_m / 1000.0).toFixed(2);
      this.distanceEl.textContent = `${km} km`;
    }
    if (this.maxSpeedEl) this.maxSpeedEl.textContent = `${summary.max_speed_kmh.toFixed(1)} km/h`;
    if (this.avgSpeedEl) this.avgSpeedEl.textContent = `${summary.avg_speed_kmh.toFixed(1)} km/h`;
    if (this.pointsCountEl) this.pointsCountEl.textContent = `${summary.gps_records.toLocaleString()} pts`;
  }

  updateInstant(point) {
    if (!point) return;

    // Big Primary Speed Gauge
    if (this.speedKmhEl) this.speedKmhEl.textContent = point.speed_kmh.toFixed(1);
    if (this.speedMsEl) this.speedMsEl.textContent = `${point.speed_ms.toFixed(1)} m/s`;

    // Digital Grid Metrics (Secondary duplicate speed removed)
    if (this.distEl) this.distEl.textContent = `${point.cum_dist_m.toFixed(0)} m`;
    if (this.utcEl) this.utcEl.textContent = point.utc_time || "—";

    if (this.accelEl) {
      const g = point.accel_g || 0.0;
      const prefix = g > 0 ? "+" : "";
      this.accelEl.textContent = `${prefix}${g.toFixed(2)} G`;
      this.accelEl.style.color = g > 0.3 ? "var(--accent-green)" : (g < -0.3 ? "var(--accent-pink)" : "var(--text-bright)");
    }

    if (this.courseEl) {
      const card = courseToCardinal(point.course_deg);
      this.courseEl.textContent = `${point.course_deg.toFixed(0)}° (${card})`;
    }
  }
}
