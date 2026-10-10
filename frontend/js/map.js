/**
 * Leaflet Track Map with Smooth Green-to-Pink Speed Gradient & Vehicle Cursor.
 * - Ultra-reliable HD Satellite Imagery (Google Maps Satellite default + Esri World Imagery fallback)
 * - Seamless SVG vector rendering (prevents Canvas clipping & disappearing segments on zoom)
 * - Pre-buffered tile loading (keepBuffer: 6) to eliminate black unloaded tiles.
 */

import { speedToColor } from "./colormap.js";

export class TrackMap {
  constructor(containerId, onPointSelected) {
    this.containerId = containerId;
    this.onPointSelected = onPointSelected;
    this.map = null;
    this.trackLayerGroup = null;
    this.cursorMarker = null;
    this.points = [];
    this.minSpeed = 0;
    this.maxSpeed = 350;

    this.initMap();
  }

  initMap() {
    const container = document.getElementById(this.containerId);
    if (!container) return;

    // Use native vector SVG renderer (preferCanvas: false) so polyline segments
    // NEVER get clipped or disappear on zoom transitions
    this.map = L.map(this.containerId, {
      zoomControl: true,
      attributionControl: false,
      preferCanvas: false,
      wheelPxPerZoomLevel: 100,
    }).setView([41.07949, -0.20074], 16);

    // 1. Google Satellite HD (Default: Ultra-fast worldwide CDN, zero black tiles, up to zoom 20)
    const googleSatelliteLayer = L.tileLayer(
      "https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
      {
        maxZoom: 20,
        maxNativeZoom: 20,
        subdomains: ["mt0", "mt1", "mt2", "mt3"],
        keepBuffer: 6,
        updateWhenZooming: false,
        updateWhenIdle: false,
        attribution: "&copy; Google Maps",
      }
    );

    // 2. Esri World Imagery (High-Resolution Satellite Alternative)
    const esriSatelliteLayer = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        maxNativeZoom: 18,
        keepBuffer: 6,
        updateWhenZooming: false,
        attribution: "Tiles &copy; Esri, Maxar",
      }
    );

    // 3. Dark Base Map: Esri World Dark Gray Base
    const darkGrayTileLayer = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 16,
        maxNativeZoom: 16,
        keepBuffer: 6,
        updateWhenZooming: false,
        attribution: "Tiles &copy; Esri",
      }
    );

    // 4. OpenStreetMap with Dark Filter fallback
    const osmDarkTileLayer = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      maxNativeZoom: 19,
      keepBuffer: 6,
      className: "osm-dark-fallback",
      attribution: "&copy; OpenStreetMap contributors",
    });

    // Set Google Satellite as primary default layer
    googleSatelliteLayer.addTo(this.map);

    // Add interactive layer selector (top right)
    const baseMaps = {
      "Satélite Google (HD Rápido)": googleSatelliteLayer,
      "Satélite Esri (Detalle)": esriSatelliteLayer,
      "Oscuro Motorsport": darkGrayTileLayer,
      "OpenStreetMap": osmDarkTileLayer,
    };
    L.control.layers(baseMaps, null, { position: "topright" }).addTo(this.map);

    this.trackLayerGroup = L.layerGroup().addTo(this.map);

    // Vehicle cursor marker (Hot Racing Pink with white core)
    const cursorIcon = L.divIcon({
      className: "vehicle-cursor-wrapper",
      html: `<div class="vehicle-cursor-dot" id="cursor-dot"></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });

    this.cursorMarker = L.marker([41.07949, -0.20074], {
      icon: cursorIcon,
      zIndexOffset: 2000,
    }).addTo(this.map);

    // Responsive window resize
    window.addEventListener("resize", () => {
      this.invalidateSize();
    });

    // Ensure Leaflet calculates container geometry after first paint
    setTimeout(() => {
      this.invalidateSize();
    }, 100);

    // Click on map to jump to closest telemetry point
    this.map.on("click", (e) => {
      if (!this.points.length) return;
      const clickedLat = e.latlng.lat;
      const clickedLng = e.latlng.lng;

      let closestIdx = 0;
      let minDistSq = Infinity;
      for (let i = 0; i < this.points.length; i++) {
        const dLat = this.points[i].lat - clickedLat;
        const dLng = this.points[i].lon - clickedLng;
        const distSq = dLat * dLat + dLng * dLng;
        if (distSq < minDistSq) {
          minDistSq = distSq;
          closestIdx = i;
        }
      }

      if (this.onPointSelected) {
        this.onPointSelected(closestIdx);
      }
    });
  }

  loadTrackData(points, minSpeed, maxSpeed) {
    if (!this.map || !points || points.length < 2) return;

    this.points = points;
    this.minSpeed = minSpeed;
    this.maxSpeed = maxSpeed;

    this.trackLayerGroup.clearLayers();

    // 1. Draw continuous dark track baseline (guarantees seamless, unbreakable road visibility)
    const allCoords = points.map((p) => [p.lat, p.lon]);
    L.polyline(allCoords, {
      color: "#0a0f18",
      weight: 8,
      opacity: 0.95,
      lineCap: "round",
      lineJoin: "round",
    }).addTo(this.trackLayerGroup);

    // 2. Smooth speeds slightly to prevent high-frequency noise from fragmenting lines
    const smoothedSpeeds = [];
    for (let i = 0; i < points.length; i++) {
      const prev = points[Math.max(0, i - 1)].speed_kmh;
      const curr = points[i].speed_kmh;
      const next = points[Math.min(points.length - 1, i + 1)].speed_kmh;
      smoothedSpeeds.push((prev + curr * 2 + next) / 4.0);
    }

    // 3. Group consecutive points into seamless overlapping colored SVG segments
    const NUM_BINS = 24;
    let currentBin = -1;
    let currentSegment = [];

    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      const speed = smoothedSpeeds[i];
      const norm = Math.max(0, Math.min(1, (speed - minSpeed) / (maxSpeed - minSpeed || 1)));
      const bin = Math.min(NUM_BINS - 1, Math.floor(norm * NUM_BINS));

      if (bin !== currentBin && currentSegment.length > 0) {
        // Close previous segment (include current point so segments connect seamlessly with zero gaps)
        currentSegment.push([p.lat, p.lon]);

        const speedNorm = (currentBin + 0.5) / NUM_BINS;
        const approxSpeed = minSpeed + speedNorm * (maxSpeed - minSpeed);
        const color = speedToColor(approxSpeed, minSpeed, maxSpeed);

        L.polyline(currentSegment, {
          color: color,
          weight: 5,
          opacity: 0.95,
          lineCap: "round",
          lineJoin: "round",
        }).addTo(this.trackLayerGroup);

        // Start new segment from current point
        currentSegment = [[p.lat, p.lon]];
        currentBin = bin;
      } else {
        if (currentSegment.length === 0) {
          currentBin = bin;
        }
        currentSegment.push([p.lat, p.lon]);
      }
    }

    // Flush last segment
    if (currentSegment.length > 1) {
      const speedNorm = (currentBin + 0.5) / NUM_BINS;
      const approxSpeed = minSpeed + speedNorm * (maxSpeed - minSpeed);
      const color = speedToColor(approxSpeed, minSpeed, maxSpeed);

      L.polyline(currentSegment, {
        color: color,
        weight: 5,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(this.trackLayerGroup);
    }

    // 4. Add Start / Finish flag marker
    const startIcon = L.divIcon({
      className: "start-gate-wrapper",
      html: `<div class="start-gate-dot" title="Salida / Meta"></div>`,
      iconSize: [12, 12],
      iconAnchor: [6, 6],
    });
    L.marker([points[0].lat, points[0].lon], {
      icon: startIcon,
      zIndexOffset: 1500,
    }).addTo(this.trackLayerGroup);

    // 5. Position vehicle cursor at start
    this.setCursorPosition(points[0]);

    // 6. Force Leaflet to update layout & fit bounds
    this.invalidateSize();
    setTimeout(() => {
      this.invalidateSize();
      const bounds = L.latLngBounds(allCoords);
      if (bounds.isValid()) {
        this.map.fitBounds(bounds, { padding: [30, 30], maxZoom: 18 });
      }
    }, 80);
  }

  setCursorPosition(point) {
    if (!point || !this.cursorMarker) return;
    this.cursorMarker.setLatLng([point.lat, point.lon]);
  }

  invalidateSize() {
    if (this.map) {
      this.map.invalidateSize();
    }
  }
}
