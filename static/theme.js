const SITE_DEFAULT_KEYS = [
    "endfieldTheme",
    "endfieldChatMessages",
    "endfieldChatOpen",
    "endfieldMusicMuted",
    "endfieldMusicTime"
];

function clearSavedSiteDefaults() {
    SITE_DEFAULT_KEYS.forEach((key) => localStorage.removeItem(key));
}

function accountSavedTheme() {
    return window.ENDFIELD_SAVED_THEME === "dark" ? "dark" : "light";
}

(function applySavedTheme() {
    const shouldReset = new URLSearchParams(window.location.search).get("logged_out") === "1";
    if (shouldReset) {
        clearSavedSiteDefaults();
    }

    const theme = shouldReset ? "light" : accountSavedTheme();
    document.documentElement.dataset.theme = theme;
})();

function setTheme(theme) {
    const selectedTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = selectedTheme;
}

function toggleDarkMode() {
    const isDark = document.getElementById("dark-mode-input")?.checked;
    setTheme(isDark ? "dark" : "light");
}

function resetSiteDefaults() {
    clearSavedSiteDefaults();
    document.documentElement.dataset.theme = "light";

    const input = document.getElementById("dark-mode-input");
    if (input) {
        input.checked = false;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (new URLSearchParams(window.location.search).get("logged_out") === "1") {
        const url = new URL(window.location.href);
        url.searchParams.delete("logged_out");
        window.history.replaceState({}, "", url);
    }

    const input = document.getElementById("dark-mode-input");
    if (input) {
        input.checked = document.documentElement.dataset.theme === "dark";
    }
});
