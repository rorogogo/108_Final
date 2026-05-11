const SFX_VOLUME = 0.45;
const SFX_MUTED_KEY = "endfieldMusicMuted";

const uiClickSound = new Audio("/static/click.wav");
const uiHoverSound = new Audio("/static/hover.wav");

uiClickSound.volume = SFX_VOLUME;
uiHoverSound.volume = SFX_VOLUME;

function sfxMuted() {
    return localStorage.getItem(SFX_MUTED_KEY) === "true";
}

function applySfxMute() {
    const muted = sfxMuted();
    uiClickSound.muted = muted;
    uiHoverSound.muted = muted;
}

function playSfx(sound) {
    if (sfxMuted()) {
        return;
    }
    sound.currentTime = 0;
    sound.play().catch(() => {});
}

function bindLoginButtonSfx() {
    const loginButton = document.querySelector('form[action="/"] button[type="submit"]');
    if (!loginButton) {
        return;
    }
    loginButton.addEventListener("mouseenter", () => playSfx(uiHoverSound));
    loginButton.addEventListener("click", () => playSfx(uiClickSound));
}

function bindProfileHoverSfx() {
    const profileButton = document.getElementById("account-menu-button");
    if (!profileButton) {
        return;
    }
    profileButton.addEventListener("mouseenter", () => playSfx(uiHoverSound));
}

document.addEventListener("endfield-music-mute-change", () => {
    applySfxMute();
});

document.addEventListener("DOMContentLoaded", () => {
    applySfxMute();
    bindLoginButtonSfx();
    bindProfileHoverSfx();
});
