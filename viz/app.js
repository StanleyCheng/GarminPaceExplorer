import { createInsightDashboard } from "./insight-ui.mjs";

const statusEl = document.getElementById("status");
const refreshButton = document.getElementById("refresh-button");
const lastUpdatedEl = document.getElementById("last-updated");
const authView = document.getElementById("auth-view");
const accountView = document.getElementById("account-view");
const emptyView = document.getElementById("empty-view");
const accountBar = document.getElementById("account-bar");
const accountButton = document.getElementById("account-button");
const dashboardContent = document.getElementById("dashboard-content");
const dashboard = createInsightDashboard();
let currentPaceData = null;
let localMode = false;
let currentUser = null;
let signupMode = false;
let syncRunning = false;
let refreshGeneration = 0;

function showStatus(message, kind = "") {
  statusEl.className = `status${kind ? ` status-${kind}` : ""}`;
  statusEl.setAttribute("role", kind === "error" ? "alert" : "status");
  statusEl.textContent = message;
  statusEl.hidden = !message;
}

function setUpdatedTime(value) {
  const updated = new Date(value);
  if (value && Number.isFinite(updated.getTime())) {
    lastUpdatedEl.dateTime = updated.toISOString();
    lastUpdatedEl.textContent = new Intl.DateTimeFormat(undefined, {
      year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    }).format(updated);
    lastUpdatedEl.title = `Last successful Garmin sync: ${updated.toLocaleString()}`;
  } else {
    lastUpdatedEl.removeAttribute("datetime");
    lastUpdatedEl.textContent = "Not synced yet";
    lastUpdatedEl.title = "A date appears after a complete import";
  }
}

function showDashboard() {
  authView.hidden = true;
  accountView.hidden = true;
  accountButton.removeAttribute("aria-current");
  dashboardContent.hidden = !currentPaceData;
  emptyView.hidden = Boolean(currentPaceData);
  if (currentPaceData) dashboard.render();
}

function setSyncState(running, count = 0) {
  syncRunning = running;
  document.getElementById("sync-dot").hidden = !running;
  document.getElementById("sync-label").textContent = running
    ? `Loading · ${count.toLocaleString()} records` : "Last data update";
  refreshButton.disabled = running || !currentUser;
  refreshButton.setAttribute("aria-label", running
    ? "Loading all Garmin activities" : "Refresh all Garmin activities");
  refreshButton.title = currentUser ? "Refresh your complete Garmin history" : "Sign in to refresh your Garmin history";
  if (running) refreshButton.setAttribute("aria-busy", "true");
  else refreshButton.removeAttribute("aria-busy");
  document.getElementById("empty-refresh").disabled = running;
  document.getElementById("empty-refresh").textContent = running ? "Importing all activities…" : "Import all Garmin activities";
  accountButton.disabled = running || localMode;
}

function clearUser() {
  refreshGeneration += 1;
  currentUser = null;
  currentPaceData = null;
  localMode = false;
  dashboard.clear();
  accountBar.hidden = true;
  dashboardContent.hidden = true;
  accountView.hidden = true;
  emptyView.hidden = true;
  document.getElementById("garmin-password").value = "";
  document.getElementById("garmin-session").value = "";
  document.getElementById("signup-garmin-password").value = "";
  document.getElementById("app-password").value = "";
  setUpdatedTime(null);
  setSyncState(false);
}

function setAuthMode(signup) {
  signupMode = signup;
  document.getElementById("auth-title").textContent = signup ? "Create your account" : "Welcome back";
  document.getElementById("auth-intro").textContent = signup
    ? "Choose your app sign-in and connect Garmin to import your complete activity history."
    : "Sign in to explore your personal Garmin activity history.";
  document.getElementById("signup-garmin").hidden = !signup;
  document.getElementById("signup-garmin").disabled = !signup;
  document.getElementById("username-hint").hidden = !signup;
  document.getElementById("password-hint").hidden = !signup;
  const password = document.getElementById("app-password");
  password.value = "";
  password.autocomplete = signup ? "new-password" : "current-password";
  password.minLength = signup ? 10 : 1;
  document.getElementById("signup-garmin-password").value = "";
  document.getElementById("auth-submit").textContent = signup ? "Create account and import" : "Sign in";
  document.getElementById("auth-switch-copy").textContent = signup ? "Already have an account?" : "New to GarminPaceExplorer?";
  document.getElementById("auth-switch").textContent = signup ? "Sign in" : "Create an account";
}

function showAuth(message = "", isError = false) {
  clearUser();
  setAuthMode(false);
  authView.hidden = false;
  showStatus(message, isError ? "error" : "");
}

function applyPayload(payload) {
  if (!Array.isArray(payload.activities)) throw new Error("The Garmin response is invalid. Refresh again to retry.");
  currentPaceData = dashboard.applyPayload(payload);
  setUpdatedTime(payload.meta?.generated_at);
  showDashboard();
}

async function apiRequest(action, body) {
  let response;
  try {
    response = await fetch(`/api/dashboard${action ? `?action=${action}` : ""}`, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new Error("Could not reach the dashboard server. Check your connection and try again.");
  }
  let payload;
  try {
    payload = await response.json();
  } catch {
    const error = new Error(response.status === 504
      ? "The Garmin import timed out. Try refreshing again."
      : "The dashboard server is unavailable. Try again later.");
    error.status = response.status;
    throw error;
  }
  if (!response.ok) {
    const error = new Error(payload.error || "Could not load Garmin data. Try again later.");
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function loadDashboard() {
  try {
    const result = await apiRequest();
    if (!result.user?.username) throw new Error("Your account could not be loaded. Sign in again.");
    currentUser = result.user;
    accountBar.hidden = false;
    document.getElementById("account-name").textContent = `Signed in as ${currentUser.username}`;
    document.getElementById("signout-button").hidden = false;
    if (result.payload) applyPayload(result.payload);
    else {
      currentPaceData = null;
      setUpdatedTime(null);
      showDashboard();
    }
    setSyncState(false);
    showStatus("");
    return true;
  } catch (error) {
    const isLocal = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
    if (isLocal && (error.status === 404 || error.status === 501)) {
      try {
        const response = await fetch("./data/garmin_activities.json", { cache: "no-store" });
        if (response.ok) {
          localMode = true;
          currentUser = { username: "Local preview" };
          accountBar.hidden = false;
          document.getElementById("account-name").textContent = "Local data preview";
          document.getElementById("signout-button").hidden = true;
          applyPayload(await response.json());
          setSyncState(false);
          showStatus("Local data preview. Live Garmin imports and accounts are available on the deployed app.");
          return true;
        }
      } catch { /* A missing local export returns to the account screen. */ }
    }
    showAuth(error.status === 401 ? "" : error.message, error.status !== 401);
    return false;
  }
}

async function refresh() {
  if (syncRunning || !currentUser) return;
  if (localMode) {
    showStatus("For a local update, run get-garmin.py and reload this page. Live Garmin imports are available on the deployed app.");
    return;
  }
  const generation = ++refreshGeneration;
  setSyncState(true);
  showStatus("Connecting to Garmin. Importing every activity from your account; keep this tab open until loading finishes.");
  try {
    let result = await apiRequest("refresh", {});
    if (generation !== refreshGeneration) return;
    if (!result.job_id && !result.complete) throw new Error("The import could not start. Refresh again to retry.");
    const jobId = result.job_id;
    while (!result.complete) {
      const count = Number.isInteger(result.records_loaded) ? result.records_loaded : 0;
      setSyncState(true, count);
      showStatus(`Importing your complete Garmin history… ${count.toLocaleString()} records loaded. Keep this tab open until loading finishes.`);
      result = await apiRequest("sync-step", { job_id: jobId });
      if (generation !== refreshGeneration) return;
    }
    if (!result.payload) throw new Error("The completed import did not include your dashboard. Refresh again to retry.");
    applyPayload(result.payload);
    const count = Number.isInteger(result.records_loaded) ? result.records_loaded : result.payload.meta?.activity_count_fetched;
    showStatus(`${Number.isInteger(count) ? count.toLocaleString() : "All"} Garmin records imported. Your dashboard is up to date.`, "success");
  } catch (error) {
    if (generation !== refreshGeneration) return;
    if (error.status === 401) {
      showAuth("Your session expired. Sign in again to import your Garmin history.", true);
    } else {
      showStatus(`Import stopped. ${error.message}${currentPaceData ? " Your last completed dashboard is still available." : ""}`, "error");
    }
  } finally {
    if (generation === refreshGeneration) setSyncState(false);
  }
}

function setFormBusy(form, busy) {
  for (const field of form.querySelectorAll("input, textarea, button")) field.disabled = busy;
  const button = form.querySelector('button[type="submit"]');
  if (busy) button.setAttribute("aria-busy", "true");
  else button.removeAttribute("aria-busy");
}

async function submitAuth(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const signup = signupMode;
  const body = {
    username: document.getElementById("app-username").value.trim(),
    password: document.getElementById("app-password").value,
  };
  if (signup) {
    body.garmin_username = document.getElementById("signup-garmin-username").value.trim();
    body.garmin_password = document.getElementById("signup-garmin-password").value;
  }
  setFormBusy(form, true);
  document.getElementById("auth-switch").disabled = true;
  showStatus(signup ? "Creating your account…" : "Signing in…");
  try {
    await apiRequest(signup ? "signup" : "login", body);
    document.getElementById("app-password").value = "";
    document.getElementById("signup-garmin-password").value = "";
    const loaded = await loadDashboard();
    if (signup && loaded) await refresh();
  } catch (error) {
    showStatus(error.message, "error");
    document.getElementById("app-password").value = "";
  } finally {
    setFormBusy(form, false);
    document.getElementById("auth-switch").disabled = false;
  }
}

function openAccount() {
  if (!currentUser || syncRunning || localMode) return;
  document.getElementById("garmin-username").value = currentUser.garmin_username || "";
  document.getElementById("garmin-password").value = "";
  dashboardContent.hidden = true;
  emptyView.hidden = true;
  accountView.hidden = false;
  accountButton.setAttribute("aria-current", "page");
  showStatus("");
  document.getElementById("garmin-username").focus();
}

async function submitGarmin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  setFormBusy(form, true);
  showStatus("Saving your Garmin connection…");
  try {
    await apiRequest("garmin", {
      garmin_username: document.getElementById("garmin-username").value.trim(),
      garmin_password: document.getElementById("garmin-password").value,
    });
    document.getElementById("garmin-password").value = "";
    // The old payload belongs to the previous Garmin connection.
    currentPaceData = null;
    dashboard.clear();
    setUpdatedTime(null);
    if (await loadDashboard()) await refresh();
  } catch (error) {
    if (error.status === 401) showAuth("Your session expired. Sign in again to change your Garmin connection.", true);
    else showStatus(error.message, "error");
  } finally {
    setFormBusy(form, false);
  }
}

async function signOut() {
  const button = document.getElementById("signout-button");
  button.disabled = true;
  try {
    await apiRequest("logout", {});
    showAuth("You have signed out.");
  } catch (error) {
    showStatus(`Could not sign out. ${error.message}`, "error");
  } finally {
    button.disabled = false;
  }
}

async function submitSession(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const field = document.getElementById("garmin-session");
  try {
    JSON.parse(field.value);
  } catch {
    showStatus("The session is not valid JSON. Copy the complete verified-session file and try again.", "error");
    field.focus();
    return;
  }
  setFormBusy(form, true);
  showStatus("Saving your verified Garmin session…");
  try {
    await apiRequest("garmin-session", { session_json: field.value });
    field.value = "";
    showDashboard();
    await refresh();
  } catch (error) {
    if (error.status === 401) showAuth("Your session expired. Sign in again to save your Garmin connection.", true);
    else showStatus(error.message, "error");
  } finally {
    setFormBusy(form, false);
  }
}

async function init() {
  dashboard.init();
  refreshButton.addEventListener("click", refresh);
  document.getElementById("empty-refresh").addEventListener("click", refresh);
  document.getElementById("auth-form").addEventListener("submit", submitAuth);
  document.getElementById("auth-switch").addEventListener("click", () => {
    setAuthMode(!signupMode);
    showStatus("");
    document.getElementById("app-username").focus();
  });
  accountButton.addEventListener("click", openAccount);
  document.getElementById("back-button").addEventListener("click", () => {
    showDashboard();
    showStatus("");
    accountButton.focus();
  });
  document.getElementById("garmin-form").addEventListener("submit", submitGarmin);
  document.getElementById("session-form").addEventListener("submit", submitSession);
  document.getElementById("signout-button").addEventListener("click", signOut);
  await loadDashboard();
}

window.addEventListener("DOMContentLoaded", init);
