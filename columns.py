"""Column detection.

Practice management systems name the same thing a dozen ways ("Appt Date",
"AptDateTime", "Date of Service"). This module maps whatever headers a file has
onto the small set of fields the model needs, and decides which columns must
never be read at all (names, phones, addresses, emails).

Only columns that map to a field below are ever loaded into memory. Everything
else in the file, including every column that looks like a name, is skipped at
read time.
"""

from __future__ import annotations

import re

# Canonical field -> header spellings, already normalized (lowercase, letters
# and digits only). Order matters: earlier spellings win when two headers match.
FIELD_SYNONYMS: dict[str, list[str]] = {
    "patient_id": [
        "patnum", "patientid", "patid", "chartnumber", "chartno", "chart",
        "chartid", "patientnumber", "patientno", "accountnumber", "accountno",
        "account", "mrn", "medicalrecordnumber", "patientchart", "ptid", "ptnum",
        "patientkey", "clientid", "customerid", "pt", "ptno", "ptnumber", "patient", "id",
    ],
    "appt_datetime": [
        "aptdatetime", "apptdatetime", "appointmentdatetime", "appointmentdateandtime",
        "startdatetime", "scheduledstart", "starttimestamp", "datetime", "start", "when", "appointment",
    ],
    "appt_date": [
        "apptdate", "aptdate", "appointmentdate", "dateofappointment", "dateofservice",
        "dos", "servicedate", "visitdate", "scheduleddate", "date", "day",
    ],
    "appt_time": [
        "appttime", "apttime", "appointmenttime", "starttime", "time", "timeslot", "slot",
    ],
    "status": [
        "aptstatus", "apptstatus", "appointmentstatus", "status", "visitstatus",
        "outcome", "attended", "showstatus", "result", "noshow", "brokenappt", "broken",
    ],
    "procedure": [
        "procdescript", "procedures", "procedure", "proceduredescription", "proccodes",
        "proccode", "procedurecode", "cdtcode", "cdt", "apptreason", "reason",
        "appointmenttype", "appttype", "visittype", "type", "description", "service", "services", "svc",
    ],
    "date_scheduled": [
        "secdatetentry", "datescheduled", "dateentered", "datecreated", "createddate",
        "createdon", "bookeddate", "datebooked", "bookedon", "scheduledon",
        "datemade", "entrydate", "dateadded", "datetstamp",
    ],
    "lead_time_days": [
        "leadtimedays", "leadtime", "daysinadvance", "daysbooked", "leaddays",
    ],
    "birthdate": [
        "birthdate", "dateofbirth", "dob", "birthday", "bdate",
    ],
    "age": ["age", "patientage", "ageyears"],
    "insurance": [
        "carriername", "primaryinscarrier", "primaryinsurance", "insurancecarrier",
        "insurance", "carrier", "insurancetype", "payer", "payor", "plan",
        "insplan", "planname", "primarycarrier", "coverage", "fincls", "financialclass",
    ],
    "fee": [
        "procfee", "amount", "fee", "production", "scheduledproduction", "apptfee",
        "charges", "charge", "totalfee", "estimatedfee", "value", "price",
    ],
    "provider": [
        "provabbr", "provider", "providerid", "prov", "doctor", "dentist",
        "hygienist", "clinician", "staff", "renderingprovider",
    ],
    "operatory": ["op", "operatory", "chair", "room", "opnum", "column"],
    "duration_min": [
        "length", "duration", "durationmin", "minutes", "apptlength", "lengthmin",
        "mins", "units",
    ],
}

# Headers containing any of these fragments are never read, even if they would
# otherwise match a field. "name" catches LName, FName, PatientName, Guarantor
# Name; the rest catch contact details and government identifiers.
NEVER_READ_FRAGMENTS = [
    "name", "fname", "lname", "first", "last", "middle", "nickname", "preferred",
    "phone", "cell", "mobile", "wireless", "fax", "email", "mail", "address",
    "addr", "street", "city", "zip", "postal", "ssn", "social", "license",
    "guarantor", "subscriber", "employer", "emergency", "contact", "note",
    "comment", "memo",
]

# Exact normalized headers that are allowed even though they contain a blocked
# fragment ("lastvisit" contains "last" but is not a name).
NEVER_READ_EXCEPTIONS = {
    "lastvisit", "lastvisitdate", "firstvisit", "firstvisitdate",
    "carriername", "planname", "insplanname", "insurancename", "payername",
    "primaryinscarriername", "carrier1name", "insurancecarriername",
}

REQUIRED_FIELDS = ["patient_id", "appt_date"]


def normalize_header(header: object) -> str:
    """'Appt. Date ' -> 'apptdate'."""
    return re.sub(r"[^a-z0-9]", "", str(header).lower())


def is_identifying(header: object) -> bool:
    norm = normalize_header(header)
    if norm in NEVER_READ_EXCEPTIONS:
        return False
    return any(frag in norm for frag in NEVER_READ_FRAGMENTS)


def detect_columns(headers: list[str]) -> dict[str, str]:
    """Return {canonical_field: original_header} for every field we can find.

    Matching is exact on the normalized header first, then "contains" for the
    longer spellings. Each header is used at most once. Identifying columns are
    never matched. Runs in O(headers x synonyms), which is a few hundred string
    comparisons for a typical export.
    """
    norm_to_orig = {}
    for h in headers:
        n = normalize_header(h)
        if n and not is_identifying(h) and n not in norm_to_orig:
            norm_to_orig[n] = h

    taken: set[str] = set()
    mapping: dict[str, str] = {}

    # Pass 1: exact matches, in priority order.
    for field, spellings in FIELD_SYNONYMS.items():
        for s in spellings:
            if s in norm_to_orig and norm_to_orig[s] not in taken:
                mapping[field] = norm_to_orig[s]
                taken.add(norm_to_orig[s])
                break

    # Pass 2: substring matches for fields still missing. Short spellings are
    # skipped here because "id" or "op" would match half the file.
    for field, spellings in FIELD_SYNONYMS.items():
        if field in mapping:
            continue
        for s in spellings:
            if len(s) < 5:
                continue
            hit = next((orig for n, orig in norm_to_orig.items()
                        if s in n and orig not in taken), None)
            if hit is not None:
                mapping[field] = hit
                taken.add(hit)
                break

    # A combined date-time column also satisfies the date requirement.
    if "appt_date" not in mapping and "appt_datetime" in mapping:
        mapping["appt_date"] = mapping["appt_datetime"]

    return mapping


def missing_required(mapping: dict[str, str]) -> list[str]:
    return [f for f in REQUIRED_FIELDS if f not in mapping]


FIELD_LABELS = {
    "patient_id": "Patient or chart number",
    "appt_datetime": "Appointment date and time (one column)",
    "appt_date": "Appointment date",
    "appt_time": "Appointment time",
    "status": "Appointment status (kept, broken, scheduled)",
    "procedure": "Procedure or appointment type",
    "date_scheduled": "Date the appointment was booked",
    "lead_time_days": "Days booked in advance",
    "birthdate": "Birth date (turned into age, then discarded)",
    "age": "Age",
    "insurance": "Insurance carrier or plan",
    "fee": "Scheduled fee or production",
    "provider": "Provider",
    "operatory": "Operatory or chair",
    "duration_min": "Length in minutes",
}
