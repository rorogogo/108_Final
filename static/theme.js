(function applySavedTheme() {
    const theme = localStorage.getItem("endfieldTheme") || "light";
    document.documentElement.dataset.theme = theme;
})();

function setTheme(theme) {
    const selectedTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = selectedTheme;
    localStorage.setItem("endfieldTheme", selectedTheme);
}

function toggleDarkMode() {
    const isDark = document.getElementById("dark-mode-input")?.checked;
    setTheme(isDark ? "dark" : "light");
}

document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("dark-mode-input");
    if (input) {
        input.checked = document.documentElement.dataset.theme === "dark";
    }
});
