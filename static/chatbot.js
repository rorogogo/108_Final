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
        if (!response.ok) {
            throw new Error("Chat failed");
        }
        return response.json();
    }).then((data) => {
        addChatMessage(data.reply, "bot");
    }).catch(() => {
        addChatMessage("I could not answer that yet. Try again after refreshing.", "bot");
    });
}

document.addEventListener("DOMContentLoaded", () => {
    loadChatbotMessages();
    toggleChatbot(localStorage.getItem(CHATBOT_OPEN_KEY) === "true");
});
