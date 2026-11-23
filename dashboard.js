"use strict";

const locale = document.documentElement.lang === "ja" ? "ja-JP" : "en-US";
const dateTime = new Intl.DateTimeFormat(locale, {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "short",
});
for (const time of document.querySelectorAll("time[datetime]")) {
    const date = new Date(time.dateTime);
    if (!Number.isNaN(date.getTime())) {
        time.textContent = dateTime.format(date);
    }
}

for (const block of document.querySelectorAll(".copy-block")) {
    const button = block.querySelector("[data-copy]");
    const source = block.querySelector("pre code");
    const status = block.querySelector("[role=status]");
    button.hidden = false;
    button.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(source.textContent);
            status.textContent = status.dataset.copied;
        } catch {
            window.getSelection()?.selectAllChildren(source);
            status.textContent = status.dataset.fallback;
        }
    });
}

const clientPanel = document.querySelector("#client-panel");
if (clientPanel) {
    scheduleClientRefresh(clientPanel);
}

function scheduleClientRefresh(clientPanel) {
    const refreshStatus = document.querySelector("#client-refresh-status");
    const normalStatus = refreshStatus.textContent;
    const lastRefresh = document.querySelector("#client-last-refresh");
    const refreshInterval = 60_000;
    let lastAttempt = Date.now();
    let refreshing = false;

    async function refreshClients() {
        if (refreshing || document.hidden || clientPanel.contains(document.activeElement)) {
            return;
        }
        refreshing = true;
        lastAttempt = Date.now();
        try {
            const response = await fetch(clientPanel.dataset.refreshUrl, {cache: "no-store"});
            if (!response.ok) {
                throw new Error("Client status request failed");
            }
            const panel = await response.text();
            if (!document.hidden && !clientPanel.contains(document.activeElement)) {
                clientPanel.innerHTML = panel;
                refreshStatus.textContent = normalStatus;
                const checkedAt = new Date();
                const time = lastRefresh.querySelector("time");
                time.dateTime = checkedAt.toISOString();
                time.textContent = dateTime.format(checkedAt);
                lastRefresh.hidden = false;
            }
        } catch {
            refreshStatus.textContent = refreshStatus.dataset.failed;
        } finally {
            refreshing = false;
        }
    }

    window.setInterval(refreshClients, refreshInterval);
    document.addEventListener("visibilitychange", () => {
        if (Date.now() - lastAttempt >= refreshInterval) {
            refreshClients();
        }
    });
}
