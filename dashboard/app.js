/**
 * LAN Chat System - Client Dashboard Logic
 * Connects over HTTP to Web-Bridge, which interfaces directly with Python TCP Socket Server.
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

const userSelectDropdown = document.getElementById("user-select-dropdown");
const usersList = document.getElementById("users-list");
const userCount = document.getElementById("user-count");

const chatTabsBar = document.getElementById("chat-tabs-bar");
const channelTitle = document.getElementById("channel-title");
const channelIcon = document.getElementById("channel-icon");
const activeTargetDesc = document.getElementById("active-target-desc");

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
            btnSend.textContent = "Uploading...";

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
                
                // Clear selected file
                selectedFile = null;
                fileInput.value = "";
                filePreviewBar.classList.add("hidden");
            } else {
                appendSystemMessage(`Upload Error: ${upData.message}`);
                btnSend.disabled = false;
                btnSend.textContent = "Send 🚀";
                return;
            }
        } catch (err) {
            appendSystemMessage("Failed to upload file to Web Bridge server.");
            btnSend.disabled = false;
            btnSend.textContent = "Send 🚀";
            return;
        } finally {
            btnSend.disabled = false;
            btnSend.textContent = "Send 🚀";
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
            channel: "global"
        };

        addMessageToConversation("global", msgObj);

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
            channel: otherUser
        };

        if (!conversations[otherUser]) {
            conversations[otherUser] = [];
        }

        addMessageToConversation(otherUser, msgObj);

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
        updateUsersList(users);

    } else if (cmd === "SYSTEM") {
        const text = rawMsg.substring("SYSTEM:".length);
        addSystemMessageToActiveTab(text);

    } else if (cmd === "ERROR") {
        const text = rawMsg.substring("ERROR:".length);
        addSystemMessageToActiveTab(`⚠️ Error: ${text}`);
    }
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

    if (target === "global") {
        channelIcon.textContent = "#";
        channelTitle.textContent = "Global LAN Broadcast";
        activeTargetDesc.textContent = "Broadcasting to all connected clients";
    } else {
        channelIcon.textContent = "🔒";
        channelTitle.textContent = `Private Chat with ${target}`;
        activeTargetDesc.textContent = `Direct TCP socket private messaging with ${target}`;
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
    }
}

function renderTabs() {
    chatTabsBar.innerHTML = "";

    // Global Tab
    const globalBtn = document.createElement("button");
    globalBtn.className = `chat-tab ${activeTab === "global" ? "active" : ""}`;
    const globalUnread = unreadCounts["global"] || 0;
    globalBtn.innerHTML = `
        <span># Global Broadcast</span>
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
    
    // Add Welcome banner if global tab is empty
    const msgs = conversations[activeTab] || [];
    if (activeTab === "global" && msgs.length === 0) {
        const welcomeCard = document.createElement("div");
        welcomeCard.className = "system-welcome-card";
        welcomeCard.innerHTML = `
            <h3>🌐 Welcome to LAN Chat System</h3>
            <p>Academic TCP/IP Socket Application Layer Communication.</p>
            <p>Select any online person from the list to start a dedicated <strong>Private Chat</strong>, or send files using 📎 attach.</p>
        `;
        messagesContainer.appendChild(welcomeCard);
    } else if (activeTab !== "global" && msgs.length === 0) {
        const pmCard = document.createElement("div");
        pmCard.className = "system-welcome-card";
        pmCard.innerHTML = `
            <h3>🔒 Private Chat Channel</h3>
            <p>Direct private communication thread with <strong>${escapeHtml(activeTab)}</strong> over raw TCP socket.</p>
        `;
        messagesContainer.appendChild(pmCard);
    }

    msgs.forEach(msgObj => renderSingleMessage(msgObj));
}

function renderSingleMessage(msgObj) {
    const row = document.createElement("div");

    if (msgObj.type === "system") {
        row.className = "msg-row system";
        row.innerHTML = `<div class="msg-body">${escapeHtml(msgObj.text)}</div>`;
    } else {
        row.className = `msg-row ${msgObj.type}`;
        const now = new Date();
        const timeStr = now.toTimeString().split(" ")[0];
        let tagHtml = msgObj.tag ? `<span class="msg-tag pm">${msgObj.tag}</span>` : "";

        // Check if message text includes [FILE:filename:url:size]
        const formattedBody = formatMessageTextWithFiles(msgObj.text);

        row.innerHTML = `
            <div class="msg-meta">
                <span class="msg-author">${escapeHtml(msgObj.author)}</span>
                <span class="msg-time">${timeStr}</span>
                ${tagHtml}
            </div>
            <div class="msg-body">${formattedBody}</div>
        `;
    }

    messagesContainer.appendChild(row);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// --- FILE CARD REGEX PARSER ---
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

// --- ONLINE USER LIST & DROPDOWN RENDERER ---
function updateUsersList(users) {
    usersList.innerHTML = "";
    userCount.textContent = users.length;

    // Update Dropdown options
    userSelectDropdown.innerHTML = `<option value="">-- Select Person for Private Chat --</option>`;

    if (users.length === 0) {
        usersList.innerHTML = `<li class="empty-state">No active users</li>`;
        return;
    }

    users.forEach(u => {
        const isMe = (u === currentUsername);

        // Add to Dropdown if not self
        if (!isMe) {
            const opt = document.createElement("option");
            opt.value = u;
            opt.textContent = `🔒 ${u}`;
            userSelectDropdown.appendChild(opt);
        }

        // Add to Sidebar list
        const li = document.createElement("li");
        li.innerHTML = `
            <span>🟢 ${escapeHtml(u)}</span>
            <div class="user-actions">
                ${isMe ? '<span class="badge-me">YOU</span>' : `<button type="button" class="user-chat-btn">💬 Chat</button>`}
            </div>
        `;

        if (!isMe) {
            const chatBtn = li.querySelector(".user-chat-btn");
            chatBtn.addEventListener("click", () => {
                openPrivateChat(u);
            });
        }
        usersList.appendChild(li);
    });
}

userSelectDropdown.addEventListener("change", (e) => {
    const target = e.target.value;
    if (target) {
        openPrivateChat(target);
        userSelectDropdown.value = ""; // reset dropdown selection
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
