/**
 * API client for AMS Telemetry Studio backend.
 */

const BASE_URL = window.location.origin;

export async function fetchCurrentSession() {
  const response = await fetch(`${BASE_URL}/api/sessions/current`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
  }
  return await response.json();
}

export async function uploadSessionFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${BASE_URL}/api/sessions/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed (HTTP ${response.status})`);
  }
  return await response.json();
}

export async function uploadMultiTelemetryFiles(files) {
  const formData = new FormData();
  for (const f of files) {
    formData.append("files", f);
  }

  const response = await fetch(`${BASE_URL}/api/telemetry/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed (HTTP ${response.status})`);
  }
  return await response.json();
}

export async function loadSampleSession() {
  const response = await fetch(`${BASE_URL}/api/sessions/load-sample`, {
    method: "POST",
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
  }
  return await response.json();
}
