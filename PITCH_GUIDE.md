# Showing Chair Forecast to a practice

Notes for presenting the tool to a dentist or office manager. The aim of a first meeting is a pilot: they run it on their own data for a few weeks and decide whether it helps.

## Who to talk to

The office manager first. They own the schedule, the staffing and the confirmation calls, and they feel no-shows most directly. The dentist cares about the result (fewer empty chairs, less overtime) but usually isn't the one who'd use it.

## The problem, in their words

Don't open with machine learning. Open with their morning:

- A hygiene chair that sits empty for an hour still has a hygienist being paid to stand next to it.
- The front desk confirms everyone the same way, so the patients most likely to miss get the same text as the ones who never miss.
- Staffing is set weeks ahead from the booked schedule, even though everyone knows some of those patients won't come.

Ask how many no-shows they had last week and what they did about them. Their answer is your pitch.

## A ten-minute demo

1. Start the app on a laptop before you walk in. Point out the "Running on this computer" label in the corner. Privacy is usually the first worry; answer it before they ask.
2. Click "Check last week against what happened". Explain that the app hid the last week of a made-up practice and predicted it. Scroll to a day and point to the Outcome column: most of the patients marked High really did miss. This is the strongest moment of the demo, because it's evidence, not a promise.
3. Go back and click "Plan the next two weeks". Walk through one day: the summary sentence, the staffing rows ("the schedule asks for 5 hygienists, the likely turnout needs 4"), and the hours marked "Double-book here".
4. Open "How reliable is this". Explain the two big numbers in plain terms: of the patients it called high risk, about 30% missed; of the low-risk ones, about 7%.
5. Show that names never appear and that the lookup file is opt-in.

## What to offer

A free pilot. They export last month's appointments, run it in check mode with you sitting next to them, and see whether it spots their real no-shows. If it does, they use it for three or four weeks and keep a simple tally: how many high-risk patients got a phone call, how many of those showed, and whether any staffing changes were made.

Be clear about what you'd ask from them: one export at the start, ten minutes a week, and an honest opinion at the end.

## Questions you'll get

**Is this HIPAA compliant?** Say what it does rather than claiming a label. Everything runs on their computer, nothing is uploaded, names and contact details are never read, and results show only patient numbers. Point them to docs/PRIVACY.md and suggest their privacy officer look it over. Don't call it "HIPAA certified"; there is no such certification, and saying so would hurt your credibility.

**How accurate is it?** It depends on their data, which is why the app tests itself on their own history and shows the result. On the sample practice the high-risk group misses about four times as often as the low-risk group.

**Do we need to install anything?** Python, once. After that it's a double-click. You can offer to do the setup for them.

**What does it cost?** Decide this before the meeting. For a pilot, free is the honest answer; the software is open source under the MIT license.

**Will it tell us to turn patients away?** No. It's for deciding who gets an extra reminder call and how to staff the day. It should never be used to deny or delay care.

## Describing the project honestly

On applications or a résumé, describe exactly what exists at the time you write it. For example, before any practice has used it:

> Built an open-source, privacy-first tool that predicts dental appointment no-shows from practice management exports and turns them into daily staffing plans; runs entirely on the office computer and was validated on held-out appointment data.

After a pilot, add what actually happened: how many practices, how many weeks, and any numbers they agreed to share. Admissions readers and practice owners both respond better to a modest claim with evidence than to a big one without it.
