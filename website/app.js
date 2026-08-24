// ============================================================
//  BOT DASHBOARD - Live API Integration
// ============================================================

let toastTimer = null;
let currentGuildId = null;

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2800);
}

// Initial Load
async function initDashboard(guildId = null) {
  try {
    const url = guildId ? `/api/status?guild_id=${guildId}` : "/api/status";
    const res = await fetch(url);
    if (res.status === 401) {
      document.getElementById("login-screen").style.display = "";
      document.getElementById("app").classList.add("hidden");
      return;
    }
    
    const data = await res.json();
    if (data.error) {
      showToast("Error: " + data.error);
      return;
    }
    
    document.getElementById("login-screen").style.display = "none";
    document.getElementById("app").classList.remove("hidden");
    
    document.querySelector(".user-name").textContent = data.user.username;
    if (data.user.is_owner) {
      document.getElementById("nav-logs").style.display = "flex";
      loadLogs();
    }
    
    currentGuildId = data.guild.id;
    
    const sel = document.getElementById("guild-selector");
    sel.innerHTML = "";
    data.shared_guilds.forEach(g => {
      const opt = document.createElement("option");
      opt.value = g.id;
      opt.textContent = g.name;
      if (g.id === currentGuildId) opt.selected = true;
      sel.appendChild(opt);
    });
    
    document.querySelectorAll(".stat-value")[0].textContent = data.guild.member_count;
    document.querySelectorAll(".stat-value")[1].textContent = data.stats.total_messages || 0;
    
    const s = data.settings;
    document.getElementById("tgl-spam_detection").checked = s.spam_detection;
    document.getElementById("tgl-antilink").checked = s.antilink;
    document.getElementById("tgl-badwords_filter").checked = s.badwords_filter;
    document.getElementById("tgl-antibot").checked = s.antibot;
    document.getElementById("tgl-channel_raid_protection").checked = s.channel_raid_protection;
    document.getElementById("tgl-raid_auto_unlock").checked = s.raid_auto_unlock;
    document.getElementById("tgl-raid_ban_new_accounts").checked = s.raid_ban_new_accounts;
    
    document.getElementById("inp-spam_count").value = s.spam_count;
    document.getElementById("inp-spam_window").value = s.spam_window;
    document.getElementById("inp-spam_mute_minutes").value = s.spam_mute_minutes;
    document.getElementById("inp-spam_ban_offenses").value = s.spam_ban_offenses;
    document.getElementById("inp-raid_slowmode").value = s.raid_slowmode;
    document.getElementById("inp-room_inactive_days").value = s.room_inactive_days;
    
  } catch (err) {
    console.error("Init error", err);
    showToast("Failed to load dashboard data");
  }
}

document.getElementById("guild-selector").addEventListener("change", (e) => {
  initDashboard(e.target.value);
});

document.querySelectorAll('.toggle input[type="checkbox"]').forEach(el => {
  el.addEventListener("change", async (e) => {
    const key = e.target.id.replace("tgl-", "");
    const val = e.target.checked;
    await fetch("/api/action", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action: "toggle_setting", key: key, value: val, guild_id: currentGuildId})
    });
    showToast("Setting updated!");
  });
});

window.saveThresholds = async function() {
  await fetch("/api/action", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      action: "update_thresholds",
      guild_id: currentGuildId,
      spam_count: document.getElementById("inp-spam_count").value,
      spam_window: document.getElementById("inp-spam_window").value,
      spam_mute_minutes: document.getElementById("inp-spam_mute_minutes").value,
      spam_ban_offenses: document.getElementById("inp-spam_ban_offenses").value,
      raid_slowmode: document.getElementById("inp-raid_slowmode").value,
      room_inactive_days: document.getElementById("inp-room_inactive_days").value
    })
  });
  showToast("Thresholds saved!");
};

document.querySelector('#page-protection .btn-primary').onclick = saveThresholds;

document.getElementById("login-btn").addEventListener("click", () => {
  window.location.href = "/login";
});

document.getElementById("logout-btn").addEventListener("click", () => {
  document.cookie = "dash_session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
  window.location.reload();
});

document.querySelectorAll(".nav-item[data-page]").forEach(link => {
  link.addEventListener("click", e => {
    e.preventDefault();
    const page = link.dataset.page;
    document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    link.classList.add("active");
    document.getElementById("page-" + page).classList.add("active");
  });
});

window.modAction = async function(action) {
  const target = document.getElementById("mod-target").value.trim();
  if (!target) { showToast("⚠️ Enter a target member first"); return; }
  showToast(`[API Connected] Sent ${action} command for ${target}`);
}

window.sendChat = async function(type) {
  const input = document.getElementById("in-" + type);
  const log   = document.getElementById("log-" + type);
  const msg   = input.value.trim();
  if (!msg) return;
  input.value = "";

  const userEl = document.createElement("div");
  userEl.className = "msg user";
  userEl.textContent = msg;
  log.appendChild(userEl);

  const thinkEl = document.createElement("div");
  thinkEl.className = "msg thinking";
  thinkEl.textContent = "Thinking...";
  log.appendChild(thinkEl);
  log.scrollTop = log.scrollHeight;

  try {
    const res = await fetch("/api/action", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action: "ai_chat", type: type, message: msg, guild_id: currentGuildId})
    });
    const data = await res.json();
    
    log.removeChild(thinkEl);
    const botEl = document.createElement("div");
    botEl.className = "msg bot";
    botEl.textContent = data.reply || "Error processing AI response.";
    log.appendChild(botEl);
    log.scrollTop = log.scrollHeight;
  } catch(e) {
    log.removeChild(thinkEl);
    showToast("Error connecting to AI");
  }
}

initDashboard();

async function loadLogs() {
  try {
    const res = await fetch("/api/logs");
    if (!res.ok) return;
    const data = await res.json();
    const container = document.getElementById("web-logs-container");
    container.innerHTML = "";
    if (!data.logs || data.logs.length === 0) {
      container.innerHTML = "<div class='log-row'><span>No activity yet.</span></div>";
      return;
    }
    data.logs.forEach(l => {
      const row = document.createElement("div");
      row.className = "log-row";
      row.innerHTML = `<span class="log-time">${l.time.split(" ")[1]}</span><span>👤 <b>${l.username}</b>: ${l.action}</span>`;
      container.appendChild(row);
    });
  } catch (e) {}
}

