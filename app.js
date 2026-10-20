/* Chair Forecast front end. Talks only to the local server (same origin). */

"use strict";

(() => {
  const app = document.getElementById("app");
  const veil = document.getElementById("dropVeil");
  const drawer = document.getElementById("settings");

  const state = {
    screen: "start",
    job: null,
    result: null,
    fileName: "",
    pollTimer: null,
    startedAt: 0,
    ui: { day: null, tier: "All", sort: "time", find: "", allDays: false, limit: 200, job: null },
  };

  /* ---------------- helpers ---------------- */

  function applySizes(root = app) {
    root.querySelectorAll("[data-w]").forEach((el) => { el.style.width = el.dataset.w + "%"; });
    root.querySelectorAll("[data-l]").forEach((el) => { el.style.left = el.dataset.l + "%"; });
  }

  function show(html, focus = true) {
    app.innerHTML = html;
    applySizes();
    if (focus) app.focus({ preventScroll: true });
  }

  async function api(path, options = {}) {
    const res = await fetch(path, options);
    let body = {};
    try { body = await res.json(); } catch (_) { /* not json */ }
    if (!res.ok) throw new Error(body.error || `The app stopped responding (code ${res.status}). Close it and start it again.`);
    return body;
  }

  /* ---------------- screens ---------------- */

  function goStart() {
    stopPolling();
    if (state.job) fetch(`/api/jobs/${state.job}`, { method: "DELETE" }).catch(() => {});
    state.job = null;
    state.result = null;
    state.screen = "start";
    closeSettings();
    show(View.start(), false);
    window.scrollTo(0, 0);
  }

  function goLoading(name) {
    state.screen = "loading";
    state.fileName = name;
    state.startedAt = performance.now();
    show(View.loading(name));
  }

  function goError(message) {
    stopPolling();
    state.screen = "error";
    show(View.error(message));
  }

  function goResults(result) {
    state.screen = "results";
    state.result = result;
    if (!state.ui.day || !result.days.some((d) => d.date === state.ui.day)) {
      state.ui.day = result.days.length ? result.days[0].date : null;
    }
    state.ui.job = state.job;
    if (!result.days.length) {
      goError("No upcoming visits were found to plan. Check that the export includes the days you want to staff.");
      return;
    }
    renderResults(true);
  }

  function renderResults(focus = false) {
    const y = window.scrollY;
    show(View.results(state.result, state.ui), focus);
    if (!focus) window.scrollTo(0, y);
  }

  /* ---------------- running an analysis ---------------- */

  async function analyzeFile(file) {
    if (!file) return;
    const ok = /\.(csv|txt|tsv|tab|xlsx|xlsm)$/i.test(file.name);
    if (!ok) {
      goError(`${file.name} isn't a file type this app reads. Export a CSV or an Excel .xlsx file from your practice software.`);
      return;
    }
    goLoading(file.name);
    const form = new FormData();
    form.append("file", file);
    try {
      const { job } = await api("/api/analyze", { method: "POST", body: form });
      state.job = job;
      poll();
    } catch (e) {
      goError(e.message);
    }
  }

  async function analyzeSample(which) {
    goLoading(which === "forecast" ? "Sample practice, upcoming two weeks" : "Sample practice, last week checked");
    try {
      const { job } = await api(`/api/analyze?sample=${which}`, { method: "POST" });
      state.job = job;
      poll();
    } catch (e) {
      goError(e.message);
    }
  }

  function stopPolling() {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }

  function updateLoader(body) {
    const text = document.getElementById("loadText");
    const bar = document.getElementById("loadBar");
    const list = document.getElementById("stages");
    if (!text || !list) return;
    text.textContent = body.text || "Working";
    if (bar) bar.style.width = (body.pct || 0) + "%";
    const order = View.STAGES.map((s) => s[0]);
    const at = order.indexOf(body.stage);
    list.querySelectorAll("li").forEach((li, i) => {
      li.classList.toggle("done", at > i || body.stage === "done");
      li.classList.toggle("now", at === i);
    });
  }

  async function poll() {
    stopPolling();
    try {
      const body = await api(`/api/jobs/${state.job}`);
      updateLoader(body);
      if (body.stage === "done") {
        // Let the delta finish at least one full turn so a fast run doesn't flash.
        const wait = Math.max(0, 1300 - (performance.now() - state.startedAt));
        state.pollTimer = setTimeout(() => goResults(body.result), wait);
        return;
      }
      if (body.stage === "error") return goError(body.error);
      if (body.stage === "mapping") {
        state.screen = "mapping";
        show(View.mapping(body.mapping));
        return;
      }
      state.pollTimer = setTimeout(poll, 300);
    } catch (e) {
      goError(e.message);
    }
  }

  async function runWithMapping() {
    const form = document.getElementById("mapForm");
    const mapping = {};
    new FormData(form).forEach((v, k) => { if (v) mapping[k] = v; });
    goLoading(state.fileName || "Your file");
    try {
      const { job } = await api(`/api/jobs/${state.job}/mapping`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mapping }),
      });
      state.job = job;
      poll();
    } catch (e) {
      goError(e.message);
    }
  }

  async function showMappingAgain() {
    try {
      const body = await api(`/api/jobs/${state.job}/mapping`);
      state.screen = "mapping";
      closeSettings();
      show(View.mapping(body.mapping));
      window.scrollTo(0, 0);
    } catch (e) {
      goError(e.message);
    }
  }

  /* ---------------- settings ---------------- */

  let scrim = null;
  let lastFocus = null;

  function openSettings() {
    lastFocus = document.activeElement;
    drawer.innerHTML = View.settings(state.result.settings, state.result.meta);
    drawer.hidden = false;
    scrim = document.createElement("div");
    scrim.className = "scrim";
    scrim.addEventListener("click", closeSettings);
    document.body.appendChild(scrim);
    drawer.querySelector("input")?.focus();
  }

  function closeSettings() {
    drawer.hidden = true;
    drawer.innerHTML = "";
    scrim?.remove();
    scrim = null;
    lastFocus?.focus?.();
  }

  async function saveSettings(form) {
    const body = {};
    form.querySelectorAll("input[name]").forEach((input) => {
      if (input.dataset.dict) {
        body[input.dataset.dict] = body[input.dataset.dict] || {};
        body[input.dataset.dict][input.name] = Number(input.value);
      } else if (input.type === "number") {
        body[input.name] = Number(input.value) / Number(input.dataset.scale || 1);
      } else {
        body[input.name] = input.value;
      }
    });
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    btn.textContent = "Applying";
    try {
      const { result } = await api(`/api/jobs/${state.job}/settings`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      state.result = result;
      closeSettings();
      renderResults();
    } catch (e) {
      btn.disabled = false;
      btn.textContent = "Apply";
      alert(e.message);
    }
  }

  /* ---------------- events ---------------- */

  app.addEventListener("change", (e) => {
    if (e.target.id === "fileInput") analyzeFile(e.target.files[0]);
    if (e.target.id === "allDays") {
      state.ui.allDays = e.target.checked;
      state.ui.limit = 200;
      renderResults();
    }
  });

  let findTimer = null;
  app.addEventListener("input", (e) => {
    if (e.target.id !== "find") return;
    clearTimeout(findTimer);
    findTimer = setTimeout(() => {
      state.ui.find = e.target.value;
      renderResults();
      const box = document.getElementById("find");
      box.focus();
      box.setSelectionRange(box.value.length, box.value.length);
    }, 200);
  });

  app.addEventListener("click", (e) => {
    const t = e.target.closest("button, a");
    if (!t) return;
    if (t.dataset.sample) return analyzeSample(t.dataset.sample);
    if (t.dataset.day) {
      state.ui.day = t.dataset.day;
      state.ui.limit = 200;
      return renderResults();
    }
    if (t.dataset.tier) {
      state.ui.tier = t.dataset.tier;
      state.ui.limit = 200;
      return renderResults();
    }
    if (t.dataset.sort) {
      state.ui.sort = t.dataset.sort;
      return renderResults();
    }
    switch (t.dataset.action) {
      case "restart": return goStart();
      case "run-mapping": return runWithMapping();
      case "remap": return showMappingAgain();
      case "settings": return openSettings();
      case "print": return window.print();
      case "more":
        state.ui.limit += 200;
        return renderResults();
      case "key":
        if (confirm("The lookup file links each patient number to the chart number in your practice software. Keep it on this computer and delete it when you're done. Download it?")) {
          window.location.href = `/api/jobs/${state.job}/patient-key.csv`;
        }
        return;
      default:
    }
  });

  // Arrow keys move between day tabs.
  app.addEventListener("keydown", (e) => {
    const tab = e.target.closest?.(".day");
    if (!tab || !["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    const tabs = [...app.querySelectorAll(".day")];
    const i = tabs.indexOf(tab) + (e.key === "ArrowRight" ? 1 : -1);
    if (tabs[i]) {
      state.ui.day = tabs[i].dataset.day;
      renderResults();
      app.querySelector(`.day[data-day="${state.ui.day}"]`)?.focus();
    }
  });

  drawer.addEventListener("submit", (e) => {
    e.preventDefault();
    saveSettings(e.target);
  });
  drawer.addEventListener("click", (e) => {
    if (e.target.closest("[data-action=close-settings]")) closeSettings();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !drawer.hidden) closeSettings();
  });

  // Drop anywhere on the page, not just the box.
  let dragDepth = 0;
  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
  window.addEventListener("dragenter", (e) => {
    if (!hasFiles(e) || state.screen === "loading") return;
    e.preventDefault();
    dragDepth++;
    veil.hidden = false;
    document.getElementById("dropzone")?.classList.add("over");
  });
  window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) {
      veil.hidden = true;
      document.getElementById("dropzone")?.classList.remove("over");
    }
  });
  window.addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth = 0;
    veil.hidden = true;
    if (state.screen === "loading") return;
    if (state.job) fetch(`/api/jobs/${state.job}`, { method: "DELETE" }).catch(() => {});
    analyzeFile(e.dataTransfer.files[0]);
  });

  // Forget the data when the window closes.
  window.addEventListener("pagehide", () => {
    if (state.job) navigator.sendBeacon?.(`/api/jobs/${state.job}/forget`);
  });

  goStart();
})();
