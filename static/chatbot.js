const CHATBOT_MESSAGES_KEY = "endfieldChatMessages";
const CHATBOT_OPEN_KEY = "endfieldChatOpen";
const STARTER_MESSAGE = "Hello! Thank you for using this website. How can I assist you today?";

let chatHistory = [];

function storedMessages() {
    try {
        const parsed = JSON.parse(localStorage.getItem(CHATBOT_MESSAGES_KEY) || "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

function saveMessages() {
    localStorage.setItem(CHATBOT_MESSAGES_KEY, JSON.stringify(chatHistory.slice(-50)));
}

function clearChatbotStorage() {
    localStorage.removeItem(CHATBOT_MESSAGES_KEY);
    localStorage.removeItem(CHATBOT_OPEN_KEY);
}

function addChatMessage(text, sender, persist = true) {
    const messages = document.getElementById("chatbot-messages");
    if (!messages) {
        return;
    }

    const message = document.createElement("div");
    message.className = `chat-message ${sender}`;
    message.textContent = text;
    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;

    if (persist) {
        chatHistory.push({ role: sender === "user" ? "user" : "assistant", content: text });
        chatHistory = chatHistory.slice(-50);
        saveMessages();
    }
}

function loadChatbotMessages() {
    const messages = document.getElementById("chatbot-messages");
    if (!messages) {
        return;
    }

    messages.innerHTML = "";
    chatHistory = storedMessages();

    if (!chatHistory.length) {
        addChatMessage(STARTER_MESSAGE, "bot", false);
        return;
    }

    chatHistory.forEach((item) => {
        addChatMessage(item.content, item.role === "user" ? "user" : "bot", false);
    });
}

function toggleChatbot(forceOpen) {
    const widget = document.getElementById("chatbot-widget");
    const launcher = document.getElementById("chatbot-launcher");
    if (!widget || !launcher) {
        return;
    }

    const open = typeof forceOpen === "boolean" ? forceOpen : !widget.classList.contains("open");
    if (open && document.body.dataset.loggedIn === "false") {
        openLoginRequiredModal("Please Log In first");
        return;
    }

    widget.classList.toggle("open", open);
    launcher.setAttribute("aria-expanded", open ? "true" : "false");
    localStorage.setItem(CHATBOT_OPEN_KEY, String(open));

    if (open) {
        document.getElementById("chatbot-input")?.focus();
    }
}

function sendChatbotMessage(event) {
    event.preventDefault();
    const input = document.getElementById("chatbot-input");
    const message = input.value.trim();
    if (!message) {
        return;
    }

    const priorHistory = chatHistory.slice(-6);
    addChatMessage(message, "user");
    input.value = "";

    fetch("/chatbot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            message,
            history: priorHistory
        })
    }).then((response) => {
        if (response.status === 401) {
            input.value = message;
            chatHistory.pop();
            saveMessages();
            document.querySelector(".chat-message.user:last-child")?.remove();
            if (typeof openLoginRequiredModal === "function") {
                openLoginRequiredModal("Please Log In first");
                return null;
            }
            window.location.href = "/login";
            return null;
        }
        if (!response.ok) {
            throw new Error("Chat failed");
        }
        return response.json();
    }).then((data) => {
        if (!data) {
            return;
        }
        addChatMessage(data.reply, "bot");
    }).catch((error) => {
        addChatMessage(error.message || "I could not answer that yet. Try again after refreshing.", "bot");
    });
}

function ensureLoginRequiredModal() {
    if (document.getElementById("login-required-modal")) {
        return;
    }

    const modal = document.createElement("div");
    modal.className = "modal-backdrop";
    modal.id = "login-required-modal";
    modal.hidden = true;
    modal.innerHTML = `
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="login-required-title">
            <button class="modal-close" type="button" aria-label="Close login prompt" onclick="closeLoginRequiredModal()">X</button>
            <h2 id="login-required-title">Log in to continue</h2>
            <form class="modal-login-form" method="POST" action="/login">
                <div class="field">
                    <label for="modal-login-name">Username</label>
                    <input id="modal-login-name" name="name" autocomplete="username">
                </div>
                <div class="field">
                    <label for="modal-login-password">Password</label>
                    <input id="modal-login-password" name="password" type="password" autocomplete="current-password">
                </div>
                <button class="primary-button" type="submit">Log In</button>
            </form>
            <a class="secondary-button modal-create-account" href="/signup">Create Account</a>
        </div>
    `;
    document.body.appendChild(modal);
}

function openLoginRequiredModal(title = "Log in to continue") {
    ensureLoginRequiredModal();
    document.getElementById("login-required-title").textContent = title;
    document.getElementById("login-required-modal").hidden = false;
    setTimeout(() => document.getElementById("modal-login-name")?.focus(), 0);
}

function closeLoginRequiredModal() {
    const modal = document.getElementById("login-required-modal");
    if (modal) {
        modal.hidden = true;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    ensureLoginRequiredModal();
    loadChatbotMessages();
    if (document.body.dataset.loggedIn === "false") {
        localStorage.setItem(CHATBOT_OPEN_KEY, "false");
        return;
    }
    toggleChatbot(localStorage.getItem(CHATBOT_OPEN_KEY) === "true");
});

document.addEventListener("click", (event) => {
    if (event.target.id === "login-required-modal") {
        closeLoginRequiredModal();
    }
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        closeLoginRequiredModal();
    }
});
