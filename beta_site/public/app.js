const downloads = document.querySelector("#downloads");
const confirmed = document.querySelector("#confirmed");
const downloadButton = document.querySelector("#download");
const confirmButton = document.querySelector("#confirm");
const ranCheck = document.querySelector("#ran-check");
const downloadStatus = document.querySelector("#download-status");
const confirmStatus = document.querySelector("#confirm-status");
const statsNote = document.querySelector("#stats-note");
const archiveSha = document.querySelector("#archive-sha");
const releaseLink = document.querySelector("#release-link");

const STORAGE_KEY = "neurodataBetaInstallSession";
let releaseInfo = null;
let installSession = "";

function setStatus(element, text, isError = false) {
  element.classList.toggle("error", isError);
  element.setAttribute("role", isError ? "alert" : "status");
  element.setAttribute("aria-live", isError ? "assertive" : "polite");
  element.textContent = text;
}

function readStoredSession() {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "null");
    if (value && typeof value.id === "string" && typeof value.version === "string") return value;
  } catch {
    // Confirmation still works until this page is closed when storage is unavailable.
  }
  return null;
}

function storeSession(id, version) {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ id, version }));
  } catch {
    // Keep the in-memory session so confirmation still works in this page.
  }
}

function clearStoredSession() {
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing else is required after a successful confirmation.
  }
}

function updateConfirmState() {
  ranCheck.disabled = !installSession;
  confirmButton.disabled = !installSession || !ranCheck.checked;
}

async function responseError(response, fallback) {
  try {
    const body = await response.json();
    return typeof body.error === "string" ? body.error : fallback;
  } catch {
    return fallback;
  }
}

async function refreshStats() {
  try {
    const response = await fetch("api/stats", { cache: "no-store" });
    if (!response.ok) throw new Error("unavailable");
    const data = await response.json();
    downloads.textContent = data.downloads;
    confirmed.textContent = data.confirmedInstallations;
    statsNote.textContent = "These counters do not represent unique researchers or completed dataset scans.";
  } catch {
    downloads.textContent = "—";
    confirmed.textContent = "—";
    statsNote.textContent = "Activity counters are temporarily unavailable; this does not prevent local scanner use.";
  }
}

async function loadRelease() {
  if (window.location.protocol === "file:") {
    throw new Error("This file is a static preview. Open the beta through its web address to download the package.");
  }
  const response = await fetch("api/info", { cache: "no-store" });
  if (!response.ok) throw new Error("The beta package information is unavailable.");
  releaseInfo = await response.json();
  if (!/^[0-9a-f]{64}$/.test(releaseInfo.archiveSha256)) {
    throw new Error("The beta package has not passed its build check.");
  }

  for (const element of document.querySelectorAll("[data-version]")) {
    element.textContent = releaseInfo.version;
  }
  archiveSha.textContent = releaseInfo.archiveSha256;
  releaseLink.href = releaseInfo.releaseUrl;
  releaseLink.textContent = `release ${releaseInfo.tag}`;

  const stored = readStoredSession();
  if (stored?.version === releaseInfo.version) installSession = stored.id;
  downloadButton.disabled = false;
  updateConfirmState();
  setStatus(downloadStatus, "Package ready.");
  await refreshStats();
}

downloadButton.addEventListener("click", async () => {
  if (!releaseInfo || downloadButton.dataset.busy === "true") return;
  downloadButton.dataset.busy = "true";
  downloadButton.disabled = true;
  setStatus(downloadStatus, "Preparing the archive…");
  try {
    const response = await fetch("api/download", { method: "POST" });
    if (!response.ok) throw new Error(await responseError(response, "The archive could not be downloaded."));

    const blob = await response.blob();
    const link = document.createElement("a");
    const objectUrl = URL.createObjectURL(blob);
    link.href = objectUrl;
    link.download = releaseInfo.archive;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000);

    installSession = response.headers.get("X-Install-Session") || "";
    if (installSession) storeSession(installSession, releaseInfo.version);
    ranCheck.checked = false;
    updateConfirmState();
    setStatus(
      downloadStatus,
      installSession
        ? "Archive downloaded. Open README_EN.md next."
        : "Archive downloaded. Installation confirmation is temporarily unavailable.",
    );
    await refreshStats();
  } catch (error) {
    setStatus(downloadStatus, error.message || "The archive could not be downloaded.", true);
  } finally {
    downloadButton.dataset.busy = "false";
    downloadButton.disabled = !releaseInfo;
    downloadButton.focus();
  }
});

ranCheck.addEventListener("change", updateConfirmState);

confirmButton.addEventListener("click", async () => {
  if (!installSession || confirmButton.dataset.busy === "true") return;
  confirmButton.dataset.busy = "true";
  confirmButton.disabled = true;
  setStatus(confirmStatus, "Saving the confirmation…");
  try {
    const response = await fetch("api/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ installSession }),
    });
    if (!response.ok) throw new Error(await responseError(response, "The confirmation was not saved."));

    const data = await response.json();
    downloads.textContent = data.downloads;
    confirmed.textContent = data.confirmedInstallations;
    statsNote.textContent = "These counters do not represent unique researchers or completed dataset scans.";
    installSession = "";
    clearStoredSession();
    ranCheck.checked = false;
    updateConfirmState();
    setStatus(confirmStatus, "Thank you — the installation confirmation was recorded.");
  } catch (error) {
    setStatus(confirmStatus, error.message || "The confirmation was not saved.", true);
  } finally {
    confirmButton.dataset.busy = "false";
    updateConfirmState();
    if (installSession && ranCheck.checked) confirmButton.focus();
  }
});

loadRelease().catch((error) => {
  setStatus(downloadStatus, error.message || "The beta package is unavailable.", true);
  downloadButton.disabled = true;
  ranCheck.disabled = true;
  confirmButton.disabled = true;
});
