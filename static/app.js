const state = {
  token: localStorage.getItem("coachspace_token"),
  user: JSON.parse(localStorage.getItem("coachspace_user") || "null"),
  view: "library",
  mediaType: "",
  activePeerId: null,
  users: [],
  bookings: [],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function showToast(message, isError = false) {
  const toast = $("#toast") || $("#authError");
  toast.textContent = message;
  toast.style.background = isError ? "#7a1d16" : "";
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3000);
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }

  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(data?.detail || "Request failed");
  }
  return data;
}

function formDataObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function saveAuth(payload) {
  state.token = payload.token;
  state.user = payload.user;
  localStorage.setItem("coachspace_token", payload.token);
  localStorage.setItem("coachspace_user", JSON.stringify(payload.user));
}

function clearAuth() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("coachspace_token");
  localStorage.removeItem("coachspace_user");
}

function setAuthMode(mode) {
  const loginMode = mode === "login";
  $("#loginForm").classList.toggle("hidden", !loginMode);
  $("#registerForm").classList.toggle("hidden", loginMode);
  $("#loginTab").classList.toggle("active", loginMode);
  $("#registerTab").classList.toggle("active", !loginMode);
  $("#authError").textContent = "";
}

function renderShell() {
  const loggedIn = Boolean(state.token && state.user);
  $("#authView").classList.toggle("hidden", loggedIn);
  $("#appView").classList.toggle("hidden", !loggedIn);
  if (!loggedIn) return;

  $("#userName").textContent = state.user.name;
  $("#userRole").textContent = state.user.role;
  $("#uploadForm").classList.toggle("hidden", state.user.role !== "teacher");
  $("#sessionForm").classList.toggle("hidden", state.user.role !== "teacher");
  setView(state.view);
}

function setView(view) {
  state.view = view;
  $$(".nav button").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  $$(".view").forEach((section) => section.classList.add("hidden"));
  $(`#${view}View`).classList.remove("hidden");

  const labels = {
    library: ["Learning Library", "Courses and Resources"],
    sessions: ["Live Sessions", "Book and Join Classes"],
    messages: ["Messages", "In-App Communication"],
  };
  $("#sectionKicker").textContent = labels[view][0];
  $("#sectionTitle").textContent = labels[view][1];
  refreshCurrentView();
}

async function refreshCurrentView() {
  if (!state.token) return;
  try {
    if (state.view === "library") await loadMedia();
    if (state.view === "sessions") {
      await loadBookings();
      await loadSessions();
    }
    if (state.view === "messages") await loadMessaging();
  } catch (error) {
    showToast(error.message, true);
  }
}

function mediaPlayer(item) {
  if (item.media_type === "video") {
    return `<video controls src="${item.url}"></video>`;
  }
  if (item.media_type === "audio") {
    return `<audio controls src="${item.url}"></audio>`;
  }
  return `<iframe title="${escapeHtml(item.title)}" src="${item.url}"></iframe>`;
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

async function uploadLearningMaterial(form) {
  const formData = new FormData(form);
  const file = formData.get("file");
  const payload = {
    title: formData.get("title"),
    description: formData.get("description") || "",
    media_type: formData.get("media_type"),
    file_name: file.name,
    content_type: file.type || "",
    size_bytes: file.size,
  };

  const presign = await api("/api/media/presign", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (presign.storage_backend !== "s3") {
    await api("/api/media", { method: "POST", body: formData });
    return;
  }

  const s3FormData = new FormData();
  Object.entries(presign.fields).forEach(([key, value]) => s3FormData.append(key, value));
  s3FormData.append("file", file);

  const uploadResponse = await fetch(presign.url, {
    method: "POST",
    body: s3FormData,
  });
  if (!uploadResponse.ok) {
    throw new Error("Upload to S3 failed");
  }

  await api("/api/media/complete", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      content_type: presign.content_type,
      storage_key: presign.storage_key,
    }),
  });
}

async function loadMedia() {
  const query = state.mediaType ? `?media_type=${state.mediaType}` : "";
  const items = await api(`/api/media${query}`);
  $("#mediaList").innerHTML = items.length ? items.map((item) => `
    <article class="media-item">
      ${mediaPlayer(item)}
      <div class="media-body">
        <div>
          <h3>${escapeHtml(item.title)}</h3>
          <p class="meta">${item.media_type.toUpperCase()} by ${escapeHtml(item.teacher_name)}</p>
        </div>
        <p>${escapeHtml(item.description || "No description added.")}</p>
        <div class="comment-list" id="comments-${item.id}"></div>
        <form class="comment-form" data-media-id="${item.id}">
          <label>Comment<input required name="body" placeholder="Ask a question or add a note" /></label>
          <button class="secondary" type="submit">Post Comment</button>
        </form>
      </div>
    </article>
  `).join("") : `<p class="meta">No learning material has been uploaded yet.</p>`;

  await Promise.all(items.map((item) => loadComments(item.id)));
}

async function loadComments(mediaId) {
  const comments = await api(`/api/media/${mediaId}/comments`);
  const target = $(`#comments-${mediaId}`);
  if (!target) return;
  target.innerHTML = comments.length ? comments.map((comment) => `
    <div class="comment">
      <strong>${escapeHtml(comment.user_name)} <span class="meta">${escapeHtml(comment.user_role)}</span></strong>
      <p>${escapeHtml(comment.body)}</p>
    </div>
  `).join("") : `<p class="meta">No comments yet.</p>`;
}

async function loadSessions() {
  const sessions = await api("/api/live-sessions");
  $("#sessionList").innerHTML = sessions.length ? sessions.map((session) => {
    const isTeacherOwner = state.user.role === "teacher" && session.teacher_id === state.user.id;
    const isBooked = session.is_booked || state.bookings.some((booking) => booking.session_id === session.id);
    const canBook = state.user.role === "student" && !isBooked && session.booked_count < session.capacity;
    const joinVisible = isTeacherOwner || isBooked;
    return `
      <article class="session-item">
        <div>
          <h3>${escapeHtml(session.title)}</h3>
          <p class="meta">${new Date(session.starts_at).toLocaleString()} · ${session.duration_minutes} min · ${session.booked_count}/${session.capacity} booked</p>
          <p class="meta">Teacher: ${escapeHtml(session.teacher_name)}</p>
        </div>
        <p>${escapeHtml(session.description || "No description added.")}</p>
        <div class="session-actions">
          ${canBook ? `<button class="primary book-btn" data-session-id="${session.id}" type="button">Book Session</button>` : ""}
          ${isBooked ? `<span class="role-pill">Booked</span>` : ""}
          ${joinVisible && session.meeting_url ? `<a class="secondary as-link" href="${session.meeting_url}" target="_blank" rel="noreferrer">Join Live</a>` : ""}
        </div>
      </article>
    `;
  }).join("") : `<p class="meta">No live sessions are scheduled yet.</p>`;
}

async function loadBookings() {
  state.bookings = await api("/api/bookings");
  $("#bookingList").innerHTML = state.bookings.length ? state.bookings.map((booking) => `
    <article class="booking-item">
      <strong>${escapeHtml(booking.session_title)}</strong>
      <span class="meta">${new Date(booking.starts_at).toLocaleString()} · ${escapeHtml(booking.student_name || booking.teacher_name || "")}</span>
      <a class="secondary as-link" href="${booking.meeting_url}" target="_blank" rel="noreferrer">Join Live</a>
    </article>
  `).join("") : `<p class="meta">No bookings yet.</p>`;
}

async function loadMessaging() {
  const role = state.user.role === "teacher" ? "student" : "teacher";
  state.users = await api(`/api/users?role=${role}`);
  $("#recipientSelect").innerHTML = state.users.length ? state.users.map((user) => (
    `<option value="${user.id}">${escapeHtml(user.name)} (${user.role})</option>`
  )).join("") : `<option value="">No users available</option>`;

  const conversations = await api("/api/conversations");
  $("#conversationList").innerHTML = conversations.length ? conversations.map((conversation) => `
    <button type="button" data-peer-id="${conversation.peer_id}">
      ${escapeHtml(conversation.peer_name)}
      <span class="meta">${new Date(conversation.last_at).toLocaleString()}</span>
    </button>
  `).join("") : `<p class="meta">No conversations yet.</p>`;

  if (state.activePeerId) {
    await loadConversation(state.activePeerId);
  }
}

async function loadConversation(peerId) {
  state.activePeerId = Number(peerId);
  const peer = state.users.find((user) => user.id === state.activePeerId);
  $("#chatHeader").textContent = peer ? peer.name : "Conversation";
  const messages = await api(`/api/messages?with_user_id=${state.activePeerId}`);
  $("#messageList").innerHTML = messages.length ? messages.map((message) => `
    <div class="message ${message.sender_id === state.user.id ? "mine" : ""}">
      <strong>${escapeHtml(message.sender_name)}</strong>
      <p>${escapeHtml(message.body)}</p>
      <span class="meta">${new Date(message.created_at).toLocaleString()}</span>
    </div>
  `).join("") : `<p class="meta">No messages yet.</p>`;
  $("#messageList").scrollTop = $("#messageList").scrollHeight;
}

$("#loginTab").addEventListener("click", () => setAuthMode("login"));
$("#registerTab").addEventListener("click", () => setAuthMode("register"));

$("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    saveAuth(await api("/api/auth/login", { method: "POST", body: JSON.stringify(formDataObject(event.target)) }));
    renderShell();
    await refreshCurrentView();
  } catch (error) {
    $("#authError").textContent = error.message;
  }
});

$("#registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    saveAuth(await api("/api/auth/register", { method: "POST", body: JSON.stringify(formDataObject(event.target)) }));
    renderShell();
    await refreshCurrentView();
  } catch (error) {
    $("#authError").textContent = error.message;
  }
});

$("#logoutBtn").addEventListener("click", () => {
  clearAuth();
  renderShell();
});

$(".nav").addEventListener("click", (event) => {
  if (event.target.matches("button[data-view]")) setView(event.target.dataset.view);
});

$("#refreshBtn").addEventListener("click", refreshCurrentView);

$("#mediaFilters").addEventListener("click", (event) => {
  if (!event.target.matches("button")) return;
  state.mediaType = event.target.dataset.type;
  $$("#mediaFilters button").forEach((button) => button.classList.toggle("active", button === event.target));
  loadMedia().catch((error) => showToast(error.message, true));
});

$("#uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await uploadLearningMaterial(event.target);
    event.target.reset();
    showToast("Material uploaded");
    await loadMedia();
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#mediaList").addEventListener("submit", async (event) => {
  if (!event.target.matches(".comment-form")) return;
  event.preventDefault();
  const mediaId = event.target.dataset.mediaId;
  try {
    await api(`/api/media/${mediaId}/comments`, {
      method: "POST",
      body: JSON.stringify(formDataObject(event.target)),
    });
    event.target.reset();
    await loadComments(mediaId);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#sessionForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = formDataObject(event.target);
  data.duration_minutes = Number(data.duration_minutes);
  data.capacity = Number(data.capacity);
  data.starts_at = new Date(data.starts_at).toISOString();
  if (!data.meeting_url) delete data.meeting_url;
  try {
    await api("/api/live-sessions", { method: "POST", body: JSON.stringify(data) });
    event.target.reset();
    showToast("Session scheduled");
    await loadBookings();
    await loadSessions();
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#sessionList").addEventListener("click", async (event) => {
  if (!event.target.matches(".book-btn")) return;
  try {
    await api(`/api/live-sessions/${event.target.dataset.sessionId}/book`, { method: "POST" });
    showToast("Session booked");
    await loadBookings();
    await loadSessions();
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#loadConversationBtn").addEventListener("click", () => {
  const peerId = $("#recipientSelect").value;
  if (peerId) loadConversation(peerId).catch((error) => showToast(error.message, true));
});

$("#conversationList").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-peer-id]");
  if (button) loadConversation(button.dataset.peerId).catch((error) => showToast(error.message, true));
});

$("#messageForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.activePeerId) {
    showToast("Choose a person first", true);
    return;
  }
  const data = formDataObject(event.target);
  if (!data.body.trim()) return;
  try {
    await api("/api/messages", {
      method: "POST",
      body: JSON.stringify({ recipient_id: state.activePeerId, body: data.body }),
    });
    event.target.reset();
    await loadConversation(state.activePeerId);
    await loadMessaging();
  } catch (error) {
    showToast(error.message, true);
  }
});

renderShell();
if (state.token) {
  api("/api/me")
    .then((user) => {
      state.user = user;
      localStorage.setItem("coachspace_user", JSON.stringify(user));
      renderShell();
      return refreshCurrentView();
    })
    .catch(() => {
      clearAuth();
      renderShell();
    });
}
