// ============================================================
//  BOT DASHBOARD - app.js (Demo mode - no backend required)
// ============================================================

// --- AI Demo Responses ---
const AI_RESPONSES = {
  aichat: [
    "I am a general AI assistant. I can answer questions, help with writing, brainstorming, or anything else!",
    "That is a great question! In a production setup I would connect to your bot's DeepSeek AI to answer this.",
    "Sure, I can help with that! Once connected to the live bot, this will use your actual AI_API_KEY.",
    "Got it! I am running in demo mode right now, but the real AI chat is powered by DeepSeek.",
    "Interesting! When the backend is live, I will remember our full conversation history too.",
  ],
  aiadmin: [
    "Understood. I will search for that member first using search_members, then take action.",
    "Searching server members... Found target. Applying action now. Audit log entry created.",
    "That member is protected (owner/admin/whitelisted). Action refused.",
    "Done! I have completed the moderation action and logged it to the audit channel.",
    "I can ban, kick, timeout, manage roles and channels, view DM history, and more. What would you like?",
    "Checking member info... id=123456789 | BadUser | bot: false | Joined: 2025-01-10 | Timeout: none",
  ],
  aijuiced: [
    "[CATT]vk: thinking... Assessed the situation. Action queued.",
    "[CATT]vk: Target located. Proceeding with moderation protocol.",
    "[CATT]vk: Refused. That target is protected by system constraints.",
    "[CATT]vk: Task complete. Logged. What is next?",
    "[CATT]vk: Running search_members... got a match. Ready to act on your command.",
  ],
};

let toastTimer = null;

// --- TOAST ---
function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2800);
}

// --- LOGIN ---
document.getElementById("login-btn").addEventListener("click", () => {
  const btn = document.getElementById("login-btn");
  btn.textContent = "Signing in...";
  btn.disabled = true;
  setTimeout(() => {
    document.getElementById("login-screen").style.display = "none";
    document.getElementById("app").classList.remove("hidden");
    showToast("✅ Signed in as DemoUser#0001");
  }, 1000);
});

// --- LOGOUT ---
document.getElementById("logout-btn").addEventListener("click", () => {
  document.getElementById("app").classList.add("hidden");
  document.getElementById("login-screen").style.display = "";
  const btn = document.getElementById("login-btn");
  btn.textContent = "Sign in with Discord";
  btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 71 55" fill="none"><path d="M60.105 4.898A58.55 58.55 0 0 0 45.653.415a.22.22 0 0 0-.232.11 40.784 40.784 0 0 0-1.8 3.697c-5.456-.817-10.886-.817-16.23 0-.485-1.164-1.201-2.587-1.83-3.697a.228.228 0 0 0-.233-.11 58.386 58.386 0 0 0-14.451 4.483.207.207 0 0 0-.095.082C1.578 18.73-.944 32.144.293 45.39a.244.244 0 0 0 .093.167c6.073 4.46 11.956 7.167 17.729 8.962a.23.23 0 0 0 .249-.082 42.08 42.08 0 0 0 3.627-5.9.225.225 0 0 0-.123-.312 38.772 38.772 0 0 1-5.539-2.64.228.228 0 0 1-.022-.378c.372-.279.744-.569 1.1-.862a.22.22 0 0 1 .23-.031c11.62 5.307 24.198 5.307 35.68 0a.219.219 0 0 1 .233.028c.356.293.728.586 1.103.865a.228.228 0 0 1-.02.378 36.384 36.384 0 0 1-5.54 2.637.225.225 0 0 0-.12.315 47.249 47.249 0 0 0 3.623 5.897.226.226 0 0 0 .249.084c5.799-1.795 11.683-4.502 17.757-8.962a.228.228 0 0 0 .092-.164c1.48-15.315-2.48-28.618-10.497-40.412a.18.18 0 0 0-.093-.084Z" fill="white"/></svg> Sign in with Discord`;
  btn.disabled = false;
  showToast("Logged out");
});

// --- NAV ---
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

// --- MOD ACTION ---
function modAction(action) {
  const target = document.getElementById("mod-target").value.trim();
  if (!target) { showToast("⚠️ Enter a target member first"); return; }
  const reason = document.getElementById("mod-reason").value.trim() || "No reason given";
  const timeoutMin = document.getElementById("mod-timeout").value;
  const purgeCount = document.getElementById("mod-purge").value;
  const msgs = {
    Ban:     `🔨 Banned ${target} — ${reason}`,
    Kick:    `👢 Kicked ${target} — ${reason}`,
    Timeout: `🔇 Timed out ${target} for ${timeoutMin}min — ${reason}`,
    Unban:   `🔓 Unbanned ${target}`,
    Purge:   `🗑️ Purged ${purgeCount} messages`,
  };
  showToast("✅ " + (msgs[action] || action + " done"));
}

// --- WHITELIST ADD ---
function addWL(listId, inputId, icon) {
  const input = document.getElementById(inputId);
  const val = input.value.trim();
  if (!val) { showToast("⚠️ Enter a value first"); return; }
  const list = document.getElementById(listId);
  const row = document.createElement("div");
  row.className = "member-row";
  row.innerHTML = `<span>${icon} ${val}</span><button class="btn-xs btn-red" onclick="this.closest('.member-row').remove(); showToast('Removed!')">Remove</button>`;
  list.appendChild(row);
  input.value = "";
  showToast("✅ Added!");
}

// --- AUTO-RESPONSE ADD ---
function addAR() {
  const trig = document.getElementById("ar-trig").value.trim();
  const rep  = document.getElementById("ar-rep").value.trim();
  if (!trig || !rep) { showToast("⚠️ Fill in both fields"); return; }
  const list = document.getElementById("ar-list");
  const row = document.createElement("div");
  row.className = "ar-row";
  row.innerHTML = `<span class="ar-trigger">${trig}</span><span class="ar-sep">→</span><span class="ar-reply">${rep}</span><button class="btn-xs btn-red" onclick="this.closest('.ar-row').remove(); showToast('Removed!')">✕</button>`;
  list.appendChild(row);
  document.getElementById("ar-trig").value = "";
  document.getElementById("ar-rep").value = "";
  showToast("✅ Auto-response added!");
}

// --- AI CHAT ---
function sendChat(type) {
  const input = document.getElementById("in-" + type);
  const log   = document.getElementById("log-" + type);
  const msg   = input.value.trim();
  if (!msg) return;
  input.value = "";

  // User message
  const userEl = document.createElement("div");
  userEl.className = "msg user";
  userEl.textContent = msg;
  log.appendChild(userEl);

  // Thinking indicator
  const thinkEl = document.createElement("div");
  thinkEl.className = "msg thinking";
  thinkEl.textContent = "Thinking...";
  log.appendChild(thinkEl);
  log.scrollTop = log.scrollHeight;

  // Simulated response
  const pool = AI_RESPONSES[type] || AI_RESPONSES.aichat;
  const reply = pool[Math.floor(Math.random() * pool.length)];
  const delay = 600 + Math.random() * 900;

  setTimeout(() => {
    log.removeChild(thinkEl);
    const botEl = document.createElement("div");
    botEl.className = "msg bot";
    botEl.textContent = reply;
    log.appendChild(botEl);
    log.scrollTop = log.scrollHeight;
  }, delay);
}
