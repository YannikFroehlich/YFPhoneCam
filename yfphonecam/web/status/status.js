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
  decoded_frames: "Decoded frames",
  virtualcam_active: "Virtual camera active",
  virtualcam_backend: "Virtual camera backend",
  virtualcam_error: "Virtual camera error",
  server_uptime_s: "Server uptime (s)",
};

function renderValue(key, value) {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") {
    const span = document.createElement("span");
    span.className = value ? "ok" : "bad";
    span.textContent = value ? "yes" : "no";
    return span;
  }
  if (Array.isArray(value)) return value.join(" x ");
  return String(value);
}

async function refresh() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const table = document.getElementById("statusTable");
    table.innerHTML = "";
    for (const [key, label] of Object.entries(LABELS)) {
      const row = document.createElement("tr");
      const keyCell = document.createElement("td");
      keyCell.className = "key";
      keyCell.textContent = label;
      const valCell = document.createElement("td");
      const rendered = renderValue(key, data[key]);
      if (typeof rendered === "string") valCell.textContent = rendered;
      else valCell.appendChild(rendered);
      row.appendChild(keyCell);
      row.appendChild(valCell);
      table.appendChild(row);
    }
  } catch (e) {
    console.error("Status request failed", e);
  }
}

refresh();
setInterval(refresh, 1000);
