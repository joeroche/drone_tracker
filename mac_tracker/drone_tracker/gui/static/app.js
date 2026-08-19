const state = {
  mode: "drone",
  currentJob: null,
  logs: [],
};

const $ = (id) => document.getElementById(id);

function logLine(message) {
  const t = new Date().toLocaleTimeString();
  state.logs.push(`${t} ${message}`);
  if (state.logs.length > 160) state.logs.shift();
  $("logs").textContent = state.logs.join("\n");
  $("logs").scrollTop = $("logs").scrollHeight;
}

async function api(path, body = null, method = null) {
  const verb = method || (body ? "POST" : "GET");
  const options = {
    method: verb,
    headers: {"Content-Type": "application/json"},
  };
  if (body) options.body = JSON.stringify(body);
  const response = await fetch(path, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text);
  }
  return response.json();
}

function setModeButton(mode) {
  document.querySelectorAll(".mode").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  state.mode = mode;
  $("enrollPanel").classList.toggle("hidden", mode === "drone");
  $("prompt").classList.toggle("hidden", mode !== "object");
  $("enrollTitle").textContent = mode === "face" ? "Face Enrollment" : "Object Enrollment";
  $("enrollHint").textContent = mode === "face"
    ? "Choose a directory of one-face photos to build a local identity profile."
    : "Choose object photos and give the detector a prompt for crop generation.";
  $("sMode").textContent = mode;
  $("sModel").textContent = mode === "drone" ? "drone yolo" : "profile required";
}

function updateStatus(payload) {
  const s = payload.state || payload;
  $("sMode").textContent = s.mode || state.mode;
  $("sCamera").textContent = s.camera || "idle";
  $("sProfile").textContent = s.profile_id || "none";
  $("sModel").textContent = s.mode === "drone" ? "drone yolo" : (s.profile_id ? "identity ready" : "profile required");
  $("sTrack").textContent = s.paused ? "paused" : (s.tracking ? "running" : "idle");
  $("sController").textContent = s.controller || (s.dry_run ? "dry_run" : "idle");
  $("sLock").textContent = s.lock ? "on" : "off";
  $("sMotion").textContent = `${Number(s.pan || 90).toFixed(1)} / ${Number(s.tilt || 90).toFixed(1)}`;
  $("dryRunToggle").checked = Boolean(s.dry_run);
  $("overlayState").textContent = s.status || "stream idle";
}

function renderReview(job) {
  state.currentJob = job;
  $("reviewSummary").textContent = `${job.status}: ${job.accepted_count} accepted, ${job.rejected_count} rejected`;
  $("sProfile").textContent = job.profile_id || "none";
  $("sModel").textContent = job.profile_id ? "identity ready" : "profile required";
  const grid = $("reviewGrid");
  grid.innerHTML = "";
  for (const item of job.items || []) {
    const card = document.createElement("article");
    card.className = `review-card ${item.accepted ? "accepted" : "rejected"}`;
    const img = document.createElement("img");
    img.src = item.crop_preview || item.preview;
    img.alt = "Enrollment crop preview";
    const p = document.createElement("p");
    p.textContent = `${item.accepted ? "accepted" : "rejected"}: ${item.reason}`;
    const actions = document.createElement("div");
    actions.className = "review-actions";
    const accept = document.createElement("button");
    accept.textContent = "Accept";
    accept.addEventListener("click", () => reviewItem(item.item_id, true));
    const reject = document.createElement("button");
    reject.textContent = "Reject";
    reject.addEventListener("click", () => reviewItem(item.item_id, false));
    actions.append(accept, reject);
    card.append(img, p, actions);
    grid.append(card);
  }
}

async function reviewItem(itemId, accepted) {
  if (!state.currentJob) return;
  const path = `/api/enroll/${state.currentJob.job_id}/${accepted ? "accept" : "reject"}`;
  const job = await api(path, {item_id: itemId});
  renderReview(job);
}

async function boot() {
  logLine("boot sequence armed");
  const config = await api("/api/config");
  updateStatus(config);
  setModeButton(config.state.mode || "drone");
  connectEvents();
  await api("/api/tracking/start", {}, "POST");
  logLine("tracking start requested");
}

function connectEvents() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${location.host}/api/events`);
  socket.addEventListener("open", () => logLine("event stream connected"));
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "log") logLine(payload.message);
    if (payload.type === "snapshot") updateStatus(payload);
    if (payload.type === "error") logLine(`error ${payload.message}`);
    if (payload.type === "movement") {
      logLine(`move mode=${payload.mode} target=${Number(payload.target)} pan=${payload.pan} tilt=${payload.tilt} lock=${Number(payload.locked)}`);
    }
    if (payload.type === "status") {
      $("targetBadge").textContent = payload.target ? `${payload.label || "target"} ${Number(payload.confidence).toFixed(2)}` : "target unknown";
      updateStatus({state: {
        mode: payload.mode,
        camera: $("sCamera").textContent,
        profile_id: $("sProfile").textContent === "none" ? "" : $("sProfile").textContent,
        tracking: true,
        paused: false,
        controller: payload.dry_run ? "dry_run" : $("sController").textContent,
        lock: payload.locked,
        pan: payload.pan,
        tilt: payload.tilt,
        dry_run: payload.dry_run,
        status: payload.target ? "tracking" : "unknown",
      }});
    }
  });
  socket.addEventListener("close", () => {
    logLine("event stream closed");
    setTimeout(connectEvents, 1200);
  });
}

document.querySelectorAll(".mode").forEach((button) => {
  button.addEventListener("click", async () => {
    const mode = button.dataset.mode;
    setModeButton(mode);
    const profileId = state.currentJob && state.currentJob.mode === mode ? state.currentJob.profile_id : undefined;
    const response = await api("/api/mode", {mode, profile_id: profileId});
    updateStatus(response);
    logLine(`mode switched ${mode}`);
  });
});

$("startBtn").addEventListener("click", async () => updateStatus(await api("/api/tracking/start", {}, "POST")));
$("pauseBtn").addEventListener("click", async () => updateStatus(await api("/api/tracking/pause", {}, "POST")));
$("resumeBtn").addEventListener("click", async () => updateStatus(await api("/api/tracking/resume", {}, "POST")));
$("stopBtn").addEventListener("click", async () => updateStatus(await api("/api/tracking/stop", {}, "POST")));
$("centerBtn").addEventListener("click", async () => updateStatus(await api("/api/controller/center", {}, "POST")));
$("dryRunToggle").addEventListener("change", async (event) => updateStatus(await api("/api/dry-run", {enabled: event.target.checked})));

$("enrollBtn").addEventListener("click", async () => {
  const directory = $("directory").value.trim();
  const profileName = $("profileName").value.trim();
  const prompt = $("prompt").value.trim();
  if (!directory || !profileName || (state.mode === "object" && !prompt)) {
    logLine("enrollment missing required fields");
    return;
  }
  const path = state.mode === "face" ? "/api/enroll/face" : "/api/enroll/object";
  const payload = state.mode === "face" ? {directory, profile_name: profileName} : {directory, profile_name: profileName, prompt};
  const job = await api(path, payload);
  renderReview(job);
  if (job.profile_id) {
    await api("/api/mode", {mode: state.mode, profile_id: job.profile_id});
  }
  logLine(`${state.mode} enrollment ${job.status}`);
});

boot().catch((error) => logLine(`boot error ${error.message}`));
