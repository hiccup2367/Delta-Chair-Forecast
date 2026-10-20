# Front end

The interface is three files in `web/`, plus an icon:

| File | Job |
| --- | --- |
| `index.html` | The page shell: top bar, the `<main id="app">` that screens are drawn into, the drop overlay and the settings drawer |
| `styles.css` | All styling, including dark mode, small screens and the print layout |
| `render.js` | Pure functions that turn data into HTML strings, one per screen or section |
| `app.js` | State, talking to the local server, and every event handler |
| `favicon.svg` | Browser tab icon |

There is no framework, build step or package manager. Edit a file, refresh the browser. That's a deliberate choice: an office manager's computer should not need Node.js, and nothing in the interface should be fetched from the internet.

## Design

The look comes from the operatory rather than from a dashboard template.

- Color: cool tray-paper grey background (`--paper`), slate ink (`--ink`), and three risk colors: carmine for High, amber for Medium, sage for Low. Every risk color is paired with a word, so nothing depends on telling red from green.
- Type: one serif (Charter, falling back to Sitka or Cambria on Windows and Georgia elsewhere) for headings, the day summary and big numbers; one sans (Avenir Next or Segoe UI) for everything else. Both are system fonts, so nothing is downloaded. Numbers use tabular figures so columns line up.
- Layout: left-aligned, generous margins, rules instead of boxes. The hour-by-hour view is drawn like the left edge of an appointment book on purpose, because that's the picture front desk staff already have in their heads.
- The one bit of showmanship is the loader (below). Everything else stays quiet.

Copy follows the same rule. Buttons say what happens ("Download this list", "Start over"). Errors say what went wrong and what to do. Labels avoid model jargon: "ranking score" instead of AUC, "chance of missing" instead of probability.

## The delta loader

The loader is a stylized delta drawn inline in `render.js` (`LOADER`) and animated in `styles.css`:

- A faint triangle (`.delta-shadow`) sits behind as a track.
- The outline (`.delta-outer`) has one gap cut into it with `stroke-dasharray`, which makes its rotation visible. It turns in three 120-degree steps with a pause after each (`@keyframes delta-turn`), like a dial clicking into place.
- The solid inner wedge (`.delta-inner`) turns the opposite way and dips slightly in scale between steps (`@keyframes delta-settle`).
- Both rotate around the triangle's centroid, (60, 67.33) in the 120 × 120 view box, set with `transform-box: view-box`.
- With "reduce motion" turned on in the operating system, both simply fade in and out instead.

A full cycle is 3.6 seconds. When a run finishes very quickly, `app.js` waits until the loader has been on screen 1.3 seconds so the screen doesn't flash.

To change the speed, edit the `3.6s` in both animation lines. To change the shape, edit the three path strings in `LOADER` and the matching ones in `index.html` (top bar) and keep the centroid in `transform-origin` in step.

## Screens and state

`app.js` keeps one `state` object and redraws the current screen from it. Screens:

| Screen | Drawn by | Shown when |
| --- | --- | --- |
| Start | `View.start()` | First load, or after Start over |
| Loading | `View.loading(name)` | While the server works; updated in place every 300 ms |
| Column matching | `View.mapping(payload)` | The server couldn't find a required column, or the person clicked "Fix the column matching" |
| Results | `View.results(result, ui)` | The run finished |
| Error | `View.error(message)` | Anything the person needs to fix |

`state.ui` holds view choices (selected day, risk filter, sort, search, all-days toggle, rows shown). Changing any of them calls `renderResults()`, which redraws and keeps the scroll position.

Big lists render 200 rows at a time with a "Show more" button, so a 5,000-visit plan doesn't freeze the page.

## Why widths are set with JavaScript

The server sends a strict Content Security Policy that forbids inline `style="..."` attributes. Bars therefore carry their size as `data-w` (width in %) or `data-l` (left in %), and `applySizes()` in `app.js` sets them after each render through the DOM, which the policy allows. Keep to this pattern when adding charts; an inline style will silently do nothing.

For the same reason there are no inline scripts or event attributes (`onclick`). Events are handled by delegation on `#app` in `app.js`, keyed off `data-action`, `data-day`, `data-tier`, `data-sort` and `data-sample` attributes.

## Server endpoints the page uses

All on the same origin (`http://127.0.0.1:<port>`).

| Method and path | Purpose |
| --- | --- |
| `POST /api/analyze` | Body: multipart `file`. Or `?sample=forecast` / `?sample=check` with no body. Returns `{job}`. |
| `GET /api/jobs/<job>` | `{stage, text, pct}` while running; adds `result`, `error` or `mapping` at the end. Stages: read, clean, features, check, train, score, plan, done. |
| `GET /api/jobs/<job>/mapping` | Column matching payload for the current file |
| `POST /api/jobs/<job>/mapping` | Body `{mapping: {field: header}}`. Starts a new run; returns `{job}`. |
| `POST /api/jobs/<job>/settings` | Body: any settings keys. Returns `{result}` with the plan rebuilt; the model isn't retrained. |
| `GET /api/jobs/<job>/call-list.csv?tier=High` | Download of the visit list, patient numbers only |
| `GET /api/jobs/<job>/patient-key.csv` | The private lookup file |
| `DELETE /api/jobs/<job>` and `POST /api/jobs/<job>/forget` | Forget the file and results. The page sends the second one when the tab closes. |
| `GET /docs/<file>` | The manuals, as plain text |

## Shape of a result

```jsonc
{
  "meta": { "mode": "forecast" | "backtest", "file_name": "...", "history_visits": 14271,
            "upcoming_visits": 386, "columns_used": {...}, "columns_not_read": [...],
            "status_values": {...}, "warnings": [...], "fees_from_file": true, "seconds": 1.35 },
  "quality": { "method": "model" | "simple", "auc": 0.69, "tiers": [{ "tier": "High", "visits": 176,
               "predicted": 0.33, "actual": 0.30 }, ...], "top_tenth_miss_rate": 0.27, ... },
  "totals": { "visits": 386, "expected_misses": 39.8, "production_at_risk": 10503, "high": 18, ... },
  "days": [{ "date": "2026-10-19", "visits": 45, "expected_misses": 5.0, "misses_low": 2, "misses_high": 8,
             "production_at_risk": 1125, "booked_production": 11620,
             "hygienists": { "booked": 5, "recommended": 4 }, "assistants": {...}, "front_desk": {...},
             "hours": [{ "label": "8 AM", "chairs_booked": 5.5, "chairs_expected": 5.0,
                         "empty_minutes": 30, "hygienists": 4, "assistants": 2, "flag": true }, ...],
             "suggestions": ["..."] }],
  "patients": [{ "patient": 1, "date": "2026-10-19", "time": "7:00 AM", "visit": "Hygiene",
                 "provider": "HYG1", "chance": 0.20, "tier": "Medium", "why": ["..."], "fee": 210,
                 "outcome": "Came" /* check mode only */ }],
  "patterns": [{ "title": "Day of the week", "rows": [{ "label": "Monday", "visits": 2801, "rate": 0.13 }] }],
  "settings": { ... }
}
```

## Accessibility

- Every interactive element is a real button, link or input, so keyboard and screen reader use work without extra code. Day tabs also respond to the left and right arrow keys.
- Focus is always visible (`:focus-visible` ring) and moves to the top of each new screen (start, loading, results, errors).
- The loader text is in an `aria-live` region, so screen readers announce each step.
- The hour-by-hour view uses table roles; bars carry an `aria-label` with the numbers.
- Colors meet contrast guidelines in both light and dark mode, and tiers are always labeled in words.
- Motion respects the "reduce motion" system setting.

## Printing

`@media print` in `styles.css` turns a results screen into a one-day huddle sheet: it hides the top bar, buttons, day tabs, reliability and pattern sections, and adds the full date as a title.

## Checking changes

1. `python run.py` and click both sample buttons.
2. Try a window about 390 px wide (phone size) and a dark system theme.
3. Turn on "reduce motion" in the operating system and check the loader.
4. Open the browser console; there should be no errors, including Content Security Policy errors.
5. `python -m pytest -q` covers the server side, including the endpoints above.
