# How the numbers are made

This page explains the method in enough detail that someone could check it. The code is short and commented, so the file names are given for each step.

## 1. Reading the file (`chairforecast/ingest.py`, `columns.py`)

The app looks at the first 30 rows of the file and picks the one that matches the most known column names as the header. That handles reports with a title and date range printed above the real table.

Headers are normalized (lowercase, letters and digits only) and compared with a list of spellings for each field: "Appt Date", "AptDateTime", "Date of Service" and so on. Exact matches win, then longer spellings are allowed to match as substrings. Anything that looks like a name or contact detail is excluded before matching starts and is never loaded; see [PRIVACY.md](PRIVACY.md).

Statuses are mapped to four outcomes: kept, missed, cancelled and upcoming. Late and same-day cancellations count as missed, because the chair still sits empty. Ordinary cancellations are left out of learning. Visits still marked scheduled but dated well before the latest known outcome are treated as stale records and dropped.

## 2. Features (`chairforecast/features.py`)

For every visit:

| Feature | How it's made |
| --- | --- |
| Lead time | Days between booking and the visit |
| Hour, weekday, month | From the appointment time |
| Age | From birth date at the time of the visit |
| Fee, length | From the file when present |
| Visit type | CDT code ranges first (D1xxx is hygiene, D3xxx is endodontics and so on), then keywords such as "prophy", "SRP", "crn", "RCT". When a visit lists several codes, the most involved procedure decides. |
| Insurance group | Carrier name grouped into PPO or commercial, HMO or DHMO, Medicaid or CHIP, and self-pay or none |
| Provider | Top 30 providers kept; the rest grouped as Other |
| Prior visits, prior misses, prior cancellations | Counts of the patient's earlier visits |
| Prior miss rate | The patient's own miss rate, shrunk toward the practice average: (misses + 3 × practice rate) / (visits + 3). A patient with one visit and one miss isn't treated as a guaranteed no-show. |
| Days since last visit | Gap to the patient's previous appointment |
| First visit | Whether the patient has any earlier recorded visit |

History features look only backwards. Visits are sorted by patient and time, and each count is a running total minus the current row. In check mode, outcomes inside the held-back week are hidden from these counts too, so the test is fair.

## 3. The model (`chairforecast/model.py`)

Scikit-learn's `HistGradientBoostingClassifier`: gradient boosted decision trees that bucket each feature into at most 255 bins. It was chosen over a random forest or plain logistic regression for three practical reasons:

- It handles missing columns and blank cells without any filling in, which matters because every practice exports something different.
- It takes categories (visit type, insurance group, provider) directly.
- It's fast on large files; see the next section.

Settings: learning rate 0.06, up to 350 trees with early stopping on larger files, 31 leaves per tree, a minimum leaf size that grows with the data, and light L2 regularization. Classes are not reweighted, so the output stays a calibrated probability rather than a score.

Columns that are blank or constant in a particular export are dropped before training.

### The honest test

Before the final model is trained, a copy is trained on the oldest 80% of past visits and asked to predict the newest 20%. Splitting by time, not at random, is what makes this honest: in real use the model always predicts the future from the past. The app reports:

- the share of High, Medium and Low patients who actually missed, next to the average predicted chance for each group (a calibration check);
- the miss rate in the riskiest tenth of visits against the overall rate;
- the ROC AUC, described on screen as a "ranking score". 0.5 means the ranking is no better than chance; 1.0 means every miss was ranked above every kept visit;
- the Brier score of the model and of a flat guess at the practice average (kept in the result data for anyone who wants it).

After the test, the final model is trained on all past visits and scores the upcoming ones.

### Small practices

With fewer than 300 past visits or fewer than 25 recorded misses, the model isn't trained. Instead each visit gets the patient's shrunk miss rate, multiplied by how much more or less often that visit type and lead-time band are missed at the practice. The app says when it does this.

### Reasons

The "Why" column is built from plain rules, not from the model's internals, so it's always readable: earlier misses, two or more cancellations, booked 45 or more days ahead, first visit, more than 18 months since the last visit, or a weekday or visit type that this practice misses at least 30% more often than average. "Has kept every recorded visit" only appears when it explains a below-average estimate.

## 4. The staffing plan (`chairforecast/staffing.py`)

For each day, with p being each visit's chance of missing:

**Expected no-shows** is the sum of p. **The likely range** comes from the exact distribution of the number of misses, which is the Poisson binomial distribution (each visit is its own coin with its own p). It's computed exactly by adding one visit at a time, and the 10th and 90th percentiles are shown.

**Production at risk** is the sum of p × fee.

**Staff.** Visits are split by who mostly works them: hygiene and periodontal visits go to hygienists; everything else to dentists, with assistants at the set ratio. For each group:

- Booked chair hours = sum of lengths.
- Expected chair hours = sum of (1 − p) × length.
- Planning chair hours = expected + z × standard deviation, where z matches the planning confidence (0.84 for 80%) and the variance is the sum of p(1 − p) × length². Never more than booked.
- People needed by hours = planning hours ÷ (shift length × chairside share).
- People needed at the busiest hour = the same calculation per hour, using how much of each visit falls inside that hour.

The recommendation is the larger of the two, and never more than the "if everyone shows" number. Front desk is planning patients ÷ patients per front desk person, minimum one.

**Double-booking hours.** For each clock hour, likely empty chair minutes = sum of p × minutes of each visit inside that hour. Hours at or above the threshold (30 minutes by default) are flagged.

## How long it takes

Here n is the number of rows, f the number of features (16), and d the number of visits on one day.

| Step | Cost | Notes |
| --- | --- | --- |
| Find header and columns | O(30 rows × headers × spellings) | A few thousand string comparisons |
| Read the file | O(n × used columns) | Unused columns are skipped by the CSV parser, so wide exports don't cost extra |
| Parse dates and times | O(n) hashing + O(u) parsing | u is the number of distinct values. A year has about 300 distinct dates and 50 distinct times, so the slow parser runs a few hundred times, not hundreds of thousands. |
| Visit type and insurance group | O(n) + O(distinct texts) | Same trick |
| Sort by patient and time | O(n log n) | The only super-linear step on the full data |
| History features | O(n) | Grouped running totals |
| Training | O(n × f × trees) | Histograms mean each tree is linear in n. Training uses at most the 400,000 most recent visits. |
| Daily miss distribution | O(d²) per day | d is under a few hundred even for big groups |
| Hour-by-hour view | O(d × hours) | About 10 hours per day |
| Changing a setting | O(visits planned) | The model isn't retrained |

Measured on a laptop with `python scripts/benchmark.py`:

```
290,624 rows, 45 MB
    0.76s  read the file
    1.69s  clean and parse dates
    0.90s  patient history features
    8.39s  honest test (train on older 80%, predict newest 20%)
    9.32s  final model on all history
    0.12s  score upcoming visits
    0.75s  reasons, anonymizing and staffing plan
Total 21.9s
```

A single practice with 18 months of history (about 15,000 visits) takes about 1.5 seconds.

## What it can't know

- Reasons that aren't in the data: weather, a snowstorm, a school holiday, a patient's car breaking down.
- Whether a confirmation call was already made, unless the export has a confirmed status. If your system records confirmations, leave them in. "Confirmed" is read as upcoming today; using it as its own signal is on the list below.
- Anything about patients the practice has never seen before, beyond the general first-visit pattern.

## Ideas for later

- Learn from confirmation status and reminder history when the export includes them.
- Add the operatory as a feature and plan by operatory as well as by role.
- Remember settings between sessions in a small local file.
- Package as a single Windows program so Python isn't needed.
