/**
 * LAN Chat System - WhatsApp & Instagram Inspired Dashboard Controller
 * Bridges Browser UI to Raw TCP Socket Server over HTTP Web Bridge
 */

// Application State
let sessionId = null;
let currentUsername = "";
let pollInterval = null;
let uptimeInterval = null;
let connectedTime = null;

let metricSentCount = 0;
let metricRecvCount = 0;

// Multi-Channel & File Attachment State
let activeTab = "global"; // "global" or username
let conversations = { "global": [] }; // { "global": [...], "alice": [...] }
let unreadCounts = {}; // { "alice": 2 }
let selectedFile = null; // { name, size, dataB64 }
let activeUsersList = []; // Array of usernames

// DOM Elements
const joinModal = document.getElementById("join-modal");
const joinForm = document.getElementById("join-form");
const modalError = document.getElementById("modal-error");

const displayLanIp = document.getElementById("display-lan-ip");
const displayTcpPort = document.getElementById("display-tcp-port");
const statusPill = document.getElementById("status-pill");
const statusText = document.getElementById("status-text");

const myUsername = document.getElementById("my-username");
const myAvatar = document.getElementById("my-avatar");
const mySessionInfo = document.getElementById("my-session-info");

const userSearchInput = document.getElementById("user-search-input");
const userSelectDropdown = document.getElementById("user-select-dropdown");
const usersList = document.getElementById("users-list");
const userCount = document.getElementById("user-count");

const globalThreadBtn = document.getElementById("global-thread-btn");
const globalLastTime = document.getElementById("global-last-time");
const globalLastMsg = document.getElementById("global-last-msg");

const headerAvatar = document.getElementById("header-avatar");
const channelTitle = document.getElementById("channel-title");
const activeTargetDesc = document.getElementById("active-target-desc");

const chatTabsBar = document.getElementById("chat-tabs-bar");
const messagesContainer = document.getElementById("messages-container");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");

const fileInput = document.getElementById("file-input");
const btnAttachFile = document.getElementById("btn-attach-file");
const filePreviewBar = document.getElementById("file-preview-bar");
const filePreviewInfo = document.getElementById("file-preview-info");
const btnRemoveFile = document.getElementById("btn-remove-file");

const btnRefreshUsers = document.getElementById("btn-refresh-users");
const btnLeave = document.getElementById("btn-leave");

const metricSent = document.getElementById("metric-sent");
const metricRecv = document.getElementById("metric-recv");
const metricUptime = document.getElementById("metric-uptime");

// On Page Load: Fetch System Config
window.addEventListener("DOMContentLoaded", async () => {
    try {
        const res = await fetch("/api/config");
        const data = await res.json();
        if (data.status === "ok") {
            displayLanIp.textContent = data.lan_ip;
            displayTcpPort.textContent = data.tcp_port;
        }
    } catch (e) {
        displayLanIp.textContent = "127.0.0.1";
    }
});

// Join Form Submit Handler
joinForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    modalError.classList.add("hidden");
    
    const username = document.getElementById("input-username").value.trim();
    const tcpHost = document.getElementById("input-tcphost").value.trim();
    const tcpPort = document.getElementById("input-tcpport").value.trim();

    if (!username) {
        showModalError("Username is required.");
        return;
    }

    const btn = document.getElementById("btn-join-submit");
    btn.disabled = true;
    btn.textContent = "Connecting to TCP Socket...";

    try {
        const res = await fetch("/api/connect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: username,
                tcp_host: tcpHost,
                tcp_port: tcpPort
            })
        });

        const data = await res.json();
        if (data.status === "ok") {
            sessionId = data.session_id;
            currentUsername = username;
            
            setConnectedUI(username, tcpHost, tcpPort);
            joinModal.classList.add("hidden");
            
            startPolling();
            startUptimeTracker();
        } else {
            showModalError(data.message || "Failed to connect to TCP server.");
        }
    } catch (err) {
        showModalError("Network error. Make sure Python TCP Server is running.");
    } finally {
        btn.disabled = false;
        btn.textContent = "Connect to TCP Server";
    }
});

function showModalError(msg) {
    modalError.textContent = msg;
    modalError.classList.remove("hidden");
}

function setConnectedUI(username, host, port) {
    myUsername.textContent = username;
    myAvatar.textContent = username.charAt(0).toUpperCase();
    mySessionInfo.textContent = `TCP Socket: ${host}:${port}`;
    
    statusPill.className = "connection-status-pill online";
    statusText.textContent = "CONNECTED (TCP)";

    chatInput.disabled = false;
    btnSend.disabled = false;
    btnAttachFile.disabled = false;
    btnLeave.classList.remove("hidden");
    chatInput.focus();
}

// --- FILE ATTACHMENT HANDLERS ---
btnAttachFile.addEventListener("click", () => {
    if (!sessionId) return;
    fileInput.click();
});

fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
        appendSystemMessage("⚠️ File size exceeds 10 MB limit.");
        fileInput.value = "";
        return;
    }

    const reader = new FileReader();
    reader.onload = function(evt) {
        const arrayBuffer = evt.target.result;
        const bytes = new Uint8Array(arrayBuffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const b64 = btoa(binary);

        selectedFile = {
            name: file.name,
            size: file.size,
            dataB64: b64
        };

        const kbSize = (file.size / 1024).toFixed(1);
        filePreviewInfo.textContent = `Selected: ${file.name} (${kbSize} KB)`;
        filePreviewBar.classList.remove("hidden");
    };
    reader.readAsArrayBuffer(file);
});

btnRemoveFile.addEventListener("click", () => {
    selectedFile = null;
    fileInput.value = "";
    filePreviewBar.classList.add("hidden");
});

// --- CHAT FORM SUBMIT HANDLER ---
chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const rawText = chatInput.value.trim();
    if (!sessionId) return;
    if (!rawText && !selectedFile) return;

    let finalMsgText = rawText;

    // Handle File Upload if selected
    if (selectedFile) {
        try {
            btnSend.disabled = true;

            const upRes = await fetch("/api/upload", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: sessionId,
                    filename: selectedFile.name,
                    file_data: selectedFile.dataB64
                })
            });
            const upData = await upRes.json();
            if (upData.status === "ok") {
                const fileTag = `[FILE:${upData.filename}:${upData.url}:${upData.size}]`;
                finalMsgText = rawText ? `${rawText}\n${fileTag}` : fileTag;
                
                selectedFile = null;
                fileInput.value = "";
                filePreviewBar.classList.add("hidden");
            } else {
                appendSystemMessage(`Upload Error: ${upData.message}`);
                btnSend.disabled = false;
                return;
            }
        } catch (err) {
            appendSystemMessage("Failed to upload file to Web Bridge server.");
            btnSend.disabled = false;
            return;
        } finally {
            btnSend.disabled = false;
        }
    }

    let command = "";
    
    // Slash commands
    if (finalMsgText.startsWith("/pm ")) {
        const parts = finalMsgText.substring(4).trim().split(" ", 1);
        const target = parts[0];
        const msgText = finalMsgText.substring(4 + target.length).trim();
        if (!target || !msgText) {
            appendSystemMessage("Usage: /pm <username> <message>");
            chatInput.value = "";
            return;
        }
        command = `PRIVATE:${currentUsername}:${target}:${msgText}`;
    } else if (finalMsgText === "/who") {
        command = "WHO";
    } else if (finalMsgText === "/quit" || finalMsgText === "/leave") {
        disconnectSession();
        return;
    } else {
        if (activeTab === "global") {
            command = `MSG:${currentUsername}:${finalMsgText}`;
        } else {
            command = `PRIVATE:${currentUsername}:${activeTab}:${finalMsgText}`;
        }
    }

    chatInput.value = "";

    try {
        const res = await fetch("/api/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                command: command
            })
        });
        const data = await res.json();
        if (data.status === "ok") {
            metricSentCount++;
            metricSent.textContent = metricSentCount;
        } else {
            appendSystemMessage(`Send Error: ${data.message}`);
        }
    } catch (err) {
        appendSystemMessage("Failed to reach Web Bridge.");
    }
});

// --- POLLING LOOP FOR INCOMING MESSAGES ---
function startPolling() {
    pollInterval = setInterval(async () => {
        if (!sessionId) return;
        try {
            const res = await fetch(`/api/poll?session_id=${sessionId}`);
            const data = await res.json();
            
            if (data.status === "ok") {
                if (!data.is_connected) {
                    appendSystemMessage("TCP Socket server connection closed.");
                    disconnectSession();
                    return;
                }
                if (data.messages && data.messages.length > 0) {
                    metricRecvCount += data.messages.length;
                    metricRecv.textContent = metricRecvCount;

                    data.messages.forEach(msgStr => parseIncomingProtocolMessage(msgStr));
                }
            } else {
                disconnectSession();
            }
        } catch (e) {
            // Passive network skip
        }
    }, 400);
}

// --- PROTOCOL PARSER & CHANNEL ROUTER ---
function parseIncomingProtocolMessage(rawMsg) {
    const parts = rawMsg.split(":", 2);
    const cmd = parts[0].toUpperCase ? parts[0].toUpperCase() : parts[0];

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (cmd === "MSG") {
        // MSG:sender:text
        const sub = rawMsg.split(":", 2);
        const remainder = rawMsg.substring(sub[0].length + 1);
        const idx = remainder.indexOf(":");
        const sender = remainder.substring(0, idx);
        const text = remainder.substring(idx + 1);

        const msgObj = {
            id: Date.now() + Math.random(),
            author: sender,
            text: text,
            type: sender === currentUsername ? "self" : "broadcast",
            channel: "global",
            time: timeStr
        };

        addMessageToConversation("global", msgObj);
        globalLastTime.textContent = timeStr;
        globalLastMsg.textContent = `${sender}: ${cleanTextForPreview(text)}`;

    } else if (cmd === "PRIVATE") {
        // PRIVATE:sender:target:text
        const parts = rawMsg.split(":");
        const sender = parts[1];
        const target = parts[2];
        const text = parts.slice(3).join(":");
        const isSelf = sender === currentUsername;
        const otherUser = isSelf ? target : sender;

        const msgObj = {
            id: Date.now() + Math.random(),
            author: isSelf ? `To ${target}` : `From ${sender}`,
            text: text,
            type: isSelf ? "self" : "private",
            tag: "PRIVATE MESSAGE",
            channel: otherUser,
            time: timeStr
        };

        if (!conversations[otherUser]) {
            conversations[otherUser] = [];
        }

        addMessageToConversation(otherUser, msgObj);
        renderUsersList();

    } else if (cmd === "JOIN") {
        const username = rawMsg.split(":")[1];
        addSystemMessageToActiveTab(`👤 ${username} joined the network.`);
        requestUserList();

    } else if (cmd === "LEAVE") {
        const username = rawMsg.split(":")[1];
        addSystemMessageToActiveTab(`🚪 ${username} left the network.`);
        requestUserList();

    } else if (cmd === "WHOREPLY") {
        const usersStr = rawMsg.substring("WHOREPLY:".length);
        const users = usersStr ? usersStr.split(",") : [];
        activeUsersList = users;
        renderUsersList();

    } else if (cmd === "SYSTEM") {
        const text = rawMsg.substring("SYSTEM:".length);
        addSystemMessageToActiveTab(text);

    } else if (cmd === "ERROR") {
        const text = rawMsg.substring("ERROR:".length);
        addSystemMessageToActiveTab(`⚠️ Error: ${text}`);
    }
}

function cleanTextForPreview(text) {
    if (!text) return "";
    if (text.includes("[FILE:")) return "📄 File attachment";
    return text;
}

function addMessageToConversation(channelKey, msgObj) {
    if (!conversations[channelKey]) {
        conversations[channelKey] = [];
    }
    conversations[channelKey].push(msgObj);

    if (activeTab === channelKey) {
        renderSingleMessage(msgObj);
    } else {
        unreadCounts[channelKey] = (unreadCounts[channelKey] || 0) + 1;
        renderTabs();
        renderUsersList();
    }
}

function addSystemMessageToActiveTab(text) {
    const msgObj = {
        id: Date.now() + Math.random(),
        text: text,
        type: "system",
        channel: activeTab
    };

    if (!conversations[activeTab]) {
        conversations[activeTab] = [];
    }
    conversations[activeTab].push(msgObj);
    renderSingleMessage(msgObj);
}

// --- TAB & CHANNEL MANAGEMENT ---
function openPrivateChat(targetUser) {
    if (!targetUser || targetUser === currentUsername) return;
    if (!conversations[targetUser]) {
        conversations[targetUser] = [];
    }
    renderTabs();
    switchTab(targetUser);
}

function switchTab(target) {
    activeTab = target;
    unreadCounts[target] = 0;
    renderTabs();
    renderUsersList();

    if (target === "global") {
        headerAvatar.textContent = "🌐";
        channelTitle.textContent = "Global LAN Broadcast";
        activeTargetDesc.innerHTML = `<span class="status-dot-inline"></span> Direct TCP Stream Broadcast`;
        globalThreadBtn.classList.add("active");
    } else {
        headerAvatar.textContent = target.charAt(0).toUpperCase();
        channelTitle.textContent = target;
        activeTargetDesc.innerHTML = `<span class="status-dot-inline"></span> Online via TCP Socket`;
        globalThreadBtn.classList.remove("active");
    }

    renderActiveMessages();
}

function closeTab(target, event) {
    if (event) event.stopPropagation();
    delete conversations[target];
    delete unreadCounts[target];
    if (activeTab === target) {
        switchTab("global");
    } else {
        renderTabs();
        renderUsersList();
    }
}

function renderTabs() {
    chatTabsBar.innerHTML = "";

    // Global Tab
    const globalBtn = document.createElement("button");
    globalBtn.className = `chat-tab ${activeTab === "global" ? "active" : ""}`;
    const globalUnread = unreadCounts["global"] || 0;
    globalBtn.innerHTML = `
        <span>🌐 # Global Broadcast</span>
        ${globalUnread > 0 ? `<span class="tab-unread-badge">${globalUnread}</span>` : ""}
    `;
    globalBtn.addEventListener("click", () => switchTab("global"));
    chatTabsBar.appendChild(globalBtn);

    // Private Tabs
    Object.keys(conversations).forEach(user => {
        if (user === "global") return;
        const tabBtn = document.createElement("button");
        tabBtn.className = `chat-tab ${activeTab === user ? "active" : ""}`;
        const unread = unreadCounts[user] || 0;
        tabBtn.innerHTML = `
            <span>🔒 ${escapeHtml(user)}</span>
            ${unread > 0 ? `<span class="tab-unread-badge">${unread}</span>` : ""}
            <span class="tab-close-btn" title="Close chat tab">✕</span>
        `;
        tabBtn.addEventListener("click", (e) => {
            if (e.target.classList.contains("tab-close-btn")) {
                closeTab(user, e);
            } else {
                switchTab(user);
            }
        });
        chatTabsBar.appendChild(tabBtn);
    });
}

function renderActiveMessages() {
    messagesContainer.innerHTML = "";
    
    const msgs = conversations[activeTab] || [];
    if (activeTab === "global" && msgs.length === 0) {
        const welcomeCard = document.createElement("div");
        welcomeCard.className = "system-welcome-card";
        welcomeCard.innerHTML = `
            <h3>💬 Welcome to LAN Chat</h3>
            <p>Select any person from the sidebar or dropdown to start a sleek <strong>Private Direct Chat</strong>.</p>
            <p>Send files instantly over Wi-Fi/LAN using the 📎 button.</p>
        `;
        messagesContainer.appendChild(welcomeCard);
    } else if (activeTab !== "global" && msgs.length === 0) {
        const pmCard = document.createElement("div");
        pmCard.className = "system-welcome-card";
        pmCard.innerHTML = `
            <h3>🔒 Direct Private Chat</h3>
            <p>End-to-end TCP socket private conversation thread with <strong>${escapeHtml(activeTab)}</strong>.</p>
        `;
        messagesContainer.appendChild(pmCard);
    }

    msgs.forEach(msgObj => renderSingleMessage(msgObj));
}

// --- RENDER WHATSAPP SPEECH BUBBLES ---
function renderSingleMessage(msgObj) {
    const row = document.createElement("div");

    if (msgObj.type === "system") {
        row.className = "msg-row system";
        row.innerHTML = `<div class="msg-body">${escapeHtml(msgObj.text)}</div>`;
    } else {
        row.className = `msg-row ${msgObj.type}`;
        
        const isSelf = (msgObj.type === "self");
        const timeStr = msgObj.time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const pmTag = msgObj.tag ? `<span class="msg-pm-tag">${msgObj.tag}</span>` : "";

        const formattedContent = formatMessageTextWithFiles(msgObj.text);

        row.innerHTML = `
            <div class="msg-bubble">
                <div class="msg-header-line">
                    <span class="msg-author-name">${escapeHtml(msgObj.author)}</span>
                    ${pmTag}
                </div>
                <div class="msg-content-text">${formattedContent}</div>
                <div class="msg-footer-line">
                    <span class="msg-timestamp">${timeStr}</span>
                    ${isSelf ? '<span class="msg-status-check">✓✓</span>' : ''}
                </div>
            </div>
        `;
    }

    messagesContainer.appendChild(row);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// --- FILE CARD PARSER ---
function formatMessageTextWithFiles(rawText) {
    const fileRegex = /\[FILE:(.*?):(.*?):(\d+)\]/g;
    let match;
    let lastIndex = 0;
    let htmlResult = "";

    while ((match = fileRegex.exec(rawText)) !== null) {
        const textBefore = rawText.substring(lastIndex, match.index);
        if (textBefore) {
            htmlResult += escapeHtml(textBefore);
        }

        const filename = match[1];
        const url = match[2];
        const sizeBytes = match[3];

        htmlResult += renderFileCardHtml(filename, url, sizeBytes);
        lastIndex = fileRegex.lastIndex;
    }

    const textRemaining = rawText.substring(lastIndex);
    if (textRemaining) {
        htmlResult += escapeHtml(textRemaining);
    }

    return htmlResult;
}

function renderFileCardHtml(filename, url, sizeBytes) {
    const kbSize = (parseInt(sizeBytes, 10) / 1024).toFixed(1);
    const isImage = /\.(png|jpe?g|gif|webp|svg)$/i.test(filename);
    const icon = isImage ? "🖼️" : "📄";

    let imgPreview = isImage ? `<img src="${escapeHtml(url)}" alt="${escapeHtml(filename)}" class="file-card-preview-img" loading="lazy">` : "";

    return `
        <div class="file-card">
            <div class="file-card-main">
                <span class="file-card-icon">${icon}</span>
                <div class="file-card-details">
                    <span class="file-card-name" title="${escapeHtml(filename)}">${escapeHtml(filename)}</span>
                    <span class="file-card-size">${kbSize} KB</span>
                </div>
                <a href="${escapeHtml(url)}" download="${escapeHtml(filename)}" class="file-card-download" target="_blank">📥 Download</a>
            </div>
            ${imgPreview}
        </div>
    `;
}

// --- WHATSAPP SIDEBAR THREAD LIST RENDERER ---
function renderUsersList() {
    const query = userSearchInput.value.toLowerCase().trim();
    usersList.innerHTML = "";
    userCount.textContent = activeUsersList.length;

    // Reset dropdown
    userSelectDropdown.innerHTML = `<option value="">-- Direct Message Person --</option>`;

    const filtered = activeUsersList.filter(u => u.toLowerCase().includes(query));

    if (filtered.length === 0) {
        usersList.innerHTML = `<li class="empty-state">No active users found</li>`;
        return;
    }

    filtered.forEach(u => {
        const isMe = (u === currentUsername);

        if (!isMe) {
            const opt = document.createElement("option");
            opt.value = u;
            opt.textContent = `🔒 ${u}`;
            userSelectDropdown.appendChild(opt);
        }

        const li = document.createElement("li");
        li.className = `chat-thread-item ${activeTab === u ? "active" : ""}`;

        // Get last message in conversation
        const userMsgs = conversations[u] || [];
        const lastMsgObj = userMsgs.length > 0 ? userMsgs[userMsgs.length - 1] : null;
        const lastText = lastMsgObj ? cleanTextForPreview(lastMsgObj.text) : "Tap to start private chat";
        const lastTime = lastMsgObj ? (lastMsgObj.time || "Active") : "Online";

        const unreadCount = unreadCounts[u] || 0;
        const unreadHtml = unreadCount > 0 ? `<span class="unread-pill">${unreadCount}</span>` : "";

        li.innerHTML = `
            <div class="user-thread-avatar">
                <span>${u.charAt(0).toUpperCase()}</span>
                <span class="user-status-dot"></span>
            </div>
            <div class="user-thread-details">
                <div class="user-thread-top">
                    <span class="user-thread-name">${escapeHtml(u)} ${isMe ? '(YOU)' : ''}</span>
                    <span class="thread-time">${lastTime}</span>
                </div>
                <div class="user-thread-top" style="margin-top: 2px;">
                    <span class="thread-sub">${escapeHtml(lastText)}</span>
                    ${unreadHtml}
                </div>
            </div>
        `;

        if (!isMe) {
            li.addEventListener("click", () => {
                openPrivateChat(u);
            });
        }
        usersList.appendChild(li);
    });
}

globalThreadBtn.addEventListener("click", () => {
    switchTab("global");
});

userSearchInput.addEventListener("input", () => renderUsersList());

userSelectDropdown.addEventListener("change", (e) => {
    const target = e.target.value;
    if (target) {
        openPrivateChat(target);
        userSelectDropdown.value = "";
    }
});

function requestUserList() {
    if (!sessionId) return;
    fetch("/api/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, command: "WHO" })
    }).catch(() => {});
}

btnRefreshUsers.addEventListener("click", () => requestUserList());
btnLeave.addEventListener("click", () => disconnectSession());

function disconnectSession() {
    if (sessionId) {
        fetch("/api/disconnect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId })
        }).catch(() => {});
    }

    clearInterval(pollInterval);
    clearInterval(uptimeInterval);
    sessionId = null;
    activeTab = "global";
    conversations = { "global": [] };
    unreadCounts = {};
    selectedFile = null;
    activeUsersList = [];

    statusPill.className = "connection-status-pill offline";
    statusText.textContent = "DISCONNECTED";

    myUsername.textContent = "Not Connected";
    myAvatar.textContent = "?";
    mySessionInfo.textContent = "Standard TCP Socket Client";

    chatInput.disabled = true;
    btnSend.disabled = true;
    btnAttachFile.disabled = true;
    btnLeave.classList.add("hidden");
    filePreviewBar.classList.add("hidden");

    joinModal.classList.remove("hidden");
}

function startUptimeTracker() {
    connectedTime = new Date();
    uptimeInterval = setInterval(() => {
        if (!connectedTime) return;
        const diffSec = Math.floor((new Date() - connectedTime) / 1000);
        const hrs = String(Math.floor(diffSec / 3600)).padStart(2, '0');
        const mins = String(Math.floor((diffSec % 3600) / 60)).padStart(2, '0');
        const secs = String(diffSec % 60).padStart(2, '0');
        metricUptime.textContent = `${hrs}:${mins}:${secs}`;
    }, 1000);
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
