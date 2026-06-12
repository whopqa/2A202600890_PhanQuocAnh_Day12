const promptSamples = [
  "Theo quy dinh hien hanh, tang tru trai phep chat ma tuy co the bi xu ly nhu the nao?",
  "Trong corpus tin tuc, co bai nao noi ve nghe si lien quan ma tuy khong?",
  "Neu mot nguoi vua bi nghi tang tru ma tuy, vua co thong tin tren bao chi, he thong co the tong hop gi?",
];

const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const questionInput = document.getElementById("question");
const sendButton = document.getElementById("send-button");
const promptList = document.getElementById("prompt-list");
const serviceStatus = document.getElementById("service-status");
const statusSummary = document.getElementById("status-summary");
const runtimeInfo = document.getElementById("runtime-info");
const runtimeSummary = document.getElementById("runtime-summary");
const sessionPill = document.getElementById("session-pill");
const traceIdPill = document.getElementById("trace-id-pill");
const stage4Log = document.getElementById("stage4-log");
const stage5Log = document.getElementById("stage5-log");
const resetSessionButton = document.getElementById("reset-session");
const refreshStatusButton = document.getElementById("refresh-status");
const messageTemplate = document.getElementById("message-template");

function getSessionId() {
  let value = window.localStorage.getItem("day08-session-id");
  if (!value) {
    value = crypto.randomUUID();
    window.localStorage.setItem("day08-session-id", value);
  }
  return value;
}

function setSessionId(value) {
  window.localStorage.setItem("day08-session-id", value);
  sessionPill.textContent = `Session: ${value}`;
}

function resetSession() {
  const nextId = crypto.randomUUID();
  setSessionId(nextId);
  chatLog.innerHTML = "";
  addMessage({
    role: "assistant",
    detail: "He thong da tao thread moi.",
    body: "Ban co the dat lai cau hoi de kiem tra memory/context moi.",
  });
}

function addMessage({ role, detail, body }) {
  const fragment = messageTemplate.content.cloneNode(true);
  const article = fragment.querySelector(".message");
  article.classList.add(role);
  fragment.querySelector(".message-role").textContent = role === "user" ? "Ban" : "Assistant";
  fragment.querySelector(".message-detail").textContent = detail || "";
  fragment.querySelector(".message-body").textContent = body;
  chatLog.appendChild(fragment);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addPromptButtons() {
  promptSamples.forEach((prompt) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "prompt-button";
    button.textContent = prompt;
    button.addEventListener("click", () => {
      questionInput.value = prompt;
      questionInput.focus();
    });
    promptList.appendChild(button);
  });
}

function renderRuntimeInfo(info) {
  runtimeInfo.innerHTML = "";
  runtimeSummary.textContent = info.llm_enabled ? "Live LLM dang bat" : "Dang fallback/offline";

  const rows = [
    ["UI version", info.ui_version],
    ["Provider", info.provider],
    ["API base", info.api_base],
    ["Model", info.model],
    ["LLM enabled", String(info.llm_enabled)],
    ["Disable flag", String(info.disable_flag)],
  ];

  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "runtime-row";
    row.innerHTML = `
      <div class="runtime-label">${label}</div>
      <div class="runtime-value">${value ?? "N/A"}</div>
    `;
    runtimeInfo.appendChild(row);
  });
}

function renderTraceList(container, items, emptyText) {
  container.innerHTML = "";
  if (!items || items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "trace-item trace-empty";
    empty.innerHTML = `<div class="trace-detail">${emptyText}</div>`;
    container.appendChild(empty);
    return;
  }

  items.forEach((item, index) => {
    const event = document.createElement("div");
    event.className = "trace-item";
    const statusClass = item.status === "completed" ? "trace-status-ok" : "trace-status-failed";
    const metaJson = item.metadata && Object.keys(item.metadata).length
      ? JSON.stringify(item.metadata, null, 2)
      : "";
    event.innerHTML = `
      <div class="trace-topline">
        <div class="trace-step">${index + 1}. ${item.step}</div>
        <span class="trace-status ${statusClass}">${item.status}</span>
      </div>
      <div class="trace-agent">${item.agent}</div>
      <div class="trace-detail">${item.detail}</div>
      <div class="trace-meta">${item.timestamp}</div>
      ${metaJson ? `<pre class="trace-meta">${metaJson}</pre>` : ""}
    `;
    container.appendChild(event);
  });
}

function renderTraceGroups(payload) {
  traceIdPill.textContent = payload.trace_id ? `Trace: ${payload.trace_id}` : "Trace chua tao";
  renderTraceList(stage4Log, payload.stage4_logs, "Chua co buoc Stage 4 nao.");
  renderTraceList(stage5Log, payload.stage5_logs, "Chua co buoc Stage 5 nao.");
}

function renderStatuses(items) {
  serviceStatus.innerHTML = "";
  const upCount = items.filter((item) => item.healthy).length;
  statusSummary.textContent = `${upCount}/${items.length} services san sang`;

  items.forEach((item) => {
    const wrapper = document.createElement("div");
    wrapper.className = "status-item";

    const detail = document.createElement("div");
    detail.innerHTML = `
      <div class="status-name">${item.name}</div>
      <div class="status-url">${item.url}</div>
      <div class="status-detail">${item.healthy ? `Latency ${item.latency_ms} ms` : (item.detail || "Khong ket noi duoc")}</div>
    `;

    const pill = document.createElement("span");
    pill.className = `status-pill ${item.healthy ? "up" : "down"}`;
    pill.textContent = item.healthy ? "UP" : "DOWN";

    wrapper.appendChild(detail);
    wrapper.appendChild(pill);
    serviceStatus.appendChild(wrapper);
  });
}

async function refreshStatuses() {
  statusSummary.textContent = "Dang kiem tra...";
  try {
    const response = await fetch("/api/status");
    const payload = await response.json();
    renderStatuses(payload);
  } catch (error) {
    statusSummary.textContent = "Khong lay duoc status";
  }
}

async function refreshRuntimeInfo() {
  runtimeSummary.textContent = "Dang tai...";
  try {
    const response = await fetch("/api/runtime");
    const payload = await response.json();
    renderRuntimeInfo(payload);
  } catch (error) {
    runtimeSummary.textContent = "Khong tai duoc runtime";
  }
}

async function submitQuestion(event) {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    return;
  }

  const sessionId = getSessionId();
  addMessage({
    role: "user",
    detail: "Yeu cau gui den customer agent",
    body: question,
  });

  sendButton.disabled = true;
  sendButton.textContent = "Dang xu ly...";
  questionInput.value = "";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Yeu cau that bai");
    }

    setSessionId(payload.session_id);
    renderTraceGroups(payload);
    addMessage({
      role: "assistant",
      detail: `Tra loi tu ${payload.agent_endpoint} trong ${payload.latency_ms} ms · trace ${payload.trace_id}`,
      body: payload.answer,
    });
    await refreshStatuses();
  } catch (error) {
    addMessage({
      role: "assistant",
      detail: "Loi he thong",
      body: error.message || "Khong the lay cau tra loi luc nay.",
    });
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "Gui cau hoi";
    questionInput.focus();
  }
}

function bootstrap() {
  addPromptButtons();
  setSessionId(getSessionId());
  renderTraceGroups({ trace_id: "", stage4_logs: [], stage5_logs: [] });
  addMessage({
    role: "assistant",
    detail: "San sang de test pipeline Day08",
    body: "Hoi bat ky cau hoi phap ly, tin tuc, hoac cau hoi ket hop de kiem tra luong A2A + RAG.",
  });
  refreshStatuses();
  refreshRuntimeInfo();

  chatForm.addEventListener("submit", submitQuestion);
  resetSessionButton.addEventListener("click", resetSession);
  refreshStatusButton.addEventListener("click", refreshStatuses);
}

bootstrap();
