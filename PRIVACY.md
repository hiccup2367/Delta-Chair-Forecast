# Privacy and data handling

This page is for the practice owner and whoever handles privacy or compliance. It describes exactly what Chair Forecast does with data. It is not legal advice and it is not a HIPAA certification. A practice using this tool should run it past its own privacy officer and keep following its normal policies for handling exports from the practice management system.

## The short answer

The app runs on the practice's own computer and nowhere else. Files are processed in memory and never uploaded, saved by the app, or sent to Delta Consulting or anyone else. Names and contact details are never read from the file. Patients appear in results only as numbers.

## Where the data goes

1. The person at the desk drags an export into a browser window. The browser hands the file to the app's own server, which is running on the same computer at the address 127.0.0.1. Traffic to 127.0.0.1 never leaves the machine.
2. The server reads the file into memory. It does not write the file to disk.
3. Results are sent back to the browser on the same computer and shown on screen.
4. When someone clicks Start over, closes the browser tab, closes the app, or leaves it idle for two hours, the file and results are dropped from memory.

The app makes no internet connections while running. The only time it touches the internet is during first-time setup, when the start file downloads standard open-source Python packages (Flask, pandas, scikit-learn and a few others) from the official Python package index. No practice data exists at that point.

## What is read from the file, and what isn't

Columns are chosen by their headers before any rows are read. Only the columns the model uses are loaded.

Never read, even if present: any column whose header looks like a name (first, last, middle, preferred, guarantor, subscriber), a phone number (phone, cell, mobile, wireless, fax), an email, an address (street, city, zip, postal), a Social Security or license number, an employer, an emergency contact, or free-text notes and comments. The app refuses to load these even if someone tries to pick them on the column matching screen.

Read, then thrown away: birth date is turned into an age at the time of each visit, then discarded.

Read and kept in memory during the session: patient or chart number (only to link visits together), appointment date and time, status, procedure text, date booked, insurance carrier name, fee, length, provider and operatory codes.

## What appears on screen and in downloads

- Patients are shown as Patient 1, Patient 2 and so on, numbered in appointment order for that run. The numbering is new every run.
- Chart numbers never appear on screen, in the call list download, or in the printout.
- Provider and operatory codes appear as they were exported (for example HYG1 or DDS2), because staffing decisions need them.
- The call list download contains patient numbers, dates, times, visit type, provider, chance of missing and reasons.

## The private lookup file

The one exception is the lookup file, which someone has to request on purpose (there's a confirmation box). It pairs patient numbers with chart numbers so the front desk can find patients in the practice software. It contains chart numbers and nothing else identifying. It should be handled like any other patient record: kept on the office computer, not emailed, and deleted after use. The `.gitignore` in this repository blocks files with that name from being committed by accident.

## Technical safeguards

- The server binds to 127.0.0.1 only, so other devices on the office network can't connect.
- It rejects requests whose Host header isn't this computer, which blocks a known trick where a malicious web page in another tab tries to talk to local servers.
- Every page carries a Content Security Policy that only allows loading code and sending data to the app itself. Even a bug in the interface couldn't send data to an outside address.
- No cookies, analytics, fonts or scripts are loaded from the internet. Everything the interface needs ships in the `web` folder.
- Responses are marked `no-store`, so the browser doesn't cache results to disk.
- Error messages shown in the app are written in plain language and never include rows from the file.

## What the practice is still responsible for

- The export file itself. It came out of the practice software and sits wherever it was saved, usually Downloads. Delete it after use, or save it to a folder that follows the practice's normal policies.
- The lookup file, if downloaded.
- Printed huddle sheets. They show patient numbers only, but treat them like any schedule printout.
- The computer: a login password, an up-to-date operating system, and disk encryption (BitLocker on Windows, FileVault on Mac) are the practice's normal baseline and still apply.

## Fairness note

Insurance group and age are among the things the model can learn from, because they can relate to transportation, scheduling flexibility and cost, all of which affect attendance. The output is meant for deciding who gets an extra reminder call and how to staff a day. It should never be used to refuse care, to book anyone into worse appointment times, or to treat patients differently in any clinical sense. If a practice prefers, removing the insurance or birth date column from the export takes those factors out entirely; the app works without them.
