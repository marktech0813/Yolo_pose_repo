import { analyzeAudio, analyzeText, fetchHealth } from "./api.js";
import { WavRecorder } from "./recorder.js";
import {
  renderCoachMessage,
  renderPending,
  renderUserMessage,
  renderWelcome,
} from "./render.js";

const STORAGE_KEY = "northline.thread";

const thread = document.getElementById("thread");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const micBtn = document.getElementById("mic");
const sendBtn = document.getElementById("send");
const statusEl = document.getElementById("status");
const statusLabel = document.getElementById("status-label");
const hint = document.getElementById("composer-hint");
const recTimer = document.getElementById("rec-timer");
const live = document.getElementById("live");

let ready = false;
let busy = false;
let history = [];

const recorder = new WavRecorder({
  maxSeconds: 60,
  onTick: (sec) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    recTimer.hidden = false;
    recTimer.textContent = `${m}:${String(s).padStart(2, "0")}`;
  },
});

function setStatus(state, label) {
  statusEl.dataset.state = state;
  statusLabel.textContent = label;
}

function setReady(isReady, message) {
  ready = isReady;
  input.disabled = !isReady || busy;
  micBtn.disabled = !isReady || busy;
  sendBtn.disabled = !isReady || busy;
  hint.textContent = message || "";
}

function persist() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch {
    /* ignore quota */
  }
}

function restore() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const data = JSON.parse(raw);
    if (!Array.isArray(data) || !data.length) return false;
    history = data;
    for (const item of history) {
      if (item.role === "user") {
        renderUserMessage(thread, { text: item.text, durationSec: item.durationSec });
      } else if (item.role === "coach" && item.result) {
        renderCoachMessage(thread, item.result);
      }
    }
    return true;
  } catch {
    return false;
  }
}

async function pollHealth() {
  try {
    const h = await fetchHealth();
    if (h.status === "ok" && h.whisper_ready && h.languagetool_ready) {
      setStatus("ok", "Ready");
      setReady(true, "Mic or type — analysis stays on this machine.");
      return true;
    }
    if (h.status === "error") {
      setStatus("error", "Error");
      setReady(false, h.detail || "Models failed to load. Check the server log.");
      return false;
    }
    setStatus("loading", "Loading");
    setReady(false, "Loading the offline models…");
    return false;
  } catch {
    setStatus("loading", "Loading");
    setReady(false, "Waiting for the local server…");
    return false;
  }
}

async function waitUntilReady() {
  for (;;) {
    const ok = await pollHealth();
    if (ok) return;
    await new Promise((r) => setTimeout(r, 1500));
  }
}

async function runAnalyze(kind, payload) {
  if (!ready || busy) return;
  busy = true;
  setReady(true, kind === "audio" ? "Recognizing English speech…" : "Checking grammar & spelling…");
  input.disabled = true;
  micBtn.disabled = true;
  sendBtn.disabled = true;

  const userText = kind === "text" ? payload : "(voice)";
  renderUserMessage(thread, {
    text: kind === "text" ? payload : "Voice message",
    durationSec: kind === "audio" ? payload.durationSec : null,
  });
  history.push({
    role: "user",
    text: kind === "text" ? payload : "Voice message",
    durationSec: kind === "audio" ? payload.durationSec : null,
  });

  const pending = renderPending(thread);
  try {
    const result =
      kind === "text" ? await analyzeText(payload) : await analyzeAudio(payload.blob);
    pending.remove();
    if (kind === "audio" && result.transcript) {
      // Update last user bubble transcript if useful — keep voice label; show heard text in coach
    }
    renderCoachMessage(thread, result);
    history.push({ role: "coach", result });
    persist();
    live.textContent = result.coach_message;
  } catch (err) {
    pending.remove();
    const msg = err?.message || "Something went wrong.";
    const fail = {
      transcript: userText === "(voice)" ? "" : userText,
      coach_message: msg,
      alerts: [],
      metrics: {},
      suppressed: "none",
    };
    renderCoachMessage(thread, fail);
    live.textContent = msg;
  } finally {
    busy = false;
    setReady(true, "Mic or type — analysis stays on this machine.");
    input.focus();
  }
}

form.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  runAnalyze("text", text);
});

input.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    form.requestSubmit();
  }
});

function httpsMicUrl() {
  const host = location.hostname || "127.0.0.1";
  return `https://${host}:8443/`;
}

function micErrorMessage(err) {
  const name = err?.name || "";
  if (!window.isSecureContext) {
    return `Mic needs HTTPS. Open ${httpsMicUrl()} and accept the certificate warning once.`;
  }
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "Microphone blocked. Allow mic access for this site in the browser address bar.";
  }
  if (name === "NotFoundError") {
    return "No microphone found on this device.";
  }
  return err?.message || "Could not open the microphone.";
}

function showSecureBanner() {
  if (window.isSecureContext) return;
  const existing = document.getElementById("secure-banner");
  if (existing) return;
  const banner = document.createElement("div");
  banner.id = "secure-banner";
  banner.className = "secure-banner";
  banner.innerHTML = `Microphone needs a secure page. <a href="${httpsMicUrl()}">Continue on HTTPS :8443</a> (accept the certificate warning once).`;
  document.body.prepend(banner);
}

micBtn.addEventListener("click", async () => {
  if (!ready || busy) return;
  if (!recorder.recording) {
    try {
      await recorder.start();
      micBtn.setAttribute("aria-pressed", "true");
      hint.textContent = "Recording… tap Mic again to stop.";
    } catch (err) {
      hint.textContent = micErrorMessage(err);
    }
    return;
  }
  const blob = await recorder.stop();
  micBtn.setAttribute("aria-pressed", "false");
  recTimer.hidden = true;
  if (!blob) return;
  // Approximate duration from blob size: 16-bit mono 16kHz => 32000 bytes/sec + 44 header
  const durationSec = Math.max(0, (blob.size - 44) / 32000);
  if (durationSec < 0.3) {
    hint.textContent = "Recording too short — hold a little longer.";
    return;
  }
  runAnalyze("audio", { blob, durationSec });
});

if (!restore()) {
  renderWelcome(thread);
  history = [];
}

showSecureBanner();
waitUntilReady();
