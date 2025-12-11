// SecureChat Logic

// ---------------------------------------------------------
// STATE MANAGEMENT
// ---------------------------------------------------------
const state = {
    token: localStorage.getItem('token'),
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    privateChats: [],
    groupChats: [],
    users: [],
    activeChat: null, // { id, type }
    socket: null,
    isAdmin: false // Simplified for demo
};

const API_URL = 'http://127.0.0.1:8000'; // Adjust if needed
const WS_URL = 'ws://127.0.0.1:8000/ws';

// ---------------------------------------------------------
// INITIALIZATION
// ---------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    initAuth();
    setupEventListeners();
    if (state.token) {
        navigate('view-app');
        connectWebSocket();
        loadInitialData();
    } else {
        navigate('view-auth');
    }
});

function setupEventListeners() {
    // Auth
    document.getElementById('to-signup').onclick = () => toggleAuthMode(true);
    document.getElementById('to-login').onclick = () => toggleAuthMode(false);
    document.getElementById('login-form').onsubmit = handleLogin;
    document.getElementById('signup-form').onsubmit = handleSignup;
    document.getElementById('btn-logout').onclick = handleLogout;
    document.getElementById('btn-contact-public').onclick = () => navigate('view-contact');
    document.getElementById('btn-back-auth').onclick = () => navigate('view-auth');
    document.getElementById('contact-form').onsubmit = handleContactSubmit;


    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.onclick = (e) => {
            // Admin is special
            if (e.target.id === 'nav-admin') {
                document.getElementById('admin-panel').classList.remove('hidden');
                loadAdminData();
                return;
            }

            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');

            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById(`tab-${e.target.dataset.tab}`).classList.add('active');

            if (e.target.dataset.tab === 'contacts') loadUsers();
            if (e.target.dataset.tab === 'chats') loadChats();
        };
    });

    // Chat
    document.getElementById('message-form').onsubmit = sendMessage;
    document.getElementById('btn-refresh-chats').onclick = loadChats;
    document.getElementById('btn-refresh-emails').onclick = loadAdminEmails;

    // Admin
    document.getElementById('btn-close-admin').onclick = () => document.getElementById('admin-panel').classList.add('hidden');
    document.querySelectorAll('.admin-tab').forEach(tab => {
        tab.onclick = (e) => {
            document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
            document.getElementById(e.target.dataset.target).classList.add('active');

            if (e.target.dataset.target === 'email-inbox') loadAdminEmails();
            if (e.target.dataset.target === 'email-config') loadAdminConfig();
            if (e.target.dataset.target === 'contact-subs') loadContactSubmissions();
        };
    });
    document.getElementById('config-form').onsubmit = handleConfigUpdate;
    document.getElementById('btn-toggle-mode').onclick = toggleEmailMode;
}

// ---------------------------------------------------------
// AUTHENTICATION
// ---------------------------------------------------------
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;

    try {
        const res = await apiCall('/api/auth/login', 'POST', { nick_name: username, password });
        state.token = res.access_token;
        state.user = res.user;
        localStorage.setItem('token', state.token);
        localStorage.setItem('user', JSON.stringify(state.user));

        showToast('Login successful', 'success');
        navigate('view-app');
        connectWebSocket();
        loadInitialData();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleSignup(e) {
    e.preventDefault();
    const username = document.getElementById('signup-username').value;
    const password = document.getElementById('signup-password').value;

    try {
        const res = await apiCall('/api/auth/signup', 'POST', { nick_name: username, password });
        state.token = res.access_token;
        state.user = res.user;
        localStorage.setItem('token', state.token);
        localStorage.setItem('user', JSON.stringify(state.user));

        showToast('Account created', 'success');
        navigate('view-app');
        connectWebSocket();
        loadInitialData();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function handleLogout() {
    state.token = null;
    state.user = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    if (state.socket) {
        state.socket.onclose = null; // Prevent reconnect triggering
        state.socket.close();
        state.socket = null;
    }
    navigate('view-auth');
}

function toggleAuthMode(isSignup) {
    document.getElementById('login-form').classList.toggle('hidden', isSignup);
    document.getElementById('signup-form').classList.toggle('hidden', !isSignup);
    document.getElementById('to-signup').classList.toggle('hidden', isSignup);
    document.getElementById('to-login').classList.toggle('hidden', !isSignup);
}

function initAuth() {
    toggleAuthMode(false);
}

// ---------------------------------------------------------
// DATA & UI
// ---------------------------------------------------------
async function loadInitialData() {
    updateUserInfo();
    await loadChats();
    // Enable admin button for everyone in this demo, or filter by user
    document.getElementById('nav-admin').style.display = 'block';
}

function updateUserInfo() {
    if (state.user) {
        document.getElementById('current-user-name').textContent = state.user.nick_name;
        document.getElementById('current-user-avatar').textContent = state.user.nick_name[0].toUpperCase();
    }
}

async function loadChats() {
    try {
        const res = await apiCall('/api/chats/private');
        state.privateChats = res.chats;
        renderChatList();
    } catch (err) {
        console.error('Failed to load chats', err);
    }
}

function renderChatList() {
    const list = document.getElementById('private-chat-list');
    list.innerHTML = '';

    state.privateChats.forEach(chat => {
        const li = document.createElement('li');
        li.className = `list-item ${state.activeChat && state.activeChat.id === chat.id ? 'active' : ''}`;
        li.onclick = () => openChat(chat.id, 'private', chat.other_participant);
        li.innerHTML = `
            <div class="item-avatar">${chat.other_participant[0].toUpperCase()}</div>
            <div class="item-info">
                <span class="item-name">${chat.other_participant}</span>
            </div>
        `;
        list.appendChild(li);
    });
}

async function loadUsers() {
    try {
        const res = await apiCall('/api/users');
        state.users = res.users;
        const list = document.getElementById('users-list');
        list.innerHTML = '';

        state.users.forEach(user => {
            const li = document.createElement('li');
            li.className = 'list-item';
            li.onclick = () => createPrivateChat(user.id);
            li.innerHTML = `
                <div class="item-avatar">${user.nick_name[0].toUpperCase()}</div>
                <div class="item-info">
                    <span class="item-name">${user.nick_name}</span>
                </div>
            `;
            list.appendChild(li);
        });
    } catch (err) {
        showToast('Failed to load users', 'error');
    }
}

async function createPrivateChat(otherUserId) {
    try {
        const res = await apiCall(`/api/chats/private?other_user_id=${otherUserId}`, 'POST');
        await loadChats();
        // Switch to chats tab
        document.querySelector('.nav-btn[data-tab="chats"]').click();
        // Open the new chat
        const chat = res.chat;
        const otherUser = state.users.find(u => u.id === otherUserId);
        openChat(chat.id, 'private', otherUser ? otherUser.nick_name : 'Chat');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function openChat(chatId, type, title) {
    state.activeChat = { id: chatId, type };

    document.getElementById('chat-placeholder').classList.add('hidden');
    document.getElementById('chat-container').classList.remove('hidden');
    document.getElementById('active-chat-title').textContent = title;
    document.getElementById('messages-area').innerHTML = ''; // Clear previous

    // Highlight sidebar item
    renderChatList();

    // Join WS room
    if (state.socket && state.socket.readyState === WebSocket.OPEN) {
        state.socket.send(JSON.stringify({
            type: type === 'private' ? 'join_private_chat' : 'join_group_chat',
            chat_id: chatId, // backend expects chat_id for private
            group_id: chatId // backend expects group_id for group
        }));
    }

    // Load history
    try {
        const endpoint = type === 'private' ? `/api/chats/private/${chatId}` : `/api/chats/groups/${chatId}`;
        const res = await apiCall(endpoint);
        res.messages.forEach(msg => {
            appendMessage(msg, msg.sender_id === state.user.id);
        });
    } catch (err) {
        console.error('Failed to load messages', err);
    }
}

function appendMessage(msg, isMe) {
    const area = document.getElementById('messages-area');
    const div = document.createElement('div');
    div.className = `message ${isMe ? 'sent' : 'received'}`;
    const time = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    div.innerHTML = `
        <div class="msg-bubble">${escapeHtml(msg.content)}</div>
        <div class="msg-meta">${time}</div>
    `;
    area.appendChild(div);
    area.scrollTop = area.scrollHeight;
}

async function sendMessage(e) {
    e.preventDefault();
    if (!state.activeChat) return;

    const input = document.getElementById('message-input');
    const content = input.value.trim();
    if (!content) return;

    // Send via WebSocket for real-time
    // Note: The backend logic in App.jsx implies sending via WS handles strict memory, 
    // BUT the backend server.py defines logic for "private_message" type in WS.
    if (state.socket && state.socket.readyState === WebSocket.OPEN) {
        // Optimistic UI update
        const tempMsg = {
            content: content,
            timestamp: new Date().toISOString(),
            sender_id: state.user.id,
            sender_name: state.user.nick_name
        };
        appendMessage(tempMsg, true);

        state.socket.send(JSON.stringify({
            type: state.activeChat.type === 'private' ? 'private_message' : 'group_message',
            chat_id: state.activeChat.id, // for private
            group_id: state.activeChat.id, // for group
            content: content
        }));
        input.value = '';
    } else {
        showToast('Connection lost', 'error');
    }
}

// ---------------------------------------------------------
// WEBSOCKETS
// ---------------------------------------------------------
function connectWebSocket() {
    if (!state.token || state.token === 'null' || state.token === 'undefined') return;

    if (state.socket) {
        state.socket.onclose = null;
        state.socket.close();
    }

    const token = encodeURIComponent(state.token);
    state.socket = new WebSocket(`${WS_URL}?token=${token}`);

    state.socket.onopen = () => {
        console.log('WS Connected');
        document.querySelector('.status-indicator').textContent = 'Online';
        document.querySelector('.status-indicator').style.color = 'var(--success)';

        // Re-join active chat if any
        if (state.activeChat) {
            openChat(state.activeChat.id, state.activeChat.type, document.getElementById('active-chat-title').textContent);
        }
    };

    state.socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWsMessage(data);
    };

    state.socket.onclose = () => {
        console.log('WS Disconnected');
        document.querySelector('.status-indicator').textContent = 'Offline';
        document.querySelector('.status-indicator').style.color = 'var(--text-muted)';
        if (state.token) {
            setTimeout(connectWebSocket, 3000); // Reconnect only if logged in
        }
    };
}

function handleWsMessage(data) {
    if (data.type === 'message') {
        // Check if message belongs to active chat
        if (state.activeChat) {
            const isTargetChat = (data.chat_type === 'private' && data.chat_id === state.activeChat.id) ||
                (data.chat_type === 'group' && data.group_id === state.activeChat.id);

            if (isTargetChat) {
                appendMessage(data.message, data.message.sender_id === state.user.id);
            } else {
                showToast(`New message from ${data.message.sender_name}`, 'success');
            }
        } else {
            showToast(`New message from ${data.message.sender_name}`, 'success');
        }
    } else if (data.type === 'message_sent') {
        // Acknowledge sent, maybe play sound
    } else if (data.type === 'error') {
        showToast(data.message, 'error');
    }
}

// ---------------------------------------------------------
// ADMIN & OTHERS
// ---------------------------------------------------------
async function loadAdminEmails() {
    try {
        const res = await apiCall('/api/admin/emails?limit=20');
        const list = document.getElementById('email-list');
        list.innerHTML = '';

        document.getElementById('current-email-mode').textContent = `Mode: ${res.mode}`;

        res.emails.forEach(email => {
            const li = document.createElement('li');
            li.className = 'email-item';
            li.innerHTML = `
                <div class="email-header">
                    <span>${escapeHtml(email.from)}</span>
                    <span>${email.date}</span>
                </div>
                <div class="email-subject">${escapeHtml(email.subject)}</div>
                <div class="email-body">${escapeHtml(email.body).substring(0, 100)}...</div>
            `;
            list.appendChild(li);
        });
    } catch (err) {
        showToast('Failed to load emails: ' + err.message, 'error');
    }
}

async function loadAdminConfig() {
    try {
        const res = await apiCall('/api/admin/email-config');
        const config = res.config;
        const form = document.getElementById('config-form');
        for (const [key, value] of Object.entries(config)) {
            if (form.elements[key]) form.elements[key].value = value || '';
        }
    } catch (err) {
        showToast('Failed to load config', 'error');
    }
}

async function handleConfigUpdate(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
        await apiCall('/api/admin/email-config', 'POST', formData, true); // true for form data
        showToast('Configuration saved', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function toggleEmailMode() {
    try {
        const currentText = document.getElementById('current-email-mode').textContent;
        const newMode = currentText.includes('IMAP') ? 'POP3' : 'IMAP';
        await apiCall(`/api/admin/email-mode?mode=${newMode}`, 'POST');
        loadAdminEmails();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleContactSubmit(e) {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
        await apiCall('/api/contact', 'POST', formData, true);
        showToast('Message sent successfully!', 'success');
        e.target.reset();
        setTimeout(() => navigate('view-auth'), 2000);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function loadContactSubmissions() {
    try {
        const res = await apiCall('/api/admin/contact-submissions');
        const list = document.getElementById('submission-list');
        list.innerHTML = '';

        if (res.submissions.length === 0) {
            list.innerHTML = '<li class="item-empty">No submissions found</li>';
            return;
        }

        res.submissions.reverse().forEach(sub => {
            const li = document.createElement('li');
            li.className = 'submission-item';
            const time = new Date(sub.timestamp).toLocaleString();

            li.innerHTML = `
                <div class="sub-header" style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span class="sub-name" style="font-weight: bold;">${escapeHtml(sub.name)}</span>
                    <span class="sub-date" style="font-size: 0.8em; color: var(--text-muted);">${time}</span>
                </div>
                <div class="sub-email" style="font-size: 0.9em; margin-bottom: 8px;">${escapeHtml(sub.email)}</div>
                <div class="sub-message" style="background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px;">${escapeHtml(sub.message)}</div>
                ${sub.attachment_filename ? `
                    <div class="sub-att" style="margin-top: 5px; font-size: 0.9em;">
                        📎 <a href="#" onclick="downloadFile('${sub.attachment_filename}')">${escapeHtml(sub.attachment_filename)}</a>
                    </div>` : ''}
            `;
            list.appendChild(li);
        });
    } catch (err) {
        showToast('Failed to load submissions: ' + err.message, 'error');
    }
}

// Helper to download files (reusing existing token logic if needed)
async function downloadFile(filename) {
    if (!state.token) return;
    window.open(`${API_URL}/api/chats/files/${filename}?token=${encodeURIComponent(state.token)}`, '_blank');
}

function loadAdminData() {
    loadAdminEmails();
}

// ---------------------------------------------------------
// UTILS
// ---------------------------------------------------------
async function apiCall(endpoint, method = 'GET', body = null, isFormData = false) {
    const headers = {};
    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }

    const options = { method, headers };

    if (body) {
        if (isFormData) {
            options.body = body;
        } else {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }
    }

    const res = await fetch(`${API_URL}${endpoint}`, options);
    const data = await res.json();

    if (!res.ok) {
        throw new Error(data.detail || data.message || 'API Error');
    }
    return data;
}

function navigate(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById(viewId).classList.remove('hidden');
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
