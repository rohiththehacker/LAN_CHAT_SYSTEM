/**
 * LAN Chat System - Admin Portal Controller
 * Manages admin authentication, real-time client monitoring, user kicking, and inactivity settings.
 */

let adminKey = null;
let pollInterval = null;

// DOM Elements
const adminLoginModal = document.getElementById("admin-login-modal");
const adminLoginForm = document.getElementById("admin-login-form");
const inputAdminKey = document.getElementById("input-admin-key");
const adminModalError = document.getElementById("admin-modal-error");

const kpiActiveClients = document.getElementById("kpi-active-clients");
const kpiRoutedMsgs = document.getElementById("kpi-routed-msgs");
const kpiServerUptime = document.getElementById("kpi-server-uptime");
const kpiTimeoutVal = document.getElementById("kpi-timeout-val");

const broadcastForm = document.getElementById("broadcast-form");
const inputBroadcastMsg = document.getElementById("input-broadcast-msg");
const broadcastFeedback = document.getElementById("broadcast-feedback");

const timeoutConfigForm = document.getElementById("timeout-config-form");
const selectTimeout = document.getElementById("select-timeout");
const timeoutFeedback = document.getElementById("timeout-feedback");

const clientsTableBody = document.getElementById("clients-table-body");
const tableUserCount = document.getElementById("table-user-count");
const btnAdminRefresh = document.getElementById("btn-admin-refresh");
const btnAdminLogout = document.getElementById("btn-admin-logout");

// On Page Load: Check stored admin key or request login
window.addEventListener("DOMContentLoaded", () => {
    const savedKey = sessionStorage.getItem("lan_admin_key");
    if (savedKey) {
        verifyAdminKey(savedKey);
    }
});

// Login Form Submit Handler
adminLoginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    adminModalError.classList.add("hidden");
    const key = inputAdminKey.value.trim();
    if (!key) return;

    verifyAdminKey(key);
});

async function verifyAdminKey(key) {
    try {
        const res = await fetch("/api/admin/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ admin_key: key })
        });
        const data = await res.json();
        if (data.status === "ok") {
            adminKey = key;
            sessionStorage.setItem("lan_admin_key", key);
            adminLoginModal.classList.add("hidden");
            startAdminPolling();
        } else {
            showAdminModalError(data.message || "Invalid Admin Key");
        }
    } catch (err) {
        showAdminModalError("Network error reaching Web Bridge");
    }
}

function showAdminModalError(msg) {
    adminModalError.textContent = msg;
    adminModalError.classList.remove("hidden");
}

function startAdminPolling() {
    fetchAdminStats();
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(fetchAdminStats, 2000);
}

async function fetchAdminStats() {
    if (!adminKey) return;
    try {
        const res = await fetch(`/api/admin/stats?admin_key=${encodeURIComponent(adminKey)}`);
        const data = await res.json();
        if (data.status === "ok") {
            renderAdminDashboard(data);
        } else if (data.status === "error") {
            sessionStorage.removeItem("lan_admin_key");
            adminKey = null;
            clearInterval(pollInterval);
            adminLoginModal.classList.remove("hidden");
            showAdminModalError(data.message);
        }
    } catch (err) {
        // network skip
    }
}

function renderAdminDashboard(data) {
    kpiActiveClients.textContent = data.active_sessions;
    kpiRoutedMsgs.textContent = data.messages_routed;
    kpiServerUptime.textContent = formatDuration(data.uptime_seconds);

    const timeoutMins = data.inactivity_timeout > 0 ? `${intMins(data.inactivity_timeout)}m` : "Disabled";
    kpiTimeoutVal.textContent = timeoutMins;

    // Update select dropdown if not manually focused
    if (document.activeElement !== selectTimeout) {
        selectTimeout.value = String(data.inactivity_timeout);
    }

    // Render Clients Table
    clientsTableBody.innerHTML = "";
    tableUserCount.textContent = data.clients.length;

    if (data.clients.length === 0) {
        clientsTableBody.innerHTML = `<tr><td colspan="6" class="empty-state">No active clients connected</td></tr>`;
        return;
    }

    data.clients.forEach(c => {
        const tr = document.createElement("tr");
        const idleMins = Math.floor(c.idle_seconds / 60);
        const idleSecs = c.idle_seconds % 60;
        const idleStr = `${idleMins}m ${idleSecs}s`;

        tr.innerHTML = `
            <td><strong>${escapeHtml(c.username)}</strong></td>
            <td><code>${escapeHtml(c.tcp_address)}</code></td>
            <td>${formatDuration(c.connected_seconds)}</td>
            <td><span class="${c.idle_seconds > 300 ? 'idle-warning' : ''}">${idleStr}</span></td>
            <td><span class="status-badge ${c.is_connected ? 'online' : 'offline'}">${c.is_connected ? 'CONNECTED' : 'DISCONNECTED'}</span></td>
            <td>
                <button type="button" class="kick-btn" data-username="${escapeHtml(c.username)}">🚫 Kick</button>
            </td>
        `;

        const kickBtn = tr.querySelector(".kick-btn");
        kickBtn.addEventListener("click", () => kickUser(c.username));

        clientsTableBody.appendChild(tr);
    });
}

async function kickUser(username) {
    if (!confirm(`Are you sure you want to kick user '${username}'?`)) return;

    try {
        const res = await fetch("/api/admin/kick", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_key: adminKey,
                username: username
            })
        });
        const data = await res.json();
        if (data.status === "ok") {
            fetchAdminStats();
        } else {
            alert(`Kick Failed: ${data.message}`);
        }
    } catch (err) {
        alert("Failed to send kick request.");
    }
}

// Broadcast Announcement Form Submit
broadcastForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = inputBroadcastMsg.value.trim();
    if (!msg || !adminKey) return;

    try {
        const res = await fetch("/api/admin/broadcast", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_key: adminKey,
                message: msg
            })
        });
        const data = await res.json();
        if (data.status === "ok") {
            showFeedback(broadcastFeedback, `✅ ${data.message}`, "success");
            inputBroadcastMsg.value = "";
        } else {
            showFeedback(broadcastFeedback, `❌ ${data.message}`, "error");
        }
    } catch (err) {
        showFeedback(broadcastFeedback, "❌ Broadcast failed.", "error");
    }
});

// Timeout Config Form Submit
timeoutConfigForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const newTimeout = parseInt(selectTimeout.value, 10);
    if (isNaN(newTimeout) || !adminKey) return;

    try {
        const res = await fetch("/api/admin/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                admin_key: adminKey,
                timeout_seconds: newTimeout
            })
        });
        const data = await res.json();
        if (data.status === "ok") {
            const label = newTimeout > 0 ? `${newTimeout / 60} minutes` : "Disabled";
            showFeedback(timeoutFeedback, `✅ Timeout threshold saved: ${label}`, "success");
            fetchAdminStats();
        } else {
            showFeedback(timeoutFeedback, `❌ ${data.message}`, "error");
        }
    } catch (err) {
        showFeedback(timeoutFeedback, "❌ Config save failed.", "error");
    }
});

function showFeedback(el, msg, type) {
    el.textContent = msg;
    el.className = `admin-feedback ${type}`;
    el.classList.remove("hidden");
    setTimeout(() => el.classList.add("hidden"), 4000);
}

btnAdminRefresh.addEventListener("click", () => fetchAdminStats());

btnAdminLogout.addEventListener("click", () => {
    sessionStorage.removeItem("lan_admin_key");
    adminKey = null;
    if (pollInterval) clearInterval(pollInterval);
    adminLoginModal.classList.remove("hidden");
});

function formatDuration(sec) {
    const hrs = String(Math.floor(sec / 3600)).padStart(2, '0');
    const mins = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
    const secs = String(sec % 60).padStart(2, '0');
    return `${hrs}:${mins}:${secs}`;
}

function intMins(sec) {
    return Math.floor(sec / 60);
}

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
