# Chair Forecast

[![tests](https://github.com/YOUR-USERNAME/delta-chair-forecast/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR-USERNAME/delta-chair-forecast/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-1d2a30)
![Runs locally](https://img.shields.io/badge/data-stays%20on%20this%20computer-3f6e5b)
![License: MIT](https://img.shields.io/badge/license-MIT-74858a)

A small tool for dental offices. You drop in an appointment export from your practice software, and it tells you two things for each upcoming day: which patients are likely to miss, and how many hygienists, assistants and front desk staff the day really needs once those likely no-shows are taken into account.

It runs entirely on the office computer. There is no cloud account, no upload and no outside service. Patient names, phone numbers, emails and addresses are skipped when the file is read, and results show patients only as Patient 1, Patient 2 and so on.

Built by Delta Consulting.

![Day plan screen](docs/images/day-plan.png)

## What it does

1. Reads CSV or Excel exports from Dentrix, Open Dental, Eaglesoft or anything else that can export an appointment list. Column names are matched automatically, and title lines above the header are skipped.
2. Learns from the practice's own past visits which ones tend to be missed. Booking lead time, the patient's own history, visit type, day and hour, age and payer all feed in.
3. Tests itself before you rely on it. It trains on the older 80% of history and predicts the most recent 20%, then shows how often the patients it called high risk actually missed.
4. Scores every upcoming visit with a chance of missing, a Low, Medium or High label, and a short reason ("Missed 2 earlier visits", "Booked 170 days ahead").
5. Plans each day: expected no-shows with a likely range, production at risk, staff needed if everyone shows versus staff likely needed, and the specific hours where double-booking or calling the ASAP list makes the most sense.

If the file has no upcoming visits, the app holds back the last five working days and predicts them as if they hadn't happened yet, so a practice can check the tool against reality before trusting it.

## Quick start

You need Python 3.10 or newer.

| System | Do this |
| --- | --- |
| Windows | Double-click `start-windows.bat` |
| macOS | Double-click `start-mac.command` (the first time, right-click it and choose Open) |
| Linux | Run `./start-linux.sh` |

The first launch sets up a private environment in a `.venv` folder, which needs an internet connection once and takes a few minutes. After that it starts in seconds and works offline. Your browser opens to `http://127.0.0.1:8765`.

For developers:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python run.py                    # start the app
python -m pytest -q              # run the tests
python scripts/benchmark.py      # time it on about 300,000 visits
```

No export handy? The start screen has two buttons that load made-up sample practices from `data/`.

## Repository layout

```
delta-chair-forecast/
├── run.py                     starts the local server and opens the browser
├── start-windows.bat          double-click launchers
├── start-mac.command
├── start-linux.sh
├── chairforecast/
│   ├── columns.py             header matching and the never-read list for names and contacts
│   ├── ingest.py              file reading, date parsing, status vocabulary
│   ├── features.py            patient history and visit features (no look-ahead)
│   ├── model.py               gradient boosted trees plus an honest holdout test
│   ├── staffing.py            daily and hourly staffing plan
│   ├── pipeline.py            ties it together and anonymizes patients
│   ├── settings.py            fees, visit lengths, thresholds, staffing ratios
│   ├── server.py              Flask app, localhost only, strict security headers
│   └── synthetic.py           generator for the made-up sample practices
├── web/                       the interface: plain HTML, CSS and JavaScript, no frameworks
├── data/                      two fabricated sample exports
├── docs/                      manuals
├── scripts/                   sample rebuild and benchmark
└── tests/                     pytest suite, run on Windows, macOS and Linux in CI
```

## Manuals

| For | Read |
| --- | --- |
| The office manager installing it | [docs/SETUP.md](docs/SETUP.md) |
| Front desk and anyone using it day to day | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| Getting the right file out of the practice software | [docs/EXPORTING_YOUR_DATA.md](docs/EXPORTING_YOUR_DATA.md) |
| The practice's privacy or compliance contact | [docs/PRIVACY.md](docs/PRIVACY.md) |
| Anyone who wants to know how the numbers are made | [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) |
| Developers changing the interface | [docs/FRONTEND.md](docs/FRONTEND.md) |
| Presenting it to a practice | [docs/PITCH_GUIDE.md](docs/PITCH_GUIDE.md) |
| Putting this repository on GitHub | [docs/GITHUB_UPLOAD.md](docs/GITHUB_UPLOAD.md) |

## Speed

Reading is limited to the columns that are needed, dates are parsed once per distinct value instead of once per row, and patient history is one sort plus running totals. The model is scikit-learn's histogram gradient boosting, which bins each feature once and then builds trees in time proportional to the number of rows. On a laptop:

| Visits in the file | Time end to end |
| --- | --- |
| 15,000 (one practice, 18 months) | about 1.5 seconds |
| 290,000 (a multi-office group) | about 22 seconds |

Details are in [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#how-long-it-takes).

## Limits worth knowing

The estimates are only as good as the export. If a practice marks no-shows inconsistently (sometimes "broken", sometimes just deleting the appointment), the model learns from that noise. A ranking score somewhere around 0.65 to 0.80 is common for no-show models (the sample data lands near 0.69). That is useful for deciding who to call first, but it is not a crystal ball. The staffing numbers are a planning aid for the office manager, not a rule.

This is not medical software and doesn't touch clinical decisions. It is also not a HIPAA compliance certification. See [docs/PRIVACY.md](docs/PRIVACY.md) for exactly what it does and doesn't do with data.

## License

MIT. See [LICENSE](LICENSE).
