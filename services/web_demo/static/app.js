const ui = {
  decision: document.querySelector("#decision"),
  controls: document.querySelector("#universal-controls"),
  status: document.querySelector("#status-message"),
  mode: document.querySelector("#mode-badge"),
  voice: document.querySelector("#voice-status"),
  progressLabel: document.querySelector("#progress-label"),
  progress: document.querySelector("#progress-value"),
  trace: document.querySelector("#trace-list"),
  traceCount: document.querySelector("#trace-count"),
  accessDialog: document.querySelector("#access-dialog"),
  accessForm: document.querySelector("#access-form"),
  accessCode: document.querySelector("#access-code"),
  accessError: document.querySelector("#access-error"),
  profileButton: document.querySelector("#profile-button"),
  profileDialog: document.querySelector("#profile-dialog"),
  profileForm: document.querySelector("#profile-form"),
  profileSelect: document.querySelector("#profile-select"),
  profileInput: document.querySelector("#profile-input"),
  profileError: document.querySelector("#profile-error"),
  candidateTemplate: document.querySelector("#candidate-template"),
};

const RECORDING_STOP_HEADROOM_SECONDS = 0.5;

const appState = {
  demoToken: sessionStorage.getItem("meantbyme_demo_token") || "",
  sessionId: "",
  sessionToken: "",
  model: null,
  recorder: null,
  recordingStartedAt: 0,
  recordingTimer: null,
  recordingAutoStopStarted: false,
  maxAudioSeconds: 20,
  audioUrls: [],
  readbackCompleted: false,
  profiles: [],
  profileRef: "no_profile",
  profileLanguage: "en",
  replayAfterCreate: false,
  lastAudioBlob: null,
};

const stageProgress = {
  ready: 6,
  capturing: 14,
  heard_content_review: 34,
  category_clarification: 48,
  candidate_selection: 62,
  final_review: 78,
  patient_confirmed: 86,
  voice_authorized: 90,
  spoken: 94,
  memory_updated: 97,
  completed: 100,
  stopped: 100,
};

const stageLabels = {
  ready: "Ready",
  capturing: "Listening",
  heard_content_review: "Check what was heard",
  category_clarification: "Clarify the topic",
  candidate_selection: "Choose an expression",
  final_review: "Private final review",
  patient_confirmed: "Confirmed",
  voice_authorized: "Voice authorized",
  spoken: "Spoken",
  memory_updated: "Memory updated",
  completed: "Completed",
  stopped: "Stopped",
};

const eventLabels = {
  SESSION_STARTED: "Session started",
  AUDIO_CAPTURED: "Speech captured",
  ASR_RESULT_RECEIVED: "ASR evidence received",
  EVIDENCE_EXTRACTED: "Stable and uncertain fragments extracted",
  MEMORY_RETRIEVED: "Verified expression memory retrieved",
  CONTEXT_RETRIEVED: "Situational memory retrieved",
  UNCERTAINTY_ASSESSED: "Uncertainty route assessed",
  CLARIFICATION_REQUESTED: "Clarification requested",
  CANDIDATES_GENERATED: "Expression candidates generated",
  CANDIDATES_RERANKED: "Candidates ordered by evidence",
  PATIENT_SELECTION_RECEIVED: "Patient selection received",
  PRIVATE_READBACK_READY: "Private readback ready",
  FINAL_CONFIRMATION_RECEIVED: "Explicit confirmation received",
  VOICE_AUTHORIZATION_GRANTED: "Personal voice authorization granted",
  VOICE_AUTHORIZATION_BLOCKED: "Personal voice authorization blocked",
  TTS_FAILED: "Speech synthesis failed",
  EXPRESSION_SPOKEN: "Confirmed expression spoken",
  EXPRESSION_RECEIPT_CREATED: "Expression Receipt created",
  VERIFIED_MEMORY_WRITTEN: "Verified memory updated",
  SESSION_COMPLETED: "Session completed",
  SESSION_STOPPED: "Session stopped",
  COMMAND_REJECTED: "Command rejected",
  INPUT_METHOD_SWITCH_REQUESTED: "Input method switch requested",
  HELP_REQUESTED: "Help requested",
};

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (appState.demoToken) headers.set("X-Demo-Token", appState.demoToken);
  if (appState.sessionToken) headers.set("X-Demo-Session", appState.sessionToken);
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (_) {
      // Keep the status-only message.
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response;
}

async function initialize() {
  try {
    const health = await (await fetch("/api/health")).json();
    ui.mode.textContent = health.mode.toUpperCase();
    appState.maxAudioSeconds = Number(health.max_audio_seconds) || 20;
    if (health.demo_access_configured && !appState.demoToken) {
      ui.accessDialog.showModal();
      ui.accessCode.focus();
      return;
    }
    await openProfileSetup();
  } catch (error) {
    showFatal(error.message);
  }
}

async function createSession() {
  clearAudioUrls();
  appState.sessionId = "";
  appState.sessionToken = "";
  appState.model = null;
  appState.readbackCompleted = false;
  setBusy("Starting simulated session…");
  try {
    const response = await api("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: appState.profileLanguage,
        profile_ref: appState.profileRef,
      }),
    });
    const payload = await response.json();
    appState.sessionId = payload.session.session_id;
    appState.sessionToken = payload.session_token;
    delete payload.session_token;
    update(payload);
    if (appState.replayAfterCreate && appState.lastAudioBlob) {
      appState.replayAfterCreate = false;
      await uploadAudio(appState.lastAudioBlob);
      await sendCommand("start_capture");
      if (appState.model.session.stage === "capturing") {
        await sendCommand("stop_capture");
      }
    }
  } catch (error) {
    if (error.status === 401) {
      appState.demoToken = "";
      sessionStorage.removeItem("meantbyme_demo_token");
      ui.accessError.textContent = "That access code was not accepted.";
      ui.accessDialog.showModal();
      ui.accessCode.focus();
      return;
    }
    showFatal(error.message);
  }
}

async function openProfileSetup({ replay = false } = {}) {
  setBusy("Loading simulated profiles…");
  try {
    const response = await api("/api/profiles");
    const payload = await response.json();
    appState.profiles = payload.profiles;
    appState.replayAfterCreate = replay;
    renderProfileOptions();
    ui.profileError.textContent = "";
    ui.profileDialog.showModal();
  } catch (error) {
    if (error.status === 401) {
      appState.demoToken = "";
      sessionStorage.removeItem("meantbyme_demo_token");
      ui.accessError.textContent = "That access code was not accepted.";
      ui.accessDialog.showModal();
      return;
    }
    showFatal(error.message);
  }
}

function renderProfileOptions(extraProfile = null) {
  const profiles = extraProfile
    ? [...appState.profiles, extraProfile]
    : appState.profiles;
  ui.profileSelect.innerHTML = "";
  profiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.profile_ref;
    option.textContent = profile.label;
    option.dataset.language = profile.default_language;
    if (profile.profile_ref === appState.profileRef) option.selected = true;
    ui.profileSelect.append(option);
  });
}

async function sendCommand(command, payload = {}, confirmationMethod = null) {
  setStatus("");
  setInteractionDisabled(true);
  try {
    const response = await api(`/api/sessions/${appState.sessionId}/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command,
        payload,
        confirmation_method: confirmationMethod,
      }),
    });
    update(await response.json());
  } catch (error) {
    setStatus(error.message);
  } finally {
    setInteractionDisabled(false);
  }
}

async function uploadAudio(blob) {
  appState.lastAudioBlob = blob;
  const response = await api(`/api/sessions/${appState.sessionId}/audio`, {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: blob,
  });
  return response.json();
}

function update(payload) {
  appState.model = payload;
  const stage = payload.session.stage;
  ui.mode.textContent = payload.mode.toUpperCase();
  ui.progressLabel.textContent = stageLabels[stage] || stage;
  ui.progress.style.width = `${stageProgress[stage] || 10}%`;
  ui.voice.textContent = voiceLabel(payload.session.personal_voice_status);
  ui.voice.dataset.status = payload.session.personal_voice_status;
  ui.profileButton.textContent = payload.profile?.label || "No profile";
  renderDecision();
  renderControls();
  renderTrace();
}

function renderDecision() {
  clearAudioUrls();
  const model = appState.model;
  const stage = model.session.stage;
  if (model.failure_status === "heard_content_rejected") {
    renderRejectedHeardContent();
    return;
  }
  if (stage === "ready") renderReady();
  else if (stage === "capturing") renderCapturing();
  else if (stage === "heard_content_review") renderHeardReview();
  else if (stage === "category_clarification") renderCategory();
  else if (stage === "candidate_selection") renderCandidates();
  else if (stage === "final_review") renderFinalReview();
  else if (stage === "completed") renderCompleted();
  else if (stage === "stopped") renderStopped();
  else renderProcessing(stage);
}

function renderReady() {
  ui.decision.innerHTML = `
    <span class="eyebrow">New expression</span>
    <h1 id="stage-title">How would you like to speak?</h1>
    <p class="lead">Choose an input. The system will show what it heard before proposing any expression. Active profile: ${escapeHtml(appState.model.profile?.label || "No profile")}.</p>
    <div class="action-grid">
      <button id="start-microphone" class="button button-primary" type="button">Start microphone</button>
      <button id="use-demo" class="button button-secondary" type="button">Use demo fragment</button>
      <label class="button button-secondary" for="wav-input">Choose a WAV file</label>
      <input id="wav-input" class="visually-hidden" type="file" accept=".wav,audio/wav">
    </div>
  `;
  document.querySelector("#start-microphone").addEventListener("click", startMicrophone);
  document.querySelector("#use-demo").addEventListener("click", useDemoFragment);
  document.querySelector("#wav-input").addEventListener("change", useWavFile);
}

async function startMicrophone() {
  setStatus("");
  try {
    appState.recorder = await BrowserWavRecorder.create();
    await sendCommand("start_capture");
    if (appState.model.session.stage !== "capturing") return;
    appState.recorder.start();
    appState.recordingStartedAt = Date.now();
    startRecordingTimer();
  } catch (error) {
    appState.recorder = null;
    setStatus(`Microphone unavailable: ${error.message}`);
  }
}

async function useDemoFragment() {
  if (appState.model.mode !== "mock") {
    setStatus("Demo fragment is available only in mock mode. Record or upload WAV audio.");
    return;
  }
  await sendCommand("start_capture");
  if (appState.model.session.stage === "capturing") {
    await sendCommand("stop_capture");
  }
}

async function useWavFile(event) {
  const [file] = event.target.files;
  if (!file) return;
  try {
    await uploadAudio(file);
    await sendCommand("start_capture");
    if (appState.model.session.stage !== "capturing") return;
    await sendCommand("stop_capture");
  } catch (error) {
    setStatus(error.message);
  }
}

function renderCapturing() {
  ui.decision.innerHTML = `
    <span class="eyebrow">Speech capture</span>
    <h1 id="stage-title">Listening</h1>
    <div class="capture-display">
      <span class="record-dot" aria-hidden="true"></span>
      <div>
        <span id="capture-time" class="capture-time">00:00</span>
        <span class="capture-caption">Microphone capture remains unconfirmed evidence and stops at ${escapeHtml(appState.maxAudioSeconds)} seconds.</span>
      </div>
    </div>
    <div class="action-grid">
      <button id="stop-microphone" class="button button-primary" type="button">Stop and review</button>
      <label class="button button-secondary" for="capture-wav-input">Use WAV instead</label>
      <input id="capture-wav-input" class="visually-hidden" type="file" accept=".wav,audio/wav">
    </div>
  `;
  document.querySelector("#stop-microphone").addEventListener("click", stopMicrophone);
  document.querySelector("#capture-wav-input").addEventListener("change", replaceWithWav);
  updateCaptureClock();
}

async function stopMicrophone() {
  stopRecordingTimer();
  try {
    if (appState.recorder) {
      const wav = await appState.recorder.stop();
      appState.recorder = null;
      await uploadAudio(wav);
    }
    await sendCommand("stop_capture");
  } catch (error) {
    setStatus(error.message);
  }
}

async function replaceWithWav(event) {
  const [file] = event.target.files;
  if (!file) return;
  stopRecordingTimer();
  if (appState.recorder) {
    await appState.recorder.cancel();
    appState.recorder = null;
  }
  try {
    await uploadAudio(file);
    await sendCommand("stop_capture");
  } catch (error) {
    setStatus(error.message);
  }
}

function renderHeardReview() {
  const stable = appState.model.session.heard_stable;
  const uncertain = appState.model.session.heard_uncertain;
  ui.decision.innerHTML = `
    <span class="eyebrow">Heard content</span>
    <h1 id="stage-title">Is this part correct?</h1>
    <p class="lead">Only confirm the fragments that match what you meant to express.</p>
    <div class="evidence-band">
      ${tokenGroup("Stable fragments", stable, false)}
      ${uncertain.length ? tokenGroup("Uncertain fragments", uncertain, true) : ""}
    </div>
    <div class="action-grid">
      <button id="heard-yes" class="button button-primary" type="button">Yes, continue</button>
      <button id="heard-no" class="button button-secondary" type="button">No, stop this attempt</button>
    </div>
  `;
  document.querySelector("#heard-yes").addEventListener("click", () => sendCommand("confirm_heard_content"));
  document.querySelector("#heard-no").addEventListener("click", () => sendCommand("reject_heard_content"));
}

function renderRejectedHeardContent() {
  ui.decision.innerHTML = `
    <span class="eyebrow">Input rejected</span>
    <h1 id="stage-title">That attempt will not be used.</h1>
    <p class="lead">No candidate was confirmed and no verified memory was written.</p>
    <button id="new-after-reject" class="button button-primary" type="button">Start a new session</button>
  `;
  document.querySelector("#new-after-reject").addEventListener("click", createSession);
}

function renderCategory() {
  const options = appState.model.session.clarification_options;
  ui.decision.innerHTML = `
    <span class="eyebrow">One clarification</span>
    <h1 id="stage-title">${escapeHtml(appState.model.session.clarification_question || "What is this about?")}</h1>
    <div id="category-options" class="action-grid"></div>
  `;
  const target = document.querySelector("#category-options");
  options.forEach((option) => {
    const button = makeButton(option, "button button-secondary");
    button.addEventListener("click", () => sendCommand("select_category", { category: option }));
    target.append(button);
  });
}

function renderCandidates() {
  ui.decision.innerHTML = `
    <span class="eyebrow">Expression candidates</span>
    <h1 id="stage-title">Which one matches your meaning?</h1>
    <p class="lead">AI completion and memory can change the order, but they cannot choose for you.</p>
    <div id="candidate-list" class="candidate-list"></div>
  `;
  renderCandidateList(document.querySelector("#candidate-list"));
}

function renderCandidateList(target) {
  appState.model.session.candidates.forEach((candidate, index) => {
    const node = ui.candidateTemplate.content.cloneNode(true);
    node.querySelector(".candidate-index").textContent = index + 1;
    node.querySelector(".candidate-text").textContent = candidate.text;
    node.querySelector(".candidate-meta").textContent =
      `${candidate.source_level} · ${riskLabel(candidate.risk_level)}`;
    node.querySelector(".candidate-select").addEventListener("click", () => {
      appState.readbackCompleted = false;
      sendCommand("select_candidate", { candidate_id: candidate.id });
    });
    const provenance = node.querySelector(".candidate-provenance");
    candidate.patient_supported_spans.forEach((span) => {
      provenance.append(makeChip(`Patient: ${span}`, "span-chip"));
    });
    candidate.ai_added_spans.forEach((span) => {
      provenance.append(makeChip(`AI added: ${span}`, "span-chip ai"));
    });
    if (candidate.memory_support_ids.length) {
      provenance.append(makeChip("Verified memory support", "span-chip"));
    }
    target.append(node);
  });
}

function renderFinalReview() {
  const selected = appState.model.selected_candidate;
  if (!selected) {
    ui.decision.innerHTML = `
      <span class="eyebrow">Final review route</span>
      <h1 id="stage-title">Choose the expression to review.</h1>
      <p class="lead">A low-uncertainty route still requires your explicit selection and final confirmation.</p>
      <div id="candidate-list" class="candidate-list"></div>
    `;
    renderCandidateList(document.querySelector("#candidate-list"));
    return;
  }
  const strict = appState.model.strict;
  const l3 = selected.source_level === "L3";
  ui.decision.innerHTML = `
    <span class="eyebrow">Private final review</span>
    <h1 id="stage-title">Confirm the complete expression</h1>
    <div class="final-expression">${escapeHtml(selected.text)}</div>
    <div class="review-meta">
      <span class="source-badge">${escapeHtml(selected.source_level)} source</span>
      <span class="risk-badge ${escapeHtml(selected.risk_level)}">${escapeHtml(riskLabel(selected.risk_level))}</span>
      ${selected.memory_support_ids.length ? '<span class="memory-badge">Verified memory influenced ranking</span>' : ""}
    </div>
    <div class="candidate-provenance" id="review-provenance"></div>
    <div class="audio-review">
      <strong>Neutral private readback</strong>
      <span class="capture-caption">The patient’s personal voice is still blocked.</span>
      <audio id="neutral-audio" controls preload="none"></audio>
    </div>
    <label class="confirmation-check">
      <input id="readback-check" type="checkbox">
      <span>I completed the private readback and this expression is what I mean.</span>
    </label>
    ${strict ? `
      <label class="confirmation-check">
        <input id="strict-check" type="checkbox">
        <span>I completed the additional high-risk confirmation.</span>
      </label>` : ""}
    ${l3 ? `
      <label class="confirmation-check">
        <input id="l3-check" type="checkbox">
        <span>I explicitly confirm the larger AI-added portion.</span>
      </label>` : ""}
    <div class="action-grid">
      <button id="final-confirm" class="button button-primary" type="button" disabled>Confirm and speak</button>
      <button id="edit-expression" class="button button-secondary" type="button">Edit the completion</button>
    </div>
  `;
  const provenance = document.querySelector("#review-provenance");
  selected.patient_supported_spans.forEach((span) => provenance.append(makeChip(`Patient: ${span}`, "span-chip")));
  selected.ai_added_spans.forEach((span) => provenance.append(makeChip(`AI added: ${span}`, "span-chip ai")));
  const readbackCheck = document.querySelector("#readback-check");
  const strictCheck = document.querySelector("#strict-check");
  const l3Check = document.querySelector("#l3-check");
  const confirm = document.querySelector("#final-confirm");
  const updateConfirm = () => {
    appState.readbackCompleted = readbackCheck.checked;
    confirm.disabled = !readbackCheck.checked || (strict && !strictCheck.checked) || (l3 && !l3Check.checked);
  };
  readbackCheck.addEventListener("change", updateConfirm);
  strictCheck?.addEventListener("change", updateConfirm);
  l3Check?.addEventListener("change", updateConfirm);
  confirm.addEventListener("click", () => sendCommand(
    "final_confirm",
    {
      private_readback_completed: true,
      strict_confirmation: Boolean(strict),
      l3_confirmation: Boolean(l3),
    },
    "large_button",
  ));
  document.querySelector("#edit-expression").addEventListener("click", editExpression);
  loadAudio("neutral", document.querySelector("#neutral-audio"));
}

async function editExpression() {
  const current = appState.model.selected_candidate?.text || "";
  const text = window.prompt("Edit the expression. Your edit becomes patient-authored content.", current);
  if (text && text.trim()) {
    appState.readbackCompleted = false;
    await sendCommand("edit_completion", { text: text.trim() });
  }
}

function renderCompleted() {
  const selected = appState.model.selected_candidate;
  const receipt = appState.model.receipt;
  ui.decision.innerHTML = `
    <span class="eyebrow">Expression completed</span>
    <h1 id="stage-title">${escapeHtml(selected?.text || "Confirmed expression")}</h1>
    <p class="lead">The confirmed expression was authorized, spoken, receipted, and written to verified memory.</p>
    <div class="audio-review">
      <strong>Authorized personal-voice output</strong>
      <audio id="personal-audio" controls preload="none"></audio>
    </div>
    ${receipt ? receiptMarkup(receipt) : ""}
    <div class="action-grid">
      <button id="new-session" class="button button-primary" type="button">Start another expression</button>
      ${appState.lastAudioBlob ? '<button id="compare-profile" class="button button-secondary" type="button">Run same audio with another profile</button>' : ""}
    </div>
  `;
  loadAudio("personal", document.querySelector("#personal-audio"));
  document.querySelector("#new-session").addEventListener("click", () => createSession());
  document.querySelector("#compare-profile")?.addEventListener(
    "click",
    () => openProfileSetup({ replay: true }),
  );
}

function renderStopped() {
  ui.decision.innerHTML = `
    <span class="eyebrow">Session stopped</span>
    <h1 id="stage-title">Nothing was authorized to speak.</h1>
    <p class="lead">Stopping does not confirm a candidate or write verified memory.</p>
    <button id="new-session" class="button button-primary" type="button">Start a new session</button>
  `;
  document.querySelector("#new-session").addEventListener("click", () => createSession());
}

function renderProcessing(stage) {
  ui.decision.innerHTML = `
    <div class="loading-state">
      <span class="activity-indicator" aria-hidden="true"></span>
      <div>
        <span class="eyebrow">Runtime</span>
        <h1 id="stage-title">${escapeHtml(stageLabels[stage] || "Processing")}</h1>
      </div>
    </div>
  `;
}

function renderControls() {
  ui.controls.innerHTML = "";
  const actions = new Set(appState.model.session.allowed_actions);
  if (actions.has("go_back")) addControl("Back", "go_back", "button button-secondary");
  if (actions.has("none_of_these")) addControl("None of these", "none_of_these", "button button-secondary");
  if (actions.has("switch_input_method")) addControl("Switch input", "switch_input_method", "button button-secondary");
  if (actions.has("request_help")) addControl("Request help", "request_help", "button button-secondary");
  if (actions.has("stop")) addControl("Stop", "stop", "button button-danger");
}

function addControl(label, command, className) {
  const button = makeButton(label, className);
  button.dataset.command = command;
  button.addEventListener("click", () => sendCommand(command));
  ui.controls.append(button);
}

function renderTrace() {
  const events = appState.model.session.trace_items || [];
  ui.traceCount.textContent = events.length;
  if (!events.length) {
    ui.trace.innerHTML = '<p class="empty-trace">Events will appear as the session advances.</p>';
    return;
  }
  ui.trace.innerHTML = "";
  events.slice().reverse().forEach((event) => {
    const item = document.createElement("div");
    item.className = "trace-item";
    const marker = document.createElement("span");
    marker.className = "trace-marker";
    marker.setAttribute("aria-hidden", "true");
    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = eventLabels[event.event_type] || event.event_type;
    const detail = document.createElement("p");
    detail.textContent = traceDetail(event);
    content.append(title, detail);
    item.append(marker, content);
    ui.trace.append(item);
  });
}

function traceDetail(event) {
  const payload = event.payload || {};
  if (event.event_type === "ASR_RESULT_RECEIVED") return `${payload.provider} · ${payload.status}`;
  if (event.event_type === "EVIDENCE_EXTRACTED") return `${(payload.stable_fragments || []).length} stable · ${(payload.uncertain_fragments || []).length} uncertain`;
  if (event.event_type === "MEMORY_RETRIEVED") return `${payload.verified_count || 0} verified matches`;
  if (event.event_type === "CONTEXT_RETRIEVED") return `${payload.count || 0} context memories · sources kept distinct`;
  if (event.event_type === "UNCERTAINTY_ASSESSED") return `${payload.evidence_band} → ${payload.effective_route}`;
  if (event.event_type === "FINAL_CONFIRMATION_RECEIVED") return `${payload.method} · strict ${payload.strict ? "yes" : "no"}`;
  if (event.event_type === "VOICE_AUTHORIZATION_GRANTED") return "Scope: this expression only";
  if (event.event_type === "VERIFIED_MEMORY_WRITTEN") return `Gold memory · ${payload.new_write ? "new write" : "idempotent update"}`;
  return new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

async function loadAudio(kind, element) {
  if (!element || !appState.model.audio[`${kind}_available`]) {
    if (element) element.replaceWith(document.createTextNode("Audio is not available."));
    return;
  }
  try {
    const response = await api(`/api/sessions/${appState.sessionId}/audio/${kind}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    appState.audioUrls.push(url);
    element.src = url;
  } catch (error) {
    setStatus(error.message);
  }
}

function receiptMarkup(receipt) {
  return `
    <h2>Expression Receipt</h2>
    <dl class="receipt-table">
      ${receiptRow("Confirmation", receipt.confirmation_method)}
      ${receiptRow("Expression level", receipt.expression_level)}
      ${receiptRow("Voice scope", receipt.authorization_scope)}
      ${receiptRow("AI-added spans", receipt.ai_added_content.length ? receipt.ai_added_content.join(", ") : "None")}
      ${receiptRow("Memory evidence", receipt.memory_ids_used.length ? receipt.memory_ids_used.join(", ") : "None")}
      ${receiptRow("Final text hash", receipt.final_text_hash.slice(0, 16) + "…")}
    </dl>
  `;
}

function receiptRow(label, value) {
  return `<div class="receipt-row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value || "None"))}</dd></div>`;
}

function tokenGroup(label, values, uncertain) {
  return `
    <div class="evidence-group">
      <span class="evidence-label">${escapeHtml(label)}</span>
      <div class="token-row">${values.map((value) => `<span class="token ${uncertain ? "uncertain" : ""}">${escapeHtml(value)}</span>`).join("")}</div>
    </div>
  `;
}

function makeButton(label, className) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  return button;
}

function makeChip(label, className) {
  const chip = document.createElement("span");
  chip.className = className;
  chip.textContent = label;
  return chip;
}

function riskLabel(value) {
  if (value === "high_risk") return "High risk";
  if (value === "sensitive") return "Sensitive";
  return "Ordinary";
}

function voiceLabel(value) {
  if (value === "used") return "Personal voice used";
  if (value === "authorized") return "Voice authorized";
  if (value === "awaiting_confirmation") return "Awaiting confirmation";
  return "Voice blocked";
}

function setBusy(message) {
  ui.decision.innerHTML = `<div class="loading-state"><span class="activity-indicator" aria-hidden="true"></span><p>${escapeHtml(message)}</p></div>`;
}

function setStatus(message) {
  ui.status.textContent = message || "";
}

function showFatal(message) {
  ui.decision.innerHTML = `
    <span class="eyebrow">Demo unavailable</span>
    <h1 id="stage-title">The session could not start.</h1>
    <p class="lead">${escapeHtml(message)}</p>
  `;
}

function setInteractionDisabled(disabled) {
  document.querySelectorAll("button, input").forEach((element) => {
    if (!element.closest("#access-dialog")) element.disabled = disabled;
  });
}

function startRecordingTimer() {
  stopRecordingTimer();
  appState.recordingAutoStopStarted = false;
  appState.recordingTimer = window.setInterval(updateCaptureClock, 250);
}

function stopRecordingTimer() {
  if (appState.recordingTimer) window.clearInterval(appState.recordingTimer);
  appState.recordingTimer = null;
}

function updateCaptureClock() {
  const target = document.querySelector("#capture-time");
  if (!target || !appState.recordingStartedAt) return;
  const elapsedSeconds = (Date.now() - appState.recordingStartedAt) / 1000;
  const seconds = Math.floor(elapsedSeconds);
  target.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  if (
    elapsedSeconds >= Math.max(
      0.1,
      appState.maxAudioSeconds - RECORDING_STOP_HEADROOM_SECONDS,
    )
    && appState.recorder
    && !appState.recordingAutoStopStarted
  ) {
    appState.recordingAutoStopStarted = true;
    setStatus(`Maximum ${appState.maxAudioSeconds}-second recording reached.`);
    void stopMicrophone();
  }
}

function clearAudioUrls() {
  appState.audioUrls.forEach((url) => URL.revokeObjectURL(url));
  appState.audioUrls = [];
}

function escapeHtml(value) {
  const span = document.createElement("span");
  span.textContent = String(value ?? "");
  return span.innerHTML;
}

ui.accessForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  appState.demoToken = ui.accessCode.value;
  sessionStorage.setItem("meantbyme_demo_token", appState.demoToken);
  ui.accessError.textContent = "";
  ui.accessDialog.close();
  await openProfileSetup();
});

ui.profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const option = ui.profileSelect.selectedOptions[0];
  if (!option) return;
  appState.profileRef = option.value;
  appState.profileLanguage = option.dataset.language || "en";
  ui.profileDialog.close();
  await createSession();
});

ui.profileInput.addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  ui.profileError.textContent = "";
  try {
    const response = await api("/api/profiles", {
      method: "POST",
      headers: { "Content-Type": "text/markdown" },
      body: file,
    });
    const payload = await response.json();
    renderProfileOptions(payload.profile);
    ui.profileSelect.value = payload.profile.profile_ref;
  } catch (error) {
    ui.profileError.textContent = error.message;
  } finally {
    event.target.value = "";
  }
});

ui.profileButton.addEventListener("click", () => openProfileSetup());

class BrowserWavRecorder {
  constructor(stream, context, source, processor) {
    this.stream = stream;
    this.context = context;
    this.source = source;
    this.processor = processor;
    this.buffers = [];
    this.recording = false;
  }

  static async create() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const recorder = new BrowserWavRecorder(stream, context, source, processor);
    processor.onaudioprocess = (event) => {
      if (recorder.recording) {
        recorder.buffers.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      }
    };
    source.connect(processor);
    processor.connect(context.destination);
    return recorder;
  }

  start() {
    this.recording = true;
  }

  async stop() {
    this.recording = false;
    const merged = mergeBuffers(this.buffers);
    const downsampled = downsample(merged, this.context.sampleRate, 16000);
    await this.cleanup();
    return encodeWav(downsampled, 16000);
  }

  async cancel() {
    this.recording = false;
    await this.cleanup();
  }

  async cleanup() {
    this.processor.disconnect();
    this.source.disconnect();
    this.stream.getTracks().forEach((track) => track.stop());
    await this.context.close();
  }
}

function mergeBuffers(buffers) {
  const length = buffers.reduce((total, buffer) => total + buffer.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  buffers.forEach((buffer) => {
    merged.set(buffer, offset);
    offset += buffer.length;
  });
  return merged;
}

function downsample(input, inputRate, outputRate) {
  if (inputRate === outputRate) return input;
  const ratio = inputRate / outputRate;
  const output = new Float32Array(Math.floor(input.length / ratio));
  for (let index = 0; index < output.length; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(Math.floor((index + 1) * ratio), input.length);
    let sum = 0;
    for (let cursor = start; cursor < end; cursor += 1) sum += input[cursor];
    output[index] = sum / Math.max(1, end - start);
  }
  return output;
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return new Blob([view], { type: "audio/wav" });
}

function writeAscii(view, offset, text) {
  for (let index = 0; index < text.length; index += 1) {
    view.setUint8(offset + index, text.charCodeAt(index));
  }
}

initialize();
