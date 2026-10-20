"""Reading practice management exports.

The goal is zero setup for the person dropping the file in:

* CSV, TSV, semicolon or pipe separated text, and .xlsx all work.
* Title lines above the real header (common in Dentrix and Eaglesoft reports)
  are skipped automatically.
* Only the columns we need are read. Name, phone, email and address columns are
  never loaded into memory, so they cannot leak into results or logs.
* Dates and times are parsed once per unique value, then mapped back onto the
  rows. A year of appointments has hundreds of distinct dates but hundreds of
  thousands of rows, so this turns the slowest step from O(rows) parser calls
  into O(unique values) parser calls plus an O(rows) hash lookup.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .columns import detect_columns, is_identifying, missing_required

TEXT_EXTENSIONS = (".csv", ".txt", ".tsv", ".tab")
EXCEL_EXTENSIONS = (".xlsx", ".xlsm")


class IngestError(ValueError):
    """A problem with the file that the person can fix. The message is shown as-is."""


@dataclass
class FileShape:
    kind: str                      # "text" or "excel"
    headers: list[str]
    header_row: int                # rows to skip before the header
    sep: str = ","
    encoding: str = "utf-8"
    mapping: dict[str, str] = field(default_factory=dict)
    skipped_identifying: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# File shape detection
# --------------------------------------------------------------------------- #

def _decode_sample(data: bytes) -> tuple[str, str]:
    sample = data[: 256 * 1024]
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return sample.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise IngestError("The file's text encoding could not be read. Save it as CSV (UTF-8) and try again.")


def _best_header_row(rows: list[list[str]]) -> int:
    """Pick the row that looks most like a header: the one matching the most fields."""
    best_idx, best_score = 0, -1
    for i, row in enumerate(rows[:30]):
        cells = [c for c in row if str(c).strip() and str(c).lower() != "nan"]
        if len(cells) < 2:
            continue
        score = len(detect_columns(cells))
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx


def inspect_file(data: bytes, filename: str) -> FileShape:
    """Work out file type, separator, encoding, header row and column mapping."""
    if not data:
        raise IngestError("The file is empty.")
    name = (filename or "").lower()

    if name.endswith(".xls"):
        raise IngestError("Older .xls files are not supported. Open it in Excel and save as .xlsx or .csv.")

    if name.endswith(EXCEL_EXTENSIONS) or data[:4] == b"PK\x03\x04":
        try:
            preview = pd.read_excel(io.BytesIO(data), header=None, nrows=30, dtype=str, engine="openpyxl")
        except Exception as exc:  # noqa: BLE001
            raise IngestError(f"This spreadsheet could not be opened ({exc.__class__.__name__}).") from exc
        rows = preview.fillna("").astype(str).values.tolist()
        hdr = _best_header_row(rows)
        headers = [h.strip() for h in rows[hdr] if h.strip()]
        shape = FileShape(kind="excel", headers=headers, header_row=hdr)
    else:
        text, enc = _decode_sample(data)
        lines = text.splitlines()[:40]
        try:
            sep = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",;\t|").delimiter
        except csv.Error:
            sep = "\t" if name.endswith((".tsv", ".tab")) else ","
        rows = list(csv.reader(lines, delimiter=sep))
        if not rows:
            raise IngestError("No rows were found in the file.")
        hdr = _best_header_row(rows)
        headers = [h.strip() for h in rows[hdr]]
        shape = FileShape(kind="text", headers=headers, header_row=hdr, sep=sep, encoding=enc)

    shape.mapping = detect_columns(shape.headers)
    shape.skipped_identifying = [h for h in shape.headers if h and is_identifying(h)]
    return shape


def load_columns(data: bytes, shape: FileShape, mapping: dict[str, str]) -> pd.DataFrame:
    """Read only the mapped columns, renamed to canonical field names."""
    bad = [src for src in mapping.values() if is_identifying(src)]
    if bad:
        raise IngestError(f"These columns look like names or contact details and will not be read: {', '.join(bad)}")

    wanted = sorted(set(mapping.values()))
    if shape.kind == "excel":
        df = pd.read_excel(
            io.BytesIO(data), header=shape.header_row, dtype=object, engine="openpyxl",
            usecols=lambda c: str(c).strip() in wanted,
        )
        df.columns = [str(c).strip() for c in df.columns]
    else:
        df = pd.read_csv(
            io.BytesIO(data), sep=shape.sep, encoding=shape.encoding, skiprows=shape.header_row,
            header=0, dtype=str, usecols=lambda c: str(c).strip() in wanted,
            skipinitialspace=True, on_bad_lines="skip", engine="c", low_memory=False,
        )
        df.columns = [str(c).strip() for c in df.columns]

    out = pd.DataFrame(index=df.index)
    for fld, src in mapping.items():
        if src in df.columns:
            out[fld] = df[src]
    return out


# --------------------------------------------------------------------------- #
# Value parsing
# --------------------------------------------------------------------------- #

def _map_unique(series: pd.Series, parse) -> pd.Series:
    """Apply an expensive parser once per distinct value, then broadcast."""
    codes, uniques = pd.factorize(series, use_na_sentinel=True)
    if len(uniques) == 0:
        return pd.Series(pd.NaT, index=series.index)
    parsed = parse(pd.Series(uniques))
    values = np.asarray(parsed)
    result = values[np.where(codes >= 0, codes, 0)]
    out = pd.Series(result, index=series.index)
    out[codes < 0] = None
    return out


def _parse_dates(values: pd.Series) -> pd.Series:
    as_text = values.astype(str).str.strip()
    return pd.to_datetime(as_text, errors="coerce", format="mixed")


def parse_datetime_col(series: pd.Series) -> pd.Series:
    return pd.to_datetime(_map_unique(series, _parse_dates), errors="coerce")


def parse_time_col(series: pd.Series) -> pd.Series:
    """Return minutes after midnight, or NaN."""
    def _parse(values: pd.Series) -> pd.Series:
        txt = values.astype(str).str.strip().str.upper().str.replace(".", "", regex=False)
        parsed = pd.to_datetime(txt, errors="coerce", format="mixed")
        return parsed.dt.hour * 60 + parsed.dt.minute
    return pd.to_numeric(_map_unique(series, _parse), errors="coerce")


def parse_number(series: pd.Series) -> pd.Series:
    txt = series.astype(str).str.strip()
    negative = txt.str.startswith("(") & txt.str.endswith(")")
    cleaned = txt.str.replace(r"[^0-9.\-]", "", regex=True)
    num = pd.to_numeric(cleaned, errors="coerce")
    return num.where(~negative, -num)


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #

KEPT, NO_SHOW, CANCELLED, SCHEDULED, UNKNOWN = "kept", "no_show", "cancelled", "scheduled", "unknown"

_NO_SHOW_WORDS = ("noshow", "broken", "brk", "missed", "fta", "failedtoarrive", "failed",
                  "didnotshow", "didntshow", "latecancel", "shortnotice", "samedaycancel",
                  "lastminutecancel", "nocall")
_KEPT_WORDS = ("complete", "kept", "seen", "arrived", "checkedout", "checkout", "checkedin",
               "attended", "done", "finished", "showed", "posted")
_CANCEL_WORDS = ("cancel", "resched", "deleted", "unsched", "moved", "void")
_SCHED_WORDS = ("schedul", "booked", "confirm", "pending", "open", "future", "tentative",
                "asap", "reminded", "unconfirmed", "sch")
_OPEN_DENTAL_CODES = {"1": SCHEDULED, "2": KEPT, "3": CANCELLED, "5": NO_SHOW}
_TRUE = {"1", "y", "yes", "true", "t", "x"}
_FALSE = {"0", "n", "no", "false", "f", ""}


def classify_status_value(raw: object, header_norm: str = "status") -> str:
    v = "" if raw is None or (isinstance(raw, float) and np.isnan(raw)) else str(raw).strip()
    if v.endswith(".0") and v[:-2].isdigit():  # "2.0" from Excel
        v = v[:-2]
    norm = "".join(ch for ch in v.lower() if ch.isalnum())
    if header_norm in ("noshow", "brokenappt", "broken"):
        return NO_SHOW if norm in _TRUE else KEPT if norm in _FALSE else UNKNOWN
    if header_norm == "attended":
        return KEPT if norm in _TRUE else NO_SHOW if norm in _FALSE and norm else UNKNOWN
    if "aptstatus" in header_norm and norm in _OPEN_DENTAL_CODES:
        return _OPEN_DENTAL_CODES[norm]
    if not norm:
        return SCHEDULED
    if norm in ("ns", "dns", "b"):
        return NO_SHOW
    if norm in ("c", "k", "comp", "cmp"):
        return KEPT
    if norm == "x":
        return CANCELLED
    for words, label in ((_NO_SHOW_WORDS, NO_SHOW), (_KEPT_WORDS, KEPT),
                         (_CANCEL_WORDS, CANCELLED), (_SCHED_WORDS, SCHEDULED)):
        if any(w in norm for w in words):
            return label
    return UNKNOWN


def classify_status(series: pd.Series, header: str) -> tuple[pd.Series, dict[str, str]]:
    from .columns import normalize_header
    hn = normalize_header(header)
    uniques = pd.Series(series.unique())
    table = {u: classify_status_value(u, hn) for u in uniques}
    shown = {("(blank)" if (u is None or (isinstance(u, float) and np.isnan(u)) or str(u).strip() == "")
              else str(u)): lab for u, lab in table.items()}
    return series.map(table).fillna(SCHEDULED), shown


# --------------------------------------------------------------------------- #
# Standardize
# --------------------------------------------------------------------------- #

def standardize(raw: pd.DataFrame, mapping: dict[str, str]) -> tuple[pd.DataFrame, dict]:
    """Turn mapped raw columns into typed fields. Returns (frame, notes)."""
    notes: dict = {"warnings": []}
    df = pd.DataFrame(index=raw.index)

    pid = raw["patient_id"].astype(str).str.strip()
    pid = pid.where(~pid.isin(["", "nan", "None", "NaN"]))
    df["pid_raw"] = pid

    if "appt_datetime" in raw and mapping.get("appt_datetime") == mapping.get("appt_date"):
        dt = parse_datetime_col(raw["appt_datetime"])
    else:
        dt = parse_datetime_col(raw["appt_date"]).dt.normalize()
        if "appt_time" in raw:
            minutes = parse_time_col(raw["appt_time"])
            dt = dt + pd.to_timedelta(minutes.fillna(0), unit="m")
            if minutes.isna().all():
                notes["warnings"].append("Appointment times could not be read, so hour-by-hour planning is approximate.")
        elif (dt.dt.hour == 0).all():
            notes["warnings"].append("No appointment time column was found, so every visit is treated as a morning visit.")
    df["dt"] = dt

    before = len(df)
    keep = df["pid_raw"].notna() & df["dt"].notna()
    dropped = int(before - keep.sum())
    if dropped:
        notes["warnings"].append(f"{dropped:,} rows had no readable date or patient number and were skipped.")
    df = df[keep].copy()
    raw = raw.loc[df.index]

    if "status" in raw:
        df["status"], notes["status_values"] = classify_status(raw["status"], mapping["status"])
    else:
        df["status"] = SCHEDULED
        notes["status_values"] = {}

    df["procedure_raw"] = raw["procedure"].astype(str).str.strip() if "procedure" in raw else ""
    df["insurance_raw"] = raw["insurance"].astype(str).str.strip() if "insurance" in raw else ""
    df["provider"] = raw["provider"].astype(str).str.strip() if "provider" in raw else "Unassigned"
    df["operatory"] = raw["operatory"].astype(str).str.strip() if "operatory" in raw else ""
    df["fee"] = parse_number(raw["fee"]) if "fee" in raw else np.nan

    if "duration_min" in raw:
        dur = parse_number(raw["duration_min"])
        # Some systems export length in 10 or 15 minute units. Values under 13
        # are almost certainly units, not minutes.
        if dur.dropna().median() < 13:
            dur = dur * 10
        df["duration_min"] = dur.clip(5, 480)
    else:
        df["duration_min"] = np.nan

    appt_day = df["dt"].dt.normalize()
    if "date_scheduled" in raw:
        made = parse_datetime_col(raw["date_scheduled"]).dt.normalize()
        df["lead_time_days"] = (appt_day - made).dt.days.clip(lower=0)
    elif "lead_time_days" in raw:
        df["lead_time_days"] = parse_number(raw["lead_time_days"]).clip(lower=0)
    else:
        df["lead_time_days"] = np.nan

    if "birthdate" in raw:
        bd = parse_datetime_col(raw["birthdate"])
        age = (appt_day - bd).dt.days / 365.25
        df["age"] = age.where((age >= 0) & (age < 110))
    elif "age" in raw:
        df["age"] = parse_number(raw["age"]).where(lambda a: (a >= 0) & (a < 110))
    else:
        df["age"] = np.nan

    return df.reset_index(drop=True), notes
