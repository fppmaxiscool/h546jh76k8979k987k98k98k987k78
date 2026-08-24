// ============================================================
//  BOT DASHBOARD - Full Live API
// ============================================================

let currentGuildId = null;
let toastTimer = null;

function showToast(msg, isError = false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.background = isError ? "#e74c3c" : "#23272a";
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3000);
}

async function apiFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  if (res.status === 401) { window.location.reload(); return null; }
  return res;
}

// ── INIT ─────────────────────────────────────
async function initDashboard(guildId = null) {
  const url = guildId ? `/api/status?guild_id=${guildId}` : "/api/status";
  const res = await apiFetch(url);
  if (!res) return;

  if (res.status === 401) {
    document.getElementById("login-screen").style.display = "";
    document.getElementById("app").classList.add("hidden");
    return;
  }

  const data = await res.json();
  if (data.error) { showToast(data.error, true); return; }

  document.getElementById("login-screen").style.display = "none";
  document.getElementById("app").classList.remove("hidden");
  document.querySelector(".user-name").textContent = data.user.username;

  currentGuildId = data.guild.id;

  // Guild selector
  const sel = document.getElementById("guild-selector");
  sel.innerHTML = "";
  data.shared_guilds.forEach(g => {
    const opt = document.createElement("option");
    opt.value = g.id; opt.textContent = g.name;
    if (g.id === currentGuildId) opt.selected = true;
    sel.appendChild(opt);
  });

  // Stats
  const stats = document.querySelectorAll(".stat-value");
  if (stats[0]) stats[0].textContent = data.guild.member_count;
  if (stats[1]) stats[1].textContent = data.stats.total_messages || 0;

  // Audit log
  const logList = document.querySelector(".log-list");
  if (logList) {
    logList.innerHTML = "";
    if (!data.audit_log || data.audit_log.length === 0) {
      logList.innerHTML = "<div class='log-row'><span>No audit log entries yet.</span></div>";
    } else {
      data.audit_log.forEach(e => {
        const row = document.createElement("div"); row.className = "log-row";
        row.innerHTML = `<span class="log-time">${e.time}</span><span><b>${e.actor}</b>: ${e.action} → ${e.target}</span>`;
        logList.appendChild(row);
      });
    }
  }

  // Toggles
  const s = data.settings;
  ["spam_detection","antilink","badwords_filter","antibot","channel_raid_protection","raid_auto_unlock","raid_ban_new_accounts"].forEach(k => {
    const el = document.getElementById("tgl-" + k);
    if (el) el.checked = !!s[k];
  });

  // Thresholds
  ["spam_count","spam_window","spam_mute_minutes","spam_ban_offenses","raid_slowmode","room_inactive_days"].forEach(k => {
    const el = document.getElementById("inp-" + k);
    if (el) el.value = s[k];
  });

  // Owner-only tabs
  if (data.user.is_owner) {
    const navLogs = document.getElementById("nav-logs");
    if (navLogs) navLogs.style.display = "flex";
    loadLogs();
  }

  // Load live data for other pages
  loadTimedOut();
  loadWhitelist();
  loadAutoResponses();
  loadTickets();
}

// ── GUILD SELECTOR ──────────────────────────
document.getElementById("guild-selector").addEventListener("change", e => {
  initDashboard(e.target.value);
});

// ── TOGGLES ─────────────────────────────────
document.querySelectorAll('.toggle input[type="checkbox"]').forEach(el => {
  el.addEventListener("change", async e => {
    const key = e.target.id.replace("tgl-", "");
    const val = e.target.checked;
    const res = await apiFetch("/api/action", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action: "toggle_setting", key, value: val, guild_id: currentGuildId})
    });
    if (res) showToast(val ? `✅ ${key} enabled` : `❌ ${key} disabled`);
  });
});

// ── THRESHOLDS ───────────────────────────────
document.querySelector("#page-protection .btn-primary") && (document.querySelector("#page-protection .btn-primary").onclick = async () => {
  const payload = {action: "update_thresholds", guild_id: currentGuildId};
  ["spam_count","spam_window","spam_mute_minutes","spam_ban_offenses","raid_slowmode","room_inactive_days"].forEach(k => {
    const el = document.getElementById("inp-" + k);
    if (el) payload[k] = el.value;
  });
  const res = await apiFetch("/api/action", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  if (res) showToast("✅ Thresholds saved!");
});

// ── TIMED OUT ────────────────────────────────
async function loadTimedOut() {
  const res = await apiFetch(`/api/timed_out?guild_id=${currentGuildId}`);
  if (!res) return;
  const data = await res.json();
  document.querySelectorAll(".card-title").forEach(title => {
    if (title.textContent.trim() === "Currently Timed Out") {
      const list = title.nextElementSibling;
      if (!list) return;
      list.innerHTML = "";
      if (!data.members || data.members.length === 0) {
        list.innerHTML = "<div class='member-row'><span>No users timed out.</span></div>"; return;
      }
      data.members.forEach(m => {
        const row = document.createElement("div"); row.className = "member-row";
        row.innerHTML = `<span>🔇 <b>${m.name}</b> <span class="muted">(${m.id})</span></span><span class="muted">until ${m.until}</span>`;
        list.appendChild(row);
      });
    }
  });
}

// ── MODERATION ───────────────────────────────
window.modAction = async function(action) {
  const target = document.getElementById("mod-target").value.trim();
  const reason = document.getElementById("mod-reason").value.trim() || "Dashboard action";
  if (!target) { showToast("⚠️ Enter a target member", true); return; }
  const payload = {action, target, reason, guild_id: currentGuildId};
  if (action === "timeout") payload.minutes = parseInt(document.getElementById("mod-timeout").value) || 10;
  if (action === "purge") payload.count = parseInt(document.getElementById("mod-purge").value) || 10;
  const res = await apiFetch("/api/moderation", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  if (!res) return;
  const data = await res.json();
  if (data.error) showToast("❌ " + data.error, true);
  else { showToast("✅ " + data.message); loadTimedOut(); }
};

// ── WHITELIST ────────────────────────────────
async function loadWhitelist() {
  const res = await apiFetch(`/api/whitelist?guild_id=${currentGuildId}`);
  if (!res) return;
  const data = await res.json();
  renderList("wl-users", data.users || [], i => `<span>👤 <b>${i.name}</b> <span class="muted">(${i.id})</span></span>`, i => removeWL("remove_user", i.id));
  renderList("wl-roles", data.roles || [], i => `<span>🎭 <b>${i.name}</b> <span class="muted">(${i.id})</span></span>`, i => removeWL("remove_role", i.id));
  renderList("wl-links", data.links || [], i => `<span>🔗 ${i.domain}</span>`, i => removeWL("remove_link", i.domain));
}

function renderList(id, items, labelFn, removeFn) {
  const el = document.getElementById(id); if (!el) return;
  el.innerHTML = "";
  if (items.length === 0) { el.innerHTML = "<div class='member-row'><span class='muted'>None yet.</span></div>"; return; }
  items.forEach(item => {
    const row = document.createElement("div"); row.className = "member-row";
    const btn = document.createElement("button"); btn.className = "btn-xs btn-red"; btn.textContent = "Remove";
    btn.onclick = () => removeFn(item);
    row.innerHTML = labelFn(item); row.appendChild(btn);
    el.appendChild(row);
  });
}

async function removeWL(action, value) {
  const res = await apiFetch("/api/whitelist", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,value:String(value),guild_id:currentGuildId})});
  if (res) { showToast("✅ Removed!"); loadWhitelist(); }
}

window.addWLUser = async function() {
  const val = document.getElementById("wl-user-in").value.trim();
  if (!val) return;
  const res = await apiFetch("/api/whitelist", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"add_user",value:val,guild_id:currentGuildId})});
  if (!res) return;
  const data = await res.json();
  if (data.error) showToast("❌ " + data.error, true);
  else { document.getElementById("wl-user-in").value = ""; showToast("✅ User added!"); loadWhitelist(); }
};

window.addWLRole = async function() {
  const val = document.getElementById("wl-role-in").value.trim();
  if (!val) return;
  const res = await apiFetch("/api/whitelist", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"add_role",value:val,guild_id:currentGuildId})});
  if (!res) return;
  const data = await res.json();
  if (data.error) showToast("❌ " + data.error, true);
  else { document.getElementById("wl-role-in").value = ""; showToast("✅ Role added!"); loadWhitelist(); }
};

window.addWLLink = async function() {
  const val = document.getElementById("wl-link-in").value.trim();
  if (!val) return;
  const res = await apiFetch("/api/whitelist", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"add_link",value:val,guild_id:currentGuildId})});
  if (!res) return;
  const data = await res.json();
  if (data.error) showToast("❌ " + data.error, true);
  else { document.getElementById("wl-link-in").value = ""; showToast("✅ Link added!"); loadWhitelist(); }
};

// ── AUTO RESPONSES ───────────────────────────
async function loadAutoResponses() {
  const res = await apiFetch(`/api/autoresponse?guild_id=${currentGuildId}`);
  if (!res) return;
  const data = await res.json();
  const list = document.getElementById("ar-list"); if (!list) return;
  list.innerHTML = "";
  if (!data.items || data.items.length === 0) { list.innerHTML = "<div class='ar-row'><span class='muted'>No auto-responses set.</span></div>"; return; }
  data.items.forEach(item => {
    const row = document.createElement("div"); row.className = "ar-row";
    const btn = document.createElement("button"); btn.className = "btn-xs btn-red"; btn.textContent = "✕";
    btn.onclick = async () => {
      await apiFetch("/api/autoresponse", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"remove",trigger:item.trigger,guild_id:currentGuildId})});
      showToast("✅ Removed!"); loadAutoResponses();
    };
    row.innerHTML = `<span class="ar-trigger">${item.trigger}</span><span class="ar-sep">→</span><span class="ar-reply">${item.response}</span>`;
    row.appendChild(btn); list.appendChild(row);
  });
}

window.addAutoResponse = async function() {
  const trig = document.getElementById("ar-trig").value.trim();
  const rep = document.getElementById("ar-rep").value.trim();
  if (!trig || !rep) { showToast("⚠️ Enter both trigger and response", true); return; }
  const res = await apiFetch("/api/autoresponse", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"add",trigger:trig,response:rep,guild_id:currentGuildId})});
  if (!res) return;
  const data = await res.json();
  if (data.error) showToast("❌ " + data.error, true);
  else { document.getElementById("ar-trig").value = ""; document.getElementById("ar-rep").value = ""; showToast("✅ Added!"); loadAutoResponses(); }
};

// ── TICKETS ──────────────────────────────────
async function loadTickets() {
  const res = await apiFetch(`/api/tickets?guild_id=${currentGuildId}`);
  if (!res) return;
  const data = await res.json();
  document.querySelectorAll(".card-title").forEach(title => {
    if (title.textContent.trim() === "Open Tickets") {
      const list = title.nextElementSibling; if (!list) return;
      list.innerHTML = "";
      if (!data.tickets || data.tickets.length === 0) { list.innerHTML = "<div class='member-row'><span>No open tickets.</span></div>"; return; }
      data.tickets.forEach(t => {
        const row = document.createElement("div"); row.className = "member-row";
        row.innerHTML = `<span>🎫 <b>${t.name}</b></span><span class="muted">${t.opener}</span>`;
        const btn = document.createElement("a"); btn.className = "btn-xs"; btn.textContent = "View"; btn.href = t.url; btn.target = "_blank";
        row.appendChild(btn); list.appendChild(row);
      });
    }
  });
}

// ── AI CHAT ──────────────────────────────────
window.sendChat = async function(type) {
  const input = document.getElementById("in-" + type);
  const log = document.getElementById("log-" + type);
  const msg = input.value.trim(); if (!msg) return;
  input.value = "";
  const userEl = document.createElement("div"); userEl.className = "msg user"; userEl.textContent = msg; log.appendChild(userEl);
  const thinkEl = document.createElement("div"); thinkEl.className = "msg thinking"; thinkEl.textContent = "Thinking..."; log.appendChild(thinkEl);
  log.scrollTop = log.scrollHeight;
  try {
    const res = await apiFetch("/api/action", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"ai_chat",type,message:msg,guild_id:currentGuildId})});
    log.removeChild(thinkEl);
    if (!res) return;
    const data = await res.json();
    const botEl = document.createElement("div"); botEl.className = "msg bot"; botEl.textContent = data.reply || "No response."; log.appendChild(botEl);
  } catch(e) { try { log.removeChild(thinkEl); } catch(_) {} showToast("Error connecting to AI", true); }
  log.scrollTop = log.scrollHeight;
};

// ── OWNER LOGS ───────────────────────────────
async function loadLogs() {
  const res = await apiFetch("/api/logs");
  if (!res) return;
  const data = await res.json();
  const container = document.getElementById("web-logs-container"); if (!container) return;
  container.innerHTML = "";
  if (!data.logs || data.logs.length === 0) { container.innerHTML = "<div class='log-row'><span>No activity yet.</span></div>"; return; }
  data.logs.forEach(l => {
    const row = document.createElement("div"); row.className = "log-row";
    row.innerHTML = `<span class="log-time">${l.time}</span><span>👤 <b>${l.username}</b>: ${l.action}</span>`;
    container.appendChild(row);
  });
}

// ── LOGIN / LOGOUT / NAV ─────────────────────
document.getElementById("login-btn").addEventListener("click", () => { window.location.href = "/login"; });
document.getElementById("logout-btn").addEventListener("click", () => {
  document.cookie = "dash_session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
  window.location.reload();
});

document.querySelectorAll(".nav-item[data-page]").forEach(link => {
  link.addEventListener("click", e => {
    e.preventDefault();
    document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    link.classList.add("active");
    const page = document.getElementById("page-" + link.dataset.page);
    if (page) page.classList.add("active");
  });
});

// ── BOOT ─────────────────────────────────────
initDashboard();
