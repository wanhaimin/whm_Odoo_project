(function () {
    if (window.__chatterAiAutoRefreshLoaded) {
        return;
    }

    const ACTIVE_POLL_INTERVAL_MS = 1000;
    const IDLE_POLL_INTERVAL_MS = 5000;
    const STORAGE_KEY = "chatter_ai_assistant:last_refreshed_finished_at";

    let hasPendingRun = false;
    let lastFinishedAt = null;
    let lastRefreshedFinishedAt = readStoredFinishedAt();
    let pollTimer = null;
    let refreshInFlight = false;
    let redirectInFlight = false;

    function readStoredFinishedAt() {
        try {
            return window.sessionStorage.getItem(STORAGE_KEY) || null;
        } catch (error) {
            return null;
        }
    }

    function writeStoredFinishedAt(value) {
        try {
            if (value) {
                window.sessionStorage.setItem(STORAGE_KEY, value);
            } else {
                window.sessionStorage.removeItem(STORAGE_KEY);
            }
        } catch (error) {
            // Ignore storage failures and keep in-memory fallback.
        }
    }

    function pageHasChatter() {
        return Boolean(document.querySelector(".o-mail-Chatter"));
    }

    function activateHandbookReviewTabIfNeeded() {
        if (window.location.hash !== "#handbook-review") {
            return false;
        }
        const candidates = [
            '[data-bs-target*="handbook_review_tab"]',
            '[href*="handbook_review_tab"]',
            '[aria-controls*="handbook_review_tab"]',
        ];
        for (const selector of candidates) {
            const tab = document.querySelector(selector);
            if (tab) {
                tab.click();
                return true;
            }
        }
        const fallbackTabs = Array.from(document.querySelectorAll(".nav-tabs .nav-link, .o_notebook_headers .nav-link, .o_notebook_headers button"));
        const fallback = fallbackTabs.find((element) => (element.textContent || "").includes("系列总览"));
        if (fallback) {
            fallback.click();
            return true;
        }
        return false;
    }

    function openHandbookReviewInPlace() {
        if (window.location.hash !== "#handbook-review") {
            window.location.hash = "handbook-review";
        }
        activateHandbookReviewTabWithRetries(20, 250);
    }

    function activateHandbookReviewTabWithRetries(maxAttempts = 12, delayMs = 300) {
        if (window.location.hash !== "#handbook-review") {
            return;
        }
        let attempts = 0;
        const tryActivate = () => {
            attempts += 1;
            const activated = activateHandbookReviewTabIfNeeded();
            if (!activated && attempts < maxAttempts) {
                window.setTimeout(tryActivate, delayMs);
            }
        };
        tryActivate();
    }

    function currentRecordIdFromPath() {
        const match = window.location.pathname.match(/\/odoo\/action-\d+\/(\d+)(?:\/|$)/);
        return match ? Number(match[1]) : null;
    }

    async function fetchFrontendStatus() {
        const response = await window.fetch("/chatter_ai_assistant/frontend/status", {
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
            },
        });
        if (!response.ok) {
            throw new Error(`Status request failed: ${response.status}`);
        }
        const payload = await response.json();
        return payload.status || {};
    }

    async function syncChatterState() {
        if (document.visibilityState !== "visible" || !pageHasChatter()) {
            scheduleNextPoll(IDLE_POLL_INTERVAL_MS);
            return;
        }
        try {
            const status = await fetchFrontendStatus();
            if (status.latest_finished_at && status.latest_finished_at !== lastFinishedAt) {
                lastFinishedAt = status.latest_finished_at;
            }
            hasPendingRun = Boolean(status.has_pending);
            if (
                !hasPendingRun
                && lastFinishedAt
                && lastFinishedAt !== lastRefreshedFinishedAt
            ) {
                lastRefreshedFinishedAt = lastFinishedAt;
                writeStoredFinishedAt(lastRefreshedFinishedAt);
                const redirected = await maybeRedirectToHandbookReview(status);
                if (!redirected) {
                    await refreshChatterRegion();
                }
            }
            if (hasPendingRun && lastRefreshedFinishedAt && lastFinishedAt !== lastRefreshedFinishedAt) {
                writeStoredFinishedAt(lastRefreshedFinishedAt);
            }
            scheduleNextPoll(hasPendingRun ? ACTIVE_POLL_INTERVAL_MS : IDLE_POLL_INTERVAL_MS);
        } catch (error) {
            window.console.debug("chatter_ai_assistant status polling failed", error);
            scheduleNextPoll(IDLE_POLL_INTERVAL_MS);
        }
    }

    async function refreshChatterRegion() {
        if (refreshInFlight) {
            return;
        }
        refreshInFlight = true;
        try {
            window.location.reload();
        } finally {
            refreshInFlight = false;
        }
    }

    async function maybeRedirectToHandbookReview(status) {
        if (redirectInFlight) {
            return true;
        }
        const redirectUrl = status.redirect_url;
        const currentRecordId = currentRecordIdFromPath();
        if (
            !redirectUrl
            || status.latest_finished_action !== "identify_handbook"
            || status.latest_finished_model !== "diecut.catalog.source.document"
            || !status.latest_finished_res_id
            || currentRecordId !== Number(status.latest_finished_res_id)
        ) {
            return false;
        }
        redirectInFlight = true;
        try {
            window.location.href = redirectUrl;
            return true;
        } finally {
            redirectInFlight = false;
        }
    }

    function scheduleNextPoll(delay) {
        if (pollTimer) {
            window.clearTimeout(pollTimer);
        }
        pollTimer = window.setTimeout(() => {
            pollTimer = null;
            syncChatterState();
        }, delay);
    }

    window.__chatterAiAutoRefreshLoaded = true;
    window.__chatterAiState = {
        get hasPendingRun() {
            return hasPendingRun;
        },
        get lastFinishedAt() {
            return lastFinishedAt;
        },
        get lastRefreshedFinishedAt() {
            return lastRefreshedFinishedAt;
        },
        get refreshInFlight() {
            return refreshInFlight;
        },
        get redirectInFlight() {
            return redirectInFlight;
        },
    };
    window.addEventListener("load", () => {
        activateHandbookReviewTabWithRetries();
        syncChatterState();
    });
    window.addEventListener("hashchange", () => {
        activateHandbookReviewTabWithRetries();
    });
    document.addEventListener(
        "click",
        (event) => {
            const trigger = event.target && event.target.closest
                ? event.target.closest(".o_open_handbook_review_tab_button")
                : null;
            if (!trigger) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            openHandbookReviewInPlace();
        },
        true,
    );
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
            syncChatterState();
        } else {
            scheduleNextPoll(IDLE_POLL_INTERVAL_MS);
        }
    });
})();
