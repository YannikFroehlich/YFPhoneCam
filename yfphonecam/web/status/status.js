const LABELS = {
  phone_connected: "Phone connected",
  adb_device_connected: "USB / ADB connected",
  adb_device_serial: "Selected device serial",
  last_frame_age_ms: "Last frame age (ms)",
  resolution: "Negotiated resolution",
  fps: "Negotiated FPS",
  captured_frames: "Captured frames",
  sent_frames: "Sent frames",
  dropped_frames: "Dropped frames",
  dropped_busy_frames: "  - dropped (phone still encoding)",
  dropped_backpressure_frames: "  - dropped (network backlog)",
  avg_encode_ms: "Avg phone encode time (ms)",
  buffered_amount_bytes: "WebSocket send backlog (bytes)",
  capture_mode: "Phone capture mode",
  decoded_frames: "Decoded frames",
  virtualcam_active: "Virtual camera active",
  virtualcam_backend: "Virtual camera backend",
  virtualcam_error: "Virtual camera error",
  server_uptime_s: "Server uptime (s)",
};

const RATE_KEYS = new Set([
  "captured_frames",
  "sent_frames",
  "dropped_frames",
  "dropped_busy_frames",
  "dropped_backpressure_frames",
  "decoded_frames",
]);

let previous = null;

function renderValue(key, value, rate) {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") {
    const span = document.createElement("span");
    span.className = value ? "ok" : "bad";
    span.textContent = value ? "yes" : "no";
    return span;
  }
  if (Array.isArray(value)) return value.join(" x ");
  if (rate !== null) return `${value} (${rate.toFixed(1)} fps)`;
  return String(value);
}

async function refresh() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const now = performance.now();
    const elapsedS = previous ? (now - previous.now) / 1000 : 0;

    const table = document.getElementById("statusTable");
    table.innerHTML = "";
    for (const [key, label] of Object.entries(LABELS)) {
      const row = document.createElement("tr");
      const keyCell = document.createElement("td");
      keyCell.className = "key";
      keyCell.textContent = label;
      const valCell = document.createElement("td");

      let rate = null;
      if (RATE_KEYS.has(key) && previous && elapsedS > 0 && typeof data[key] === "number") {
        rate = (data[key] - previous.data[key]) / elapsedS;
      }
      const rendered = renderValue(key, data[key], rate);
      if (typeof rendered === "string") valCell.textContent = rendered;
      else valCell.appendChild(rendered);
      row.appendChild(keyCell);
      row.appendChild(valCell);
      table.appendChild(row);
    }
    previous = { data, now };
  } catch (e) {
    console.error("Status request failed", e);
  }
}

refresh();
setInterval(refresh, 1000);
