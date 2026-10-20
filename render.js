/* View builders. Each function returns an HTML string; app.js puts it on the
   page and wires up events. Widths are passed through data-w attributes and
   applied with JavaScript afterwards, because the page's security policy
   blocks inline style attributes. */

"use strict";

const View = (() => {
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => "$" + Math.round(n || 0).toLocaleString("en-US");
  const pct = (x, digits = 0) => (x == null ? "n/a" : (x * 100).toFixed(digits) + "%");
  const plural = (n, word, many) => `${n} ${n === 1 ? word : (many || word + "s")}`;
  const longDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  const shortDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const dow = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "short" });

  const LOADER = `
    <svg class="loader-mark" viewBox="0 0 120 120" role="img" aria-label="Working">
      <path class="delta-shadow" d="M60 14 L106 94 L14 94 Z"/>
      <path class="delta-outer" d="M60 14 L106 94 L14 94 Z"/>
      <path class="delta-inner" d="M60 52 L76 80 L44 80 Z"/>
    </svg>`;

  const STAGES = [
    ["read", "Reading your file"],
    ["clean", "Leaving out names and phone numbers"],
    ["features", "Looking at each patient's history"],
    ["check", "Testing on your most recent visits"],
    ["train", "Learning your practice's patterns"],
    ["score", "Scoring upcoming visits"],
    ["plan", "Building the staffing plan"],
  ];

  function start() {
    return `
    <section class="screen start">
      <h1>See who is likely to miss, and staff the day to match.</h1>
      <p class="lede">Drop in an appointment export from your practice software. Everything is worked out on this computer and nothing is uploaded anywhere.</p>

      <div class="start-grid">
        <div>
          <label class="dropzone" id="dropzone">
            <span class="book-lines" aria-hidden="true">
              <span class="b"></span><span></span><span class="b"></span><span></span>
              <span></span><span class="r"></span><span class="b"></span><span class="b"></span>
              <span class="b"></span><span></span><span></span><span class="b"></span>
              <span></span><span class="b"></span><span class="r"></span><span></span>
            </span>
            <h2>Drop your appointment export here</h2>
            <p>Use a list that covers at least the last six months plus the days you want to plan. More history gives better estimates.</p>
            <span class="btn">Choose a file</span>
            <input type="file" id="fileInput" accept=".csv,.txt,.tsv,.xlsx,.xlsm" aria-label="Choose an appointment export">
            <p class="formats">CSV or Excel (.xlsx) from Dentrix, Open Dental, Eaglesoft, Curve, Denticon or any system that can export a list.</p>
          </label>
          <p class="privacy-line">Patient names, phone numbers, emails and addresses are skipped when the file is read. Results show patients only as numbers (Patient 1, Patient 2). Closing this window or clicking Start over clears everything.</p>
        </div>

        <div class="side">
          <div class="block">
            <h3>What the export needs</h3>
            <ol>
              <li>A patient or chart number</li>
              <li>The appointment date and time</li>
              <li>The appointment status, such as complete, broken or scheduled</li>
            </ol>
            <p class="small muted">Procedure, insurance, booked-on date, length and fee make the results sharper, but they are optional. Column names don't matter; the app works them out.</p>
            <p class="small"><a href="docs/EXPORTING_YOUR_DATA.md" id="exportHelp">How to export from your practice software</a></p>
          </div>
          <div class="block">
            <h3>No file handy?</h3>
            <p class="muted small">Two made-up practices are included so you can see how it works.</p>
            <div class="sample-row">
              <button class="btn quiet" data-sample="forecast">Plan the next two weeks</button>
              <button class="btn quiet" data-sample="check">Check last week against what happened</button>
            </div>
          </div>
        </div>
      </div>
    </section>`;
  }

  function loading(fileName) {
    return `
    <section class="screen loading" aria-live="polite">
      <div>
        ${LOADER}
        <p class="loading-text" id="loadText">Getting started</p>
        <p class="loading-file">${esc(fileName)}</p>
        <div class="progress" aria-hidden="true"><span id="loadBar"></span></div>
        <ol class="stages" id="stages">
          ${STAGES.map(([k, t]) => `<li data-stage="${k}">${t}</li>`).join("")}
        </ol>
      </div>
    </section>`;
  }

  function error(message) {
    return `
    <section class="screen">
      <h1>That file didn't work.</h1>
      <div class="error-box"><p>${esc(message)}</p></div>
      <div class="map-actions">
        <button class="btn" data-action="restart">Try another file</button>
        <a class="btn quiet" href="docs/USER_GUIDE.md#if-something-goes-wrong">Troubleshooting</a>
      </div>
    </section>`;
  }

  function mapping(m) {
    const order = ["patient_id", "appt_datetime", "appt_date", "appt_time", "status", "procedure",
      "date_scheduled", "lead_time_days", "birthdate", "age", "insurance", "fee", "provider", "operatory", "duration_min"];
    const opts = (sel) => [`<option value="">Not in this file</option>`]
      .concat(m.headers.map((h) => `<option value="${esc(h)}"${h === sel ? " selected" : ""}>${esc(h)}</option>`)).join("");
    return `
    <section class="screen">
      <h1>Match up a few columns.</h1>
      <p class="lede">${esc(m.message)}</p>
      ${m.hidden_headers.length ? `<p class="notice check">These columns look like names or contact details, so they are never read and can't be picked: ${m.hidden_headers.map(esc).join(", ")}.</p>` : ""}
      <form id="mapForm" class="map-list">
        ${order.map((f) => `
          <div class="map-row">
            <label for="map_${f}">${esc(m.fields[f])}${m.required.includes(f) ? `<span class="req">needed</span>` : (f === "appt_datetime" || f === "appt_date") ? `<span class="req">this or the ${f === "appt_date" ? "row above" : "row below"}</span>` : ""}</label>
            <select id="map_${f}" name="${f}">${opts(m.detected[f])}</select>
          </div>`).join("")}
      </form>
      <p class="small muted">If your file has one column with both date and time, pick it for "Appointment date and time" and leave the separate date and time empty.</p>
      <div class="map-actions">
        <button class="btn" data-action="run-mapping">Analyze with these columns</button>
        <button class="btn quiet" data-action="restart">Use a different file</button>
      </div>
    </section>`;
  }

  /* ---------------- results ---------------- */

  function results(r, ui) {
    const meta = r.meta;
    const days = r.days;
    const day = days.find((d) => d.date === ui.day) || days[0];
    const backtest = meta.mode === "backtest";
    const span = days.length ? `${shortDate(days[0].date)} to ${shortDate(days[days.length - 1].date)}` : "";
    return `
    <section class="screen results">
      <div class="result-head">
        <div>
          <h1>${backtest ? "How last week would have looked" : `${plural(days.length, "day")} planned`}</h1>
          <p class="lede">${esc(meta.file_name)}. ${meta.history_visits.toLocaleString()} past visits from ${shortDate(meta.history_from)} to ${shortDate(meta.history_to)} were used to learn; ${meta.upcoming_visits.toLocaleString()} visits ${backtest ? "were scored" : "scored"} for ${span}.</p>
        </div>
        <div class="result-actions">
          <button class="btn quiet" data-action="print">Print huddle sheet</button>
          <button class="btn quiet" data-action="settings">Settings</button>
          <button class="btn" data-action="restart">Start over</button>
        </div>
      </div>
      ${backtest ? `<p class="notice check">Every visit in this file already has an outcome, so the last ${plural(days.length, "working day")} were held back and predicted as if they hadn't happened yet. Compare the predictions with the Outcome column to judge whether the tool works for this practice.</p>` : ""}
      ${meta.warnings.map((w) => `<p class="notice">${esc(w)}</p>`).join("")}
      ${r.quality.method === "simple" ? `<p class="notice">${esc(r.quality.method_note)}</p>` : ""}

      <div class="days" role="tablist" aria-label="Days">
        ${days.map((d) => dayTab(d, day, days)).join("")}
      </div>

      ${daySummary(day, r, backtest)}
      ${daySheet(day)}
      ${patientSection(r, day, ui, backtest)}
      ${reliability(r)}
      ${patterns(r)}
      ${columns(meta)}
    </section>`;
  }

  function dayTab(d, current, days) {
    const max = Math.max(...days.map((x) => x.expected_misses), 1);
    return `
      <button class="day" role="tab" aria-selected="${d.date === current.date}" data-day="${d.date}">
        <span class="d1">${dow(d.date)}</span>
        <span class="d2">${shortDate(d.date)}</span>
        <span class="meter"><i data-w="${(100 * d.expected_misses / max).toFixed(1)}"></i></span>
        <span class="d3">${d.expected_misses.toFixed(1)} likely misses</span>
      </button>`;
  }

  function staffRow(role, s) {
    const changed = s.recommended < s.booked;
    return `
      <div class="staff-row">
        <span class="role">${role}</span>
        <span class="num ${changed ? "was" : "same"}" title="Needed if everyone shows up">${s.booked}</span>
        <span class="num" title="Likely needed">${s.recommended}</span>
      </div>`;
  }

  function daySummary(d, r, backtest) {
    const actual = backtest ? r.patients.filter((p) => p.date === d.date && p.outcome === "Missed").length : null;
    return `
      <div class="summary">
        <div>
          <p class="summary-sentence">${longDate(d.date)}: <strong>${plural(d.visits, "visit")}</strong>. Expect about <strong>${Math.round(d.expected_misses)} no-show${Math.round(d.expected_misses) === 1 ? "" : "s"}</strong> <span class="range">(likely ${d.misses_low} to ${d.misses_high})</span>. ${money(d.production_at_risk)} of ${money(d.booked_production)} booked is at risk.</p>
          ${backtest ? `<p class="lede">What really happened: <strong>${plural(actual, "patient")}</strong> missed.</p>` : ""}
          <ul class="todo">${d.suggestions.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
        </div>
        <div>
          <div class="staff-head"><span>Team on the floor</span><span>If all show</span><span>Likely need</span></div>
          <div class="staff">
            ${staffRow("Hygienists", d.hygienists)}
            ${staffRow("Dental assistants", d.assistants)}
            ${staffRow("Front desk", d.front_desk)}
          </div>
          <p class="small muted">Planned for a day busier than ${Math.round(r.settings.planning_confidence * 100)}% of likely outcomes, so you are rarely caught short.</p>
        </div>
      </div>`;
  }

  function daySheet(d) {
    const peak = Math.max(...d.hours.map((h) => h.chairs_booked), 1);
    return `
      <section class="section">
        <div class="section-head">
          <div>
            <h2>Hour by hour</h2>
            <p>Outlined bars are chairs booked. Filled bars are chairs likely to have a patient in them. Hours marked in red are the best places to double-book or call the ASAP list.</p>
          </div>
        </div>
        <div class="sheet" role="table" aria-label="Hour by hour plan">
          <div class="sheet-row head" role="row">
            <span role="columnheader">Hour</span><span role="columnheader">Chairs in use</span>
            <span role="columnheader" class="empty-min">Empty min.</span>
            <span role="columnheader">Staff needed</span><span role="columnheader">Note</span>
          </div>
          ${d.hours.map((h) => `
            <div class="sheet-row" role="row">
              <span class="hour" role="cell">${h.label}</span>
              <span class="chairs" role="cell" aria-label="${h.chairs_booked} chairs booked, ${h.chairs_expected} likely filled">
                <span class="booked" data-w="${(100 * h.chairs_booked / peak).toFixed(1)}"></span>
                <span class="likely" data-w="${(100 * h.chairs_expected / peak).toFixed(1)}"></span>
              </span>
              <span class="empty-min ${h.flag ? "hot" : ""}" role="cell">${Math.round(h.empty_minutes)}</span>
              <span class="staff-mini" role="cell">${h.hygienists} hyg, ${h.assistants} asst</span>
              <span role="cell">${h.flag ? `<span class="flag">Double-book here</span>` : h.starting ? `<span class="muted">${plural(h.starting, "visit")} start</span>` : ""}</span>
            </div>`).join("")}
        </div>
        <div class="legend"><span><i class="lb"></i>Booked</span><span><i class="ll"></i>Likely filled</span></div>
      </section>`;
  }

  function patientRows(rows, backtest) {
    if (!rows.length) return `<tr><td colspan="${backtest ? 8 : 7}" class="empty-state">No visits match this filter.</td></tr>`;
    return rows.map((p) => `
      <tr>
        <td class="pt">Patient ${p.patient}</td>
        <td class="when">${p.time}</td>
        <td>${esc(p.visit)}</td>
        <td>${esc(p.provider)}</td>
        <td><span class="chance"><span class="pct">${Math.round(p.chance * 100)}%</span><span class="track"><span class="fill ${p.tier}" data-w="${Math.min(100, p.chance * 200).toFixed(1)}"></span></span></span></td>
        <td><span class="tier ${p.tier}">${p.tier}</span></td>
        <td class="why">${p.why.length ? p.why.map((w) => `<span>${esc(w)}</span>`).join("") : `<span class="muted">Nothing stands out</span>`}</td>
        ${backtest ? `<td class="outcome-${p.outcome}">${p.outcome}</td>` : ""}
      </tr>`).join("");
  }

  function filterPatients(r, day, ui) {
    let rows = r.patients.filter((p) => ui.allDays || p.date === day.date);
    if (ui.tier !== "All") rows = rows.filter((p) => p.tier === ui.tier);
    if (ui.find) {
      const n = ui.find.replace(/\D/g, "");
      if (n) rows = rows.filter((p) => String(p.patient) === n);
    }
    if (ui.sort === "chance") rows = rows.slice().sort((a, b) => b.chance - a.chance);
    return rows;
  }

  function patientSection(r, day, ui, backtest) {
    const rows = filterPatients(r, day, ui);
    const shown = rows.slice(0, ui.limit);
    const counts = { All: 0, High: 0, Medium: 0, Low: 0 };
    r.patients.filter((p) => ui.allDays || p.date === day.date).forEach((p) => { counts.All++; counts[p.tier]++; });
    return `
      <section class="section" id="patients">
        <div class="section-head">
          <div>
            <h2>Visits and who to call</h2>
            <p>Patients appear as numbers only. To see who Patient 12 is, use the private lookup file on this computer.</p>
          </div>
          <div class="result-actions no-print">
            <a class="btn quiet" href="/api/jobs/${ui.job}/call-list.csv${ui.tier !== "All" ? "?tier=" + ui.tier : ""}" download>Download this list</a>
            <button class="btn link" data-action="key">Get the private lookup file</button>
          </div>
        </div>
        <div class="controls">
          <div class="seg" role="group" aria-label="Risk filter">
            ${["All", "High", "Medium", "Low"].map((t) => `<button data-tier="${t}" aria-pressed="${ui.tier === t}">${t} (${counts[t]})</button>`).join("")}
          </div>
          <div class="seg" role="group" aria-label="Sort">
            <button data-sort="time" aria-pressed="${ui.sort === "time"}">By time</button>
            <button data-sort="chance" aria-pressed="${ui.sort === "chance"}">Most likely to miss</button>
          </div>
          <label class="small"><input type="checkbox" id="allDays" ${ui.allDays ? "checked" : ""}> All days</label>
          <input class="find" id="find" type="search" inputmode="numeric" placeholder="Patient number" value="${esc(ui.find)}" aria-label="Find a patient number">
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th>Patient</th><th>${ui.allDays ? "When" : "Time"}</th><th>Visit</th><th>Provider</th>
              <th>Chance of missing</th><th>Risk</th><th>Why</th>${backtest ? "<th>Outcome</th>" : ""}
            </tr></thead>
            <tbody id="ptBody">${patientRows(shown.map((p) => ui.allDays ? { ...p, time: `${shortDate(p.date)}, ${p.time}` } : p), backtest)}</tbody>
          </table>
        </div>
        ${rows.length > shown.length ? `<button class="btn quiet more" data-action="more">Show ${Math.min(200, rows.length - shown.length)} more of ${rows.length - shown.length}</button>` : ""}
        <div class="script-box no-print">
          <p class="small muted">Reminder script for high-risk patients (fill in the name from your system):</p>
          <p class="script">"Hi [first name], this is ${esc(r.settings.practice_name)} calling to confirm your visit on [day] at [time]. If that time doesn't work anymore, we can find you a better one right now."</p>
        </div>
      </section>`;
  }

  function reliability(r) {
    const q = r.quality;
    if (q.method !== "model" || q.auc == null) {
      return `
      <section class="section reliability">
        <h2>How reliable is this</h2>
        <p class="lede">${esc(q.method_note || "There wasn't enough recent history to run a fair test of the model, so treat these numbers as rough.")}</p>
      </section>`;
    }
    const tiers = q.tiers || [];
    const lowT = tiers.find((t) => t.tier === "Low") || {};
    const highT = tiers.find((t) => t.tier === "High") || {};
    return `
      <section class="section reliability">
        <div class="section-head"><div>
          <h2>How reliable is this</h2>
          <p>The model was trained on visits before ${shortDate(q.test_from)}, then asked to predict the ${q.test_visits.toLocaleString()} visits after that, which it had never seen.</p>
        </div></div>
        <div class="two-col">
          <div>
            <div class="facts">
              <div><p class="big-number">${pct(highT.actual)}</p><p class="small">of patients rated High actually missed</p></div>
              <div><p class="big-number">${pct(lowT.actual)}</p><p class="small">of patients rated Low actually missed</p></div>
              <div><p class="big-number">${pct(q.top_tenth_miss_rate)}</p><p class="small">miss rate in the riskiest tenth of visits, against ${pct(q.test_miss_rate)} overall</p></div>
              <div><p class="big-number">${q.auc.toFixed(2)}</p><p class="small">ranking score. 0.50 is a coin flip and 1.00 is perfect; 0.65 to 0.80 is common for no-show models</p></div>
            </div>
          </div>
          <div>
            <table class="tier-table">
              <thead><tr><th>Risk</th><th>Visits in test</th><th>Predicted to miss</th><th>Actually missed</th></tr></thead>
              <tbody>${tiers.map((t) => `<tr><td><span class="tier ${t.tier}">${t.tier}</span></td><td>${t.visits.toLocaleString()}</td><td>${pct(t.predicted, 1)}</td><td>${pct(t.actual, 1)}</td></tr>`).join("")}</tbody>
            </table>
            <p class="small muted">When the last two columns are close, the percentages can be taken at face value.</p>
          </div>
        </div>
      </section>`;
  }

  function patterns(r) {
    if (!r.patterns.length) return "";
    const base = r.quality.base_rate || 0;
    return `
      <section class="section patterns">
        <div class="section-head"><div>
          <h2>What drives misses at this practice</h2>
          <p>Straight averages from your own history. The red tick marks the practice-wide rate of ${pct(base, 1)}.</p>
        </div></div>
        <div class="two-col">
          ${[0, 1].map((col) => `<div>${r.patterns.filter((_, i) => i % 2 === col).map((p) => {
            const max = Math.max(...p.rows.map((x) => x.rate), base) * 1.1 || 1;
            return `
              <div class="pattern">
                <h3>${esc(p.title)}</h3>
                ${p.rows.map((x) => `
                  <div class="prow">
                    <span>${esc(x.label)}</span>
                    <span class="pbar" title="${x.visits.toLocaleString()} visits"><i data-w="${(100 * x.rate / max).toFixed(1)}"></i><b data-l="${(100 * base / max).toFixed(1)}"></b></span>
                    <span class="r">${pct(x.rate)}</span>
                  </div>`).join("")}
              </div>`;
          }).join("")}</div>`).join("")}
        </div>
      </section>`;
  }

  function columns(meta) {
    const used = Object.entries(meta.columns_used);
    const status = Object.entries(meta.status_values || {});
    const label = { kept: "kept", no_show: "missed", cancelled: "cancelled (ignored)", scheduled: "upcoming", unknown: "not recognized (ignored)" };
    return `
      <details class="columns">
        <summary>Columns read from your file</summary>
        <dl>
          ${used.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}
          <dt>Never read</dt><dd>${meta.columns_not_read.length ? meta.columns_not_read.map(esc).join(", ") : "None found"}</dd>
          ${status.length ? `<dt>Status values</dt><dd>${status.map(([k, v]) => `${esc(k)}: ${label[v] || v}`).join("; ")}</dd>` : ""}
          <dt>Fees</dt><dd>${meta.fees_from_file ? "From your file" : "Typical fees by visit type (change them in Settings)"}</dd>
          <dt>Visit lengths</dt><dd>${meta.lengths_from_file ? "From your file" : "Typical lengths by visit type (change them in Settings)"}</dd>
          <dt>Time taken</dt><dd>${meta.seconds} seconds</dd>
        </dl>
        <button class="btn quiet" data-action="remap">Fix the column matching</button>
      </details>`;
  }

  function settings(s, meta) {
    const num = (key, label, hint, step, scale = 1, suffix = "") => `
      <label class="field"><span>${label}${hint ? `<span class="hint">${hint}</span>` : ""}</span>
        <input type="number" name="${key}" step="${step}" value="${+(s[key] * scale).toFixed(2)}" data-scale="${scale}" aria-label="${label}${suffix}">
      </label>`;
    const dict = (key, title, hint, unit) => `
      <fieldset><legend>${title}</legend>${hint ? `<p class="small muted">${hint}</p>` : ""}
        ${Object.entries(s[key]).map(([cat, v]) => `
          <label class="field"><span>${esc(cat)}</span><input type="number" step="1" min="0" data-dict="${key}" name="${esc(cat)}" value="${v}" aria-label="${esc(cat)} ${unit}"></label>`).join("")}
      </fieldset>`;
    return `
      <h2 id="settingsTitle">Settings</h2>
      <p class="small muted">Changes apply right away. The model is not retrained, so this takes a moment at most.</p>
      <form id="settingsForm">
        <fieldset><legend>Risk levels</legend>
          ${num("medium_risk", "Medium starts at", "Chance of missing, in %", 1, 100)}
          ${num("high_risk", "High starts at", "Chance of missing, in %", 1, 100)}
        </fieldset>
        <fieldset><legend>Staffing</legend>
          ${num("shift_hours", "Shift length", "Hours", 0.5)}
          ${num("target_busy_share", "Chairside share of a shift", "In %, the rest is setup, breaks and notes", 1, 100)}
          ${num("assistants_per_doctor", "Assistants per dentist", "When the dentist is with a patient", 0.5)}
          ${num("patients_per_front_desk", "Patients per front desk person", "Per day", 1)}
          ${num("planning_confidence", "Plan for a day busier than", "In %. Higher means fewer surprises and more staff", 1, 100)}
          ${num("empty_minutes_to_flag", "Mark an hour for double-booking at", "Likely empty chair minutes", 5)}
        </fieldset>
        <fieldset><legend>Practice</legend>
          <label class="field"><span>Name used in the call script</span><input type="text" name="practice_name" value="${esc(s.practice_name)}"></label>
        </fieldset>
        ${meta.fees_from_file ? "" : dict("default_fee", "Fees by visit type", "Your file has no fee column, so these are used for money at risk.", "fee in dollars")}
        ${meta.lengths_from_file ? "" : dict("default_minutes", "Visit lengths", "Your file has no length column, so these are used for chair time.", "minutes")}
        <div class="drawer-actions">
          <button class="btn" type="submit">Apply</button>
          <button class="btn quiet" type="button" data-action="close-settings">Close</button>
        </div>
      </form>`;
  }

  return { start, loading, error, mapping, results, settings, patientRows, filterPatients, STAGES, esc };
})();
