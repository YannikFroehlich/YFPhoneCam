const $ = (id) => document.getElementById(id);

const PROTOCOL_VERSION = 1;
let config = { width: 1280, height: 720, fps: 30, jpeg_quality: 80, camera_id: null };
let stream = null;
let ws = null;
let running = false;
let allowReconnect = true;
let reconnectTimer = null;
let reconnectDelay = 1000;
let sendTimer = null;
let encodingInFlight = false;
let configurationChain = Promise.resolve();
let sequence = 0;
let capturedFrames = 0;
let sentFrames = 0;
let droppedFrames = 0;

const canvas = document.createElement("canvas");
const context = canvas.getContext("2d", { alpha: false });

function setStatus(text, kind = "") {
  $("status").textContent = text;
  $("status").dataset.kind = kind;
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config", { cache: "no-store" });
    if (response.ok) config = await response.json();
  } catch (error) {
    console.warn("Could not load server configuration", error);
  }
}

function facingFromLabel(label) {
  if (/back|rear|environment/i.test(label)) return "environment";
  if (/front|user|selfie/i.test(label)) return "user";
  return "unknown";
}

async function listCameras(socket = ws) {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const cameras = devices.filter((device) => device.kind === "videoinput");
  const select = $("cameraSelect");
  const previous = select.value || config.camera_id;
  select.replaceChildren();

  cameras.forEach((camera, index) => {
    const option = document.createElement("option");
    option.value = camera.deviceId;
    option.textContent = camera.label || `Camera ${index + 1}`;
    select.appendChild(option);
  });

  if (previous && cameras.some((camera) => camera.deviceId === previous)) {
    select.value = previous;
  } else {
    const environment = cameras.find((camera) => facingFromLabel(camera.label) === "environment");
    if (environment) select.value = environment.deviceId;
  }

  if (socket && socket.readyState === WebSocket.OPEN) {
    const track = stream ? stream.getVideoTracks()[0] : null;
    const capabilities = track && track.getCapabilities ? track.getCapabilities() : {};
    const range = (value) => value && typeof value === "object"
      ? { min: value.min, max: value.max }
      : {};
    socket.send(JSON.stringify({
      type: "capabilities",
      cameras: cameras.map((camera, index) => ({
        id: camera.deviceId,
        label: camera.label || `Camera ${index + 1}`,
        facing: facingFromLabel(camera.label),
      })),
      capture: {
        width: range(capabilities.width),
        height: range(capabilities.height),
        frameRate: range(capabilities.frameRate),
      },
    }));
  }
  return cameras;
}

function captureConstraints(capture, deviceId) {
  return {
    video: {
      deviceId: deviceId ? { exact: deviceId } : undefined,
      facingMode: deviceId ? undefined : { ideal: "environment" },
      width: { ideal: capture.width, max: capture.width },
      height: { ideal: capture.height, max: capture.height },
      frameRate: { ideal: capture.fps, max: capture.fps },
    },
    audio: false,
  };
}

async function replaceCamera(capture = config, deviceId = null) {
  const newStream = await navigator.mediaDevices.getUserMedia(
    captureConstraints(capture, deviceId || capture.camera_id || undefined)
  );
  const oldStream = stream;
  const video = $("localVideo");
  video.srcObject = newStream;
  try {
    await video.play();
  } catch (error) {
    newStream.getTracks().forEach((track) => track.stop());
    video.srcObject = oldStream;
    throw error;
  }
  stream = newStream;
  if (oldStream) oldStream.getTracks().forEach((track) => track.stop());
  config = { ...config, ...capture, camera_id: deviceId || capture.camera_id || null };
  await listCameras();
  return stream.getVideoTracks()[0].getSettings();
}

function sendHello(socket) {
  if (!stream || socket.readyState !== WebSocket.OPEN) return;
  const settings = stream.getVideoTracks()[0].getSettings();
  socket.send(JSON.stringify({
    type: "hello",
    protocol: PROTOCOL_VERSION,
    role: "phone",
    width: settings.width,
    height: settings.height,
    fps: settings.frameRate || config.fps,
    browser: "Chrome",
    userAgent: navigator.userAgent,
  }));
}

async function applyConfiguration(socket, message) {
  const capture = {
    width: message.width,
    height: message.height,
    fps: message.fps,
    jpeg_quality: message.jpegQuality,
    camera_id: message.deviceId || null,
  };
  try {
    const actual = await replaceCamera(capture, capture.camera_id || null);
    socket.send(JSON.stringify({
      type: "configured",
      requestId: message.requestId,
      ok: true,
      actual: {
        width: actual.width,
        height: actual.height,
        fps: actual.frameRate || capture.fps,
      },
    }));
    setStatus("Connected — streaming over USB", "ok");
  } catch (error) {
    socket.send(JSON.stringify({
      type: "configured",
      requestId: message.requestId,
      ok: false,
      error: String(error.message || error),
    }));
    setStatus(`Could not apply camera settings: ${error.message}`, "error");
  }
}

function connectWebSocket() {
  if (!running || !stream) return;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);
  socket.binaryType = "arraybuffer";
  ws = socket;

  socket.onopen = async () => {
    if (ws !== socket) return;
    reconnectDelay = 1000;
    allowReconnect = true;
    setStatus("Connected — streaming over USB", "ok");
    sendHello(socket);
    await listCameras(socket);
    startSendLoop(socket);
  };

  socket.onclose = () => {
    if (ws !== socket) return;
    ws = null;
    stopSendLoop();
    if (running && allowReconnect) {
      setStatus("Connection lost — retrying…", "warn");
      scheduleReconnect();
    }
  };

  socket.onerror = () => socket.close();
  socket.onmessage = (event) => {
    if (typeof event.data !== "string") return;
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (_error) {
      return;
    }
    if (message.type === "ping" && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "pong" }));
    } else if (message.type === "configure") {
      configurationChain = configurationChain
        .then(() => applyConfiguration(socket, message))
        .catch((error) => console.warn("Configuration failed", error));
    } else if (message.type === "bye") {
      allowReconnect = false;
      running = false;
      setStatus(message.reason === "replaced" ? "Another phone was selected" : "Stopped by PC");
      socket.close();
      updateButtons();
    }
  };
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    if (running && allowReconnect && !ws) connectWebSocket();
  }, reconnectDelay);
  reconnectDelay = Math.min(reconnectDelay * 2, 5000);
}

function startSendLoop(socket) {
  stopSendLoop();
  const intervalMs = 1000 / Math.max(1, config.fps || 30);
  const bufferedThreshold = 500_000;
  const video = $("localVideo");

  const tick = () => {
    if (!running || socket.readyState !== WebSocket.OPEN) return;
    if (video.videoWidth && video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      context.drawImage(video, 0, 0);
      capturedFrames += 1;

      if (!encodingInFlight && socket.bufferedAmount < bufferedThreshold) {
        encodingInFlight = true;
        canvas.toBlob((blob) => {
          if (!blob) {
            encodingInFlight = false;
            droppedFrames += 1;
            return;
          }
          blob.arrayBuffer().then((jpegBuffer) => {
            if (!running || ws !== socket || socket.readyState !== WebSocket.OPEN ||
                socket.bufferedAmount >= bufferedThreshold) {
              droppedFrames += 1;
              return;
            }
            const header = new ArrayBuffer(12);
            const view = new DataView(header);
            view.setUint32(0, sequence++, true);
            view.setBigUint64(4, BigInt(Date.now()), true);
            const packet = new Uint8Array(12 + jpegBuffer.byteLength);
            packet.set(new Uint8Array(header), 0);
            packet.set(new Uint8Array(jpegBuffer), 12);
            socket.send(packet);
            sentFrames += 1;
          }).catch(() => {
            droppedFrames += 1;
          }).finally(() => {
            encodingInFlight = false;
          });
        }, "image/jpeg", (config.jpeg_quality || 80) / 100);
      } else {
        droppedFrames += 1;
      }
    }
    sendTimer = setTimeout(tick, intervalMs);
  };
  tick();
}

function stopSendLoop() {
  clearTimeout(sendTimer);
  sendTimer = null;
  encodingInFlight = false;
}

function updateButtons() {
  $("startBtn").disabled = running;
  $("stopBtn").disabled = !running;
}

async function start() {
  try {
    if (!stream) await replaceCamera(config, $("cameraSelect").value || null);
    running = true;
    allowReconnect = true;
    updateButtons();
    connectWebSocket();
  } catch (error) {
    setStatus(`Camera permission is required: ${error.message}`, "error");
  }
}

function stop() {
  running = false;
  allowReconnect = false;
  clearTimeout(reconnectTimer);
  stopSendLoop();
  if (ws) ws.close();
  ws = null;
  if (stream) stream.getTracks().forEach((track) => track.stop());
  stream = null;
  $("localVideo").srcObject = null;
  setStatus("Stopped");
  updateButtons();
}

setInterval(() => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "stats", capturedFrames, sentFrames, droppedFrames }));
  }
}, 2000);

$("startBtn").addEventListener("click", () => void start());
$("stopBtn").addEventListener("click", stop);
$("cameraSelect").addEventListener("change", async () => {
  if (!stream) return;
  try {
    await replaceCamera(config, $("cameraSelect").value);
    if (ws) sendHello(ws);
  } catch (error) {
    setStatus(`Could not switch camera: ${error.message}`, "error");
  }
});

(async function initialize() {
  await loadConfig();
  setStatus("Requesting camera permission…");
  await start();
})();
