# Using Chair Forecast

This guide is for the front desk and the office manager. If the app isn't installed yet, start with [SETUP.md](SETUP.md).

## The short version

1. Export your appointment list from your practice software. It should cover at least six months of past visits and the days you want to plan. ([How to export](EXPORTING_YOUR_DATA.md))
2. Start the app and drag the file onto the window. You can drop it anywhere on the page.
3. Wait a few seconds while the triangle turns.
4. Pick a day along the top. Read the plan, call the high-risk patients, and adjust staffing if it makes sense.
5. Click Start over (or close the app) when you're done. That wipes the data from memory.

A good habit is to run it on Thursday afternoon for the following week, and again each afternoon for two days out.

## What's on the plan

### The day tabs

Each tab is one day. The red bar shows how many no-shows are expected that day compared with the other days in the file, so you can spot the rough days at a glance.

### The summary

A sentence like this one:

> Monday, October 19: 45 visits. Expect about 5 no-shows (likely 2 to 8). $1,125 of $11,620 booked is at risk.

"Likely 2 to 8" means that in 8 out of 10 days that look like this one, the number of no-shows lands in that range. "At risk" adds up each visit's fee times its chance of being missed.

Under it is a short to-do list. It might suggest calling the high-risk patients, point out the hours with the most likely empty chair time, or mention when the schedule is staffed for more patients than will probably show up.

### Team on the floor

Three rows: hygienists, dental assistants and front desk. The first number is what the schedule needs if every patient shows up. The second is what the day likely needs. When they differ, the first one is crossed out.

The plan is built for a day busier than 80% of likely outcomes, so you shouldn't get caught short often. You can change that in Settings.

These numbers are a starting point for the office manager. They don't know about vacations, a new hire who needs supervision, or the doctor who runs behind every Tuesday. Use them alongside what you already know.

### Hour by hour

One row per hour, like the left edge of your appointment book.

- The outlined bar shows chairs booked in that hour. The filled bar shows chairs likely to actually have a patient in them.
- "Empty min." is the chair time likely to go unused in that hour.
- "Staff needed" shows hygienists and assistants needed in that hour after likely no-shows.
- "Double-book here" marks hours with at least 30 likely empty chair minutes. Those are the best places to add a short visit or offer a spot from the ASAP list.

### Visits and who to call

Every visit on that day, one row each.

| Column | Meaning |
| --- | --- |
| Patient | A number, not a name. Patient 1 is the first patient of the first planned day. |
| Chance of missing | The model's estimate, from 0% to 100%. |
| Risk | Low, Medium or High. High starts at 25% by default; change it in Settings. |
| Why | Up to three plain reasons, taken from the patient's history and your practice's own patterns. |
| Outcome | Only in check mode. Shows whether the patient actually came. |

Use the buttons above the table to show only High or Medium patients, or to sort with the most likely misses first. Tick "All days" to see every day in one list. Type a number in the search box to jump to one patient.

"Download this list" saves the current list as a spreadsheet. It contains patient numbers only.

### Finding out who Patient 12 is

The app never shows names. To match a number to a real patient, click "Get the private lookup file". It downloads a small spreadsheet that pairs each patient number with the chart number from your practice software. Look the chart number up in your system as usual.

Treat that file like any other patient record. Keep it on the office computer, don't email it, and delete it when you're done with the day's calls. The numbers change every time you run the app, so an old lookup file won't match a new run anyway.

### How reliable is this

Before scoring anything, the app tests itself on your own data. It learns from the older part of your history and predicts the most recent part, which it hasn't seen, then compares.

The two numbers to look at first are "of patients rated High actually missed" and "of patients rated Low actually missed". If High is several times bigger than Low, the ranking is doing its job. The table next to them shows whether the percentages themselves can be taken at face value: when "Predicted to miss" and "Actually missed" are close, they can.

### What drives misses at this practice

Plain averages from your history: miss rate by how far ahead the visit was booked, by past misses, by weekday, by visit type and by insurance group. The red tick is your practice-wide rate. These are worth a look on their own. In the sample practice, visits booked more than 90 days ahead are missed about three times as often as visits booked within a week. Check whether yours look the same; if they do, a reminder call a week before recall visits may help more than anything else.

## Check mode

If every visit in your file already has an outcome (nothing is marked scheduled), the app can't plan the future, so it does the next best thing. It hides the last five working days, predicts them, and shows you what really happened next to each prediction. The heading says "How last week would have looked".

This is the best way to try the app before trusting it. Export last month, drop it in, and see whether the patients it flagged really were the ones who didn't come.

## Settings

Click Settings at the top of the plan. Changes apply right away and don't redo the learning, so they take a moment at most.

| Setting | Default | What it changes |
| --- | --- | --- |
| Medium starts at | 12% | Where Low ends and Medium begins |
| High starts at | 25% | Where Medium ends and High begins |
| Shift length | 8 hours | Used to turn chair hours into people |
| Chairside share of a shift | 85% | The rest of a shift goes to setup, breaks and notes |
| Assistants per dentist | 1 | Use 2 if your dentists usually work with two assistants |
| Patients per front desk person | 30 | Check-ins and check-outs one person can handle in a day |
| Plan for a day busier than | 80% | Higher means fewer surprises and more staff |
| Mark an hour for double-booking at | 30 min | Likely empty chair minutes before an hour is flagged |
| Name used in the call script | our office | Fills in the reminder script |

If your export has no fee or length column, Settings also shows typical fees and lengths by visit type. Replace them with your own fee schedule for accurate "at risk" numbers.

## Printing a huddle sheet

Click "Print huddle sheet" on a day. The printout keeps the summary, staffing, hour-by-hour plan and visit list, and drops the buttons and charts. It shows patient numbers only.

## Fixing the column matching

Open "Columns read from your file" at the bottom of the plan to see exactly which column was used for what, which columns were never read, and how each status word in your file was understood (kept, missed, cancelled, upcoming). If something was matched wrong, click "Fix the column matching", pick the right columns, and run it again.

If the app can't find the patient number, the date or the status by itself, it shows the matching screen straight away.

## If something goes wrong

| Message or problem | Likely cause and fix |
| --- | --- |
| "Every visit in this file is still marked as scheduled" | The export only has future visits. Export a range that also covers at least six months of past visits. |
| "Only N past visits with N misses were found" | Not enough history for the full model. The app falls back to a simpler estimate. Export a longer range (12 to 18 months is ideal). |
| The status values look wrong under "Columns read" | Your system uses a word the app doesn't know. Rename it in the export (for example, change "DNS" to "No show") or tell whoever maintains the app so it can be added. |
| "Older .xls files are not supported" | Open the file in Excel and save it as .xlsx or CSV. |
| "That file is over 750 MB" | Export a shorter range, such as the last 18 months. |
| Times all show as 7:00 or 8:00 AM | The export has no time column. Add the appointment time to the report if your system allows it. |
| The plan shows days you didn't expect | The export included visits further out than you meant. Only the first 60 days are planned. |
| "This session has ended" | The app was restarted or sat idle for two hours. Drop the file in again. |
| The page won't load | The app's black window was closed. Start it again. |
