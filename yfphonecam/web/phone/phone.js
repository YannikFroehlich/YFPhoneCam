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
let droppedBusyFrames = 0;
let droppedBackpressureFrames = 0;
let encodeMsTotal = 0;
let encodeSamples = 0;
let nextEncodeAt = 0;

const BUFFERED_THRESHOLD = 500_000;

const canvas = document.createElement("canvas");
const context = canvas.getContext("2d", { alpha: false });

// Reading frames straight from the track (bypassing the <video> element's
// display/compositing pipeline) can avoid a GPU readback stall that a fixed
// per-call encode-time floor pointed to on at least one real device. Falls
// back to the <video>+canvas path below when unsupported.
const offscreen = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(1, 1) : null;
const offscreenCtx = offscreen ? offscreen.getContext("2d", { alpha: false }) : null;
let frameReader = null;
let latestFrame = null;

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

function useFrameProcessor() {
  return Boolean(frameReader) && Boolean(offscreen) && Boolean(offscreenCtx);
}

async function pumpFrames(reader) {
  try {
    while (frameReader === reader) {
      const { value, done } = await reader.read();
      if (done) break;
      if (frameReader !== reader) {
        value.close();
        break;
      }
      capturedFrames += 1;
      if (latestFrame) {
        // Superseded before it could be encoded. That is only a real loss when
        // the encoder was the thing holding it up; otherwise it is just the
        // camera running ahead of the configured rate.
        latestFrame.close();
        if (encodingInFlight) {
          droppedFrames += 1;
          droppedBusyFrames += 1;
        }
      }
      latestFrame = value;
      if (ws) tryEncodeFrame(ws);
    }
  } catch (_error) {
    // Reader canceled or track ended; nothing to clean up beyond below.
  }
}

function teardownFrameProcessor() {
  if (frameReader) {
    const reader = frameReader;
    frameReader = null;
    reader.cancel().catch(() => {});
  }
  if (latestFrame) {
    latestFrame.close();
    latestFrame = null;
  }
}

function setupFrameProcessor(track) {
  teardownFrameProcessor();
  if (typeof MediaStreamTrackProcessor === "undefined" || !offscreen || !offscreenCtx) return;
  try {
    const processor = new MediaStreamTrackProcessor({ track });
    frameReader = processor.readable.getReader();
    void pumpFrames(frameReader);
  } catch (_error) {
    frameReader = null;
  }
}

function captureConstraints(capture, deviceId, pinFrameRate) {
  // frameRate needs a lower bound, not just ideal/max: with the floor left open
  // the camera can settle on a range like [10, 30] and run at its minimum in
  // dim light to lengthen exposure, which arrives here as a stuck-slow stream.
  const frameRate = pinFrameRate
    ? { min: capture.fps, ideal: capture.fps, max: capture.fps }
    : { ideal: capture.fps, max: capture.fps };
  return {
    video: {
      deviceId: deviceId ? { exact: deviceId } : undefined,
      facingMode: deviceId ? undefined : { ideal: "environment" },
      width: { ideal: capture.width, max: capture.width },
      height: { ideal: capture.height, max: capture.height },
      frameRate,
    },
    audio: false,
  };
}

async function openStream(capture, deviceId) {
  try {
    return await navigator.mediaDevices.getUserMedia(captureConstraints(capture, deviceId, true));
  } catch (error) {
    // A pinned frame rate is a hard constraint, so fall back to the hint-only
    // form instead of failing to open the camera at all.
    if (error && error.name === "OverconstrainedError") {
      return navigator.mediaDevices.getUserMedia(captureConstraints(capture, deviceId, false));
    }
    throw error;
  }
}

async function replaceCamera(capture = config, deviceId = null) {
  const newStream = await openStream(capture, deviceId || capture.camera_id || undefined);
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
  setupFrameProcessor(stream.getVideoTracks()[0]);
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

function drawFitted(ctx, source, sourceWidth, sourceHeight, targetWidth, targetHeight) {
  const scale = Math.min(targetWidth / sourceWidth, targetHeight / sourceHeight);
  const width = Math.max(1, Math.round(sourceWidth * scale));
  const height = Math.max(1, Math.round(sourceHeight * scale));
  const left = Math.floor((targetWidth - width) / 2);
  const top = Math.floor((targetHeight - height) / 2);
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, targetWidth, targetHeight);
  ctx.drawImage(source, left, top, width, height);
}

function resizeSurface(surface, width, height) {
  // Assigning width/height reallocates and clears the backing store even when
  // the value is unchanged, so only touch it on an actual size change.
  if (surface.width !== width) surface.width = width;
  if (surface.height !== height) surface.height = height;
}

function captureNextFrame(video, targetWidth, targetHeight) {
  // The camera may ignore requested width/height and keep streaming at its
  // native resolution, so downscale here rather than trust the negotiated
  // capture size — otherwise JPEG-encoding a much larger frame every tick
  // becomes the bottleneck regardless of the configured resolution.
  if (useFrameProcessor()) {
    const frame = latestFrame;
    if (!frame) return false;
    latestFrame = null;
    resizeSurface(offscreen, targetWidth, targetHeight);
    drawFitted(offscreenCtx, frame, frame.displayWidth, frame.displayHeight, targetWidth, targetHeight);
    frame.close();
    return true;
  }
  if (video.videoWidth && video.videoHeight) {
    resizeSurface(canvas, targetWidth, targetHeight);
    drawFitted(context, video, video.videoWidth, video.videoHeight, targetWidth, targetHeight);
    return true;
  }
  return false;
}

function encodeSurface(quality) {
  if (useFrameProcessor()) {
    return offscreen.convertToBlob({ type: "image/jpeg", quality });
  }
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
}

function frameIntervalMs() {
  return 1000 / Math.max(1, config.fps || 30);
}

function armSendTimer(socket, delayMs) {
  clearTimeout(sendTimer);
  sendTimer = setTimeout(() => {
    sendTimer = null;
    tryEncodeFrame(socket);
  }, Math.max(1, delayMs));
}

function sendEncodedFrame(socket, jpegBuffer) {
  const header = new ArrayBuffer(12);
  const view = new DataView(header);
  view.setUint32(0, sequence++, true);
  view.setBigUint64(4, BigInt(Date.now()), true);
  const packet = new Uint8Array(12 + jpegBuffer.byteLength);
  packet.set(new Uint8Array(header), 0);
  packet.set(new Uint8Array(jpegBuffer), 12);
  socket.send(packet);
  sentFrames += 1;
}

// Encode as soon as a frame is ready and the encoder is free, instead of on a
// fixed timer grid. A grid quantizes throughput to integer divisions of the
// configured rate (30 -> 15 -> 10 fps), so a frame that overruns its slot by a
// millisecond costs a whole slot; here it only delays itself.
function tryEncodeFrame(socket) {
  if (!running || ws !== socket || socket.readyState !== WebSocket.OPEN) return;
  if (encodingInFlight) return; // the in-flight encode calls back in when it settles

  const now = performance.now();
  if (now < nextEncodeAt) {
    armSendTimer(socket, nextEncodeAt - now);
    return;
  }
  if (socket.bufferedAmount >= BUFFERED_THRESHOLD) {
    droppedFrames += 1;
    droppedBackpressureFrames += 1;
    armSendTimer(socket, frameIntervalMs());
    return;
  }
  if (!captureNextFrame($("localVideo"), config.width, config.height)) {
    // No fresh frame yet. The track processor wakes us on arrival; the
    // <video> fallback has no such signal and needs the retry timer.
    armSendTimer(socket, frameIntervalMs());
    return;
  }
  // The track-processor path already counted this frame as the camera delivered it.
  if (!useFrameProcessor()) capturedFrames += 1;

  nextEncodeAt = now + frameIntervalMs();
  encodingInFlight = true;
  const encodeStart = performance.now();
  encodeSurface((config.jpeg_quality || 80) / 100)
    .then((blob) => {
      if (!blob) {
        droppedFrames += 1;
        return;
      }
      return blob.arrayBuffer().then((jpegBuffer) => {
        encodeMsTotal += performance.now() - encodeStart;
        encodeSamples += 1;
        if (!running || ws !== socket || socket.readyState !== WebSocket.OPEN ||
            socket.bufferedAmount >= BUFFERED_THRESHOLD) {
          droppedFrames += 1;
          droppedBackpressureFrames += 1;
          return;
        }
        sendEncodedFrame(socket, jpegBuffer);
      });
    })
    .catch(() => {
      droppedFrames += 1;
    })
    .finally(() => {
      encodingInFlight = false;
      tryEncodeFrame(socket);
    });
}

function startSendLoop(socket) {
  stopSendLoop();
  nextEncodeAt = 0;
  tryEncodeFrame(socket);
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
  teardownFrameProcessor();
  if (stream) stream.getTracks().forEach((track) => track.stop());
  stream = null;
  $("localVideo").srcObject = null;
  setStatus("Stopped");
  updateButtons();
}

setInterval(() => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "stats",
      capturedFrames,
      sentFrames,
      droppedFrames,
      droppedBusyFrames,
      droppedBackpressureFrames,
      avgEncodeMs: encodeSamples > 0 ? encodeMsTotal / encodeSamples : null,
      bufferedAmount: ws.bufferedAmount,
      captureMode: useFrameProcessor() ? "track-processor" : "video-element",
    }));
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
