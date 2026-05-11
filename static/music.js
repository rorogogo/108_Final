const MUSIC_MUTED_KEY = "endfieldMusicMuted";
const MUSIC_VOLUME = 0.3;
const MUSIC_TIME_KEY = "endfieldMusicTime";

const bgMusic = new Audio("/static/OST1.mp3");
bgMusic.loop = true;
bgMusic.volume = MUSIC_VOLUME;
bgMusic.preload = "auto";
bgMusic.autoplay = true;

let hasRestoredTime = false;

function storedMusicTime() {
    const raw = localStorage.getItem(MUSIC_TIME_KEY);
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed < 0) {
        return 0;
    }
    return parsed;
}

function saveMusicTime() {
    if (!Number.isFinite(bgMusic.currentTime) || bgMusic.currentTime < 0) {
        return;
    }
    localStorage.setItem(MUSIC_TIME_KEY, String(bgMusic.currentTime));
}

function restoreMusicTime() {
    if (hasRestoredTime) {
        return;
    }
    const targetTime = storedMusicTime();
    if (targetTime <= 0) {
        hasRestoredTime = true;
        return;
    }

    const seekToSavedTime = () => {
        const duration = Number.isFinite(bgMusic.duration) ? bgMusic.duration : 0;
        if (duration > 0) {
            bgMusic.currentTime = Math.min(targetTime, Math.max(0, duration - 0.2));
        } else {
            bgMusic.currentTime = targetTime;
        }
        hasRestoredTime = true;
    };

    if (bgMusic.readyState >= 1) {
        seekToSavedTime();
    } else {
        bgMusic.addEventListener("loadedmetadata", seekToSavedTime, { once: true });
    }
}

function storedMusicMuted() {
    return localStorage.getItem(MUSIC_MUTED_KEY) === "true";
}

function applyMusicMute(muted) {
    bgMusic.muted = Boolean(muted);
    localStorage.setItem(MUSIC_MUTED_KEY, String(Boolean(muted)));
}

function emitMuteChanged(muted) {
    document.dispatchEvent(
        new CustomEvent("endfield-music-mute-change", { detail: { muted: Boolean(muted) } })
    );
}

function tryPlayMusic() {
    const playPromise = bgMusic.play();
    if (playPromise && typeof playPromise.catch === "function") {
        playPromise.catch(() => {
            const resume = () => {
                bgMusic.play().catch(() => {});
                document.removeEventListener("pointerdown", resume);
                document.removeEventListener("keydown", resume);
            };
            document.addEventListener("pointerdown", resume);
            document.addEventListener("keydown", resume);
        });
    }
}

function ensureMusicPlaying() {
    if (bgMusic.muted) {
        return;
    }
    if (bgMusic.paused) {
        tryPlayMusic();
    }
}

function wireMuteControl() {
    const muteInput = document.getElementById("sound-muted");
    const muteButton = document.getElementById("sound-muted-button");

    const setMuteVisual = (muted) => {
        if (muteInput) {
            muteInput.checked = muted;
        }
        if (muteButton) {
            muteButton.setAttribute("aria-pressed", muted ? "true" : "false");
            muteButton.setAttribute("title", muted ? "Unmute audio" : "Mute audio");
        }
    };

    const currentMuted = storedMusicMuted();
    setMuteVisual(currentMuted);
    emitMuteChanged(currentMuted);

    if (muteInput) {
        muteInput.addEventListener("change", () => {
            applyMusicMute(muteInput.checked);
            setMuteVisual(muteInput.checked);
            emitMuteChanged(muteInput.checked);
        });
    }

    if (muteButton) {
        muteButton.addEventListener("click", () => {
            const nextMuted = !storedMusicMuted();
            applyMusicMute(nextMuted);
            setMuteVisual(nextMuted);
            emitMuteChanged(nextMuted);
        });
    }
}

function initMusicControls() {
    wireMuteControl();
}

restoreMusicTime();
applyMusicMute(storedMusicMuted());
ensureMusicPlaying();

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMusicControls, { once: true });
} else {
    initMusicControls();
}

window.addEventListener("pageshow", () => {
    ensureMusicPlaying();
});

document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
        ensureMusicPlaying();
    }
});

document.addEventListener("endfield-music-mute-change", (event) => {
    if (!Boolean(event.detail?.muted)) {
        ensureMusicPlaying();
    }
});

bgMusic.addEventListener("timeupdate", () => {
    saveMusicTime();
});

window.addEventListener("pagehide", () => {
    saveMusicTime();
});

window.addEventListener("beforeunload", () => {
    saveMusicTime();
});
