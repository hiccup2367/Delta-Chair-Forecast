# Getting the right file out of your practice software

Chair Forecast reads one file: a list of appointments, one row per appointment. Most practice software can produce this as a report and save it as CSV or Excel.

Menu names change between versions, so treat the steps below as directions rather than exact clicks. If you get stuck, your software's support line can tell you which report lists appointments with their status. Ask for "an appointment list I can export to Excel, including broken and completed appointments".

## What to include

Date range: the last 12 to 18 months plus the days you want to plan. Six months is the minimum for useful results.

| Column | Needed? | Why |
| --- | --- | --- |
| Patient or chart number | Yes | To link a patient's visits together. Never used for anything else. |
| Appointment date and time | Yes | One column with both, or two separate columns. |
| Appointment status | Yes | Complete, broken, no-show, cancelled, scheduled and so on. This is what the app learns from. |
| Procedure or appointment type | Strongly recommended | Hygiene recalls and crown seats behave very differently. CDT codes or short descriptions both work. |
| Date the appointment was made | Strongly recommended | How far ahead a visit was booked is one of the strongest signals. |
| Birth date or age | Recommended | Turned into an age, then thrown away. |
| Insurance carrier | Recommended | Grouped into PPO, HMO, Medicaid or CHIP, and self-pay. |
| Scheduled fee or production | Optional | Without it, typical fees by visit type are used for "at risk" dollars. |
| Appointment length | Optional | Without it, typical lengths by visit type are used. |
| Provider | Optional | Helps the hour-by-hour view. |
| Operatory | Optional | Shown in the column list; not used in the model yet. |

You don't need to remove patient names, phone numbers or addresses first. The app recognizes those columns by their headers and never reads them. That said, if your report lets you leave them out, do; less sensitive data on disk is always better.

Leaving out cancelled appointments is fine. Leaving out broken appointments is not: if the export only contains visits that happened, there is nothing to learn from.

## Status words the app understands

Missed: broken, no show, no-show, missed, FTA, failed, did not show, DNS, late cancel, short notice cancel, same day cancel.

Kept: complete, completed, kept, seen, arrived, checked in, checked out, attended, posted.

Cancelled (left out of learning): cancelled, canceled, rescheduled, unscheduled, deleted, moved.

Upcoming: scheduled, booked, confirmed, unconfirmed, pending, tentative, ASAP, or blank.

Open Dental's numeric AptStatus codes are understood too: 1 scheduled, 2 complete, 3 unscheduled list, 5 broken.

A column called "No Show" or "Broken" with Y/N or 1/0 values works as well.

After a run, open "Columns read from your file" at the bottom of the plan to see how each status in your file was understood.

## Dentrix

Dentrix has appointment list reports in the Office Manager under the reports or lists menus. Pick the report that lists appointments by date and includes the status (look for "Broken" appointments in the output), set the date range, and export or save it as CSV or Excel. Report title lines at the top of the file are fine; the app skips them.

If your version can't include broken appointments in the same list, run the broken appointment list separately for the same date range, paste its rows under the main list in Excel with a Status column set to "Broken", and save.

## Open Dental

The cleanest route is a User Query (Reports, then User Query), which exports straight to CSV. This query is a starting point; have whoever manages your Open Dental database check it against your version before running it.

```sql
SELECT a.PatNum, a.AptDateTime, a.AptStatus, a.ProcDescript,
       pr.Abbr AS ProvAbbr, a.Op,
       LENGTH(a.Pattern) * 5 AS Length,      -- assumes 5-minute schedule increments
       a.SecDateTEntry,                      -- when the appointment was made
       p.Birthdate, c.CarrierName
FROM appointment a
JOIN patient p ON p.PatNum = a.PatNum
LEFT JOIN provider pr ON pr.ProvNum = a.ProvNum
LEFT JOIN patplan pp ON pp.PatNum = a.PatNum AND pp.Ordinal = 1
LEFT JOIN inssub s ON s.InsSubNum = pp.InsSubNum
LEFT JOIN insplan ip ON ip.PlanNum = s.PlanNum
LEFT JOIN carrier c ON c.CarrierNum = ip.CarrierNum
WHERE a.AptDateTime >= DATE_SUB(CURDATE(), INTERVAL 18 MONTH)
  AND a.AptStatus IN (1, 2, 3, 5)
ORDER BY a.AptDateTime;
```

Notes:

- If your schedule uses 10 or 15 minute increments, change the `* 5` to match.
- If the query complains about `SecDateTEntry`, delete that line. You lose the booking lead time, which costs some accuracy, but everything else works.
- This query doesn't select names, phones or addresses at all, which is the best case for privacy.

## Eaglesoft

Look for an appointment history or appointment list report under the reports menu that can include broken and completed appointments. Set the date range and export to Excel or CSV. If the report has a "Broken" or "Status" column, you're set.

## Other systems (Curve, Denticon, Dentrix Ascend, tab32 and others)

Any report that gives one row per appointment with a patient number, date and status will work. Cloud systems often have an "export to CSV" option on their appointment or scheduling reports.

## Checking the file before you drop it in

Open it in Excel and look for three things:

1. One row per appointment.
2. A status column where some rows say something like Broken or No Show.
3. Dates both in the past and in the days you want to plan.

If all three are there, drop it in. The app sorts out the column names by itself, and if it can't find something, it will ask.
